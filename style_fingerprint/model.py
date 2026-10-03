"""Build, persist, compare, and validate the personal reference fingerprint."""
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .config import Config, VERSION, FEATURE_SCHEMA_VERSION, PREPROCESSING_VERSION, ENCODING_VERSION, WEIGHTS
from .corpus import NEGATIVE_CORPUS_POLICY, load_negative_corpus, Document, Passage, load_corpus, load_work_corpus, load_email_corpus, clean_email, clean_markdown, chunk_text, word_count, sentence_spans
from .embeddings import AuthorshipEncoder, cache_key, cosine_matrix, symmetric_maxsim
from .holdout import split_holdout, source as document_source, label as document_label
from .features import extract_features, stylometry_similarity, deviations, normalize_similarity, evidence_strength


def _document_structure(document):
    return document.clean_text if document.source_type == 'email' or (document.metadata or {}).get('genre', '').endswith('_email') else document.raw_markdown


def _genre_indices(documents, positive_ids):
    result = defaultdict(list)
    for index, doc in enumerate(documents):
        if doc.document_id in positive_ids:
            result[(doc.metadata or {}).get('genre', 'unknown')].append(index)
    return dict(result)


def _fold_genre_indices(folds):
    result = defaultdict(list)
    for index, fold in enumerate(folds):
        result[fold['genre']].append(index)
    return dict(result)


def _reject_primary_overlap(training_documents, test_documents):
    """Whole reserved documents and substantial copied prose must not enter fitting."""
    for test in test_documents:
        test_text = ' '.join(test.clean_text.split())
        test_paragraphs = [' '.join(p.split()) for p in test.clean_text.split('\n\n') if word_count(p) >= 20]
        for doc in training_documents:
            text = ' '.join(doc.clean_text.split())
            paragraphs = [' '.join(p.split()) for p in doc.clean_text.split('\n\n') if word_count(p) >= 20]
            if text == test_text or any(p in text for p in test_paragraphs) or any(p in test_text for p in paragraphs):
                raise ValueError(f'Primary positive test contamination/overlap: {test.document_id} and {doc.document_id}; remove copied prose from training inputs.')


@dataclass
class StyleScore:
    score: float
    raw_score: float
    evidence_strength: str
    word_count: int
    component_scores: dict
    feature_deviations: list = field(default_factory=list)
    strongest_matches: list = field(default_factory=list)
    largest_mismatches: list = field(default_factory=list)
    anomalous_sentences: list = field(default_factory=list)
    anomalous_passages: list = field(default_factory=list)
    nearest_reference_passages: list = field(default_factory=list)
    best_matching_documents: list = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    decision: str = "INCONCLUSIVE_OR_MISMATCH"
    match_threshold: float | None = None
    mismatch_threshold: float | None = None

    def to_dict(self):
        return asdict(self)


class StyleFingerprint:
    def __init__(self, documents, passages, embeddings, config, manifest=None, evaluation=None, verifier=None):
        self.documents = documents
        self.passages = passages
        self.embeddings = embeddings
        self.config = config
        self.manifest = manifest or {}
        self.evaluation = evaluation or {}
        self.verifier = verifier
        self.encoder = AuthorshipEncoder(config)
        self._embedding_cache = {cache_key(p.text, config): e for p, e in zip(passages, embeddings)}
        self._reference_cache = {}
        self._document_features = self.manifest.get('document_features') or {d.document_id: extract_features(d.clean_text, _document_structure(d)) for d in documents}

    @classmethod
    def build(cls, corpus_dir='blog_posts', artifact_dir='artifacts', *, config=None, negative_dir=None, work_dir=None, gmail_dir=None, primary_test_dir=None, holdout_fraction=.2, build_mode='evaluation', holdout_manifest=None, include_historical_holdout=True):
        if build_mode not in {'evaluation', 'production'}:
            raise ValueError('Build mode must be evaluation or production')
        artifact_dir = Path(artifact_dir)
        frozen = None
        frozen_evaluation = None
        prior_frozen = json.loads((artifact_dir / 'evaluation_config.json').read_text()) if (artifact_dir / 'evaluation_config.json').exists() else {}
        if build_mode == 'production':
            if not (artifact_dir / 'evaluation_config.json').exists() or prior_frozen.get('negative_corpus_policy') != NEGATIVE_CORPUS_POLICY or prior_frozen.get('feature_schema_version') != FEATURE_SCHEMA_VERSION:
                cls.build(corpus_dir, artifact_dir, config=config, negative_dir=negative_dir,
                          work_dir=work_dir, gmail_dir=gmail_dir, primary_test_dir=primary_test_dir,
                          holdout_fraction=holdout_fraction, holdout_manifest=holdout_manifest,
                          build_mode='evaluation')
            frozen = json.loads((artifact_dir / 'evaluation_config.json').read_text())
            frozen_evaluation = json.loads((artifact_dir / 'evaluation.json').read_text())
            config = config or Config(**frozen['configuration'])
            if (config.seed != frozen['random_seed'] or config.model_revision != frozen['encoder_revision']
                    or config.model_id != frozen['encoder_model'] or frozen['feature_schema_version'] != FEATURE_SCHEMA_VERSION
                    or frozen.get('view_generation_version') != 'paragraph-views-v1'
                    or frozen.get('segmentation') != {'minimum': 300, 'preferred_min': 350, 'preferred_max': 600, 'maximum': 700, 'max_views': 6}):
                raise ValueError('Production settings differ from frozen evaluation configuration; run evaluate first')
        config = config or Config()
        documents = load_corpus(corpus_dir)
        for doc in documents:
            doc.metadata = dict(doc.metadata or {}, genre='blog')
        work_root = Path(work_dir) if work_dir is not None and work_dir is not False else Path(corpus_dir).parent / 'work_corpus'
        if work_dir is not False and (work_dir is not None or work_root.exists()):
            documents += load_work_corpus(work_root)
        gmail_root = Path(gmail_dir) if gmail_dir is not None and gmail_dir is not False else Path(corpus_dir).parent / 'gmail_corpus'
        if gmail_dir is not False and (gmail_dir is not None or gmail_root.exists()):
            documents += load_email_corpus(gmail_root, source='gmail')
        if len({d.document_id for d in documents}) != len(documents):
            raise ValueError('Positive document IDs collide with reserved work/ or gmail/ namespaces; rename those blog files.')
        negative_root = Path(negative_dir) if negative_dir is not None else Path(corpus_dir).parent / 'negative_posts'
        negatives = load_negative_corpus(negative_root) if negative_root.exists() else []
        for d in negatives:
            d.document_id = 'negative/' + d.document_id
            d.root_document_id = d.document_id
            d.metadata = dict(d.metadata or {}, genre='negative_posts')
        negative_hashes = {d.root_document_id: d.file_hash for d in negatives}
        if frozen is not None and frozen.get('negative_corpus_hashes') != negative_hashes:
            raise ValueError('Eligible negative inputs changed; run evaluation before production refitting')
        sealed_ids = set(prior_frozen.get('sealed_holdout_ids', []))
        newly_sealed = set()
        if holdout_manifest is not None:
            sealed = json.loads(Path(holdout_manifest).read_text())
            newly_sealed = set(sealed.get('holdout_v2', sealed.get('document_ids', [])))
            if build_mode == 'production' and not newly_sealed <= set(frozen.get('sealed_holdout_ids', [])):
                raise ValueError('New sealed holdout designations require evaluation before production build')
            sealed_ids.update(newly_sealed)
        available = documents + negatives
        unknown = newly_sealed - {d.document_id for d in available}
        if unknown:
            raise ValueError('Sealed holdout manifest refers to unavailable documents')
        # Exclude connected duplicates and known negative authors as well as designated roots.
        if sealed_ids:
            from .holdout import document_groups
            groups = document_groups(available)
            sealed_groups = {groups[i] for i in sealed_ids if i in groups}
            sealed_ids.update(i for i, group in groups.items() if group in sealed_groups)
        documents = [d for d in documents if d.document_id not in sealed_ids]
        negatives = [d for d in negatives if d.document_id not in sealed_ids]
        holdout_documents = []
        holdout_split = None
        if build_mode == 'production':
            holdout_split = frozen.get('holdout_split')
            if not include_historical_holdout and holdout_split:
                excluded = set(holdout_split['holdout_document_ids'])
                documents = [d for d in documents if d.document_id not in excluded]
                negatives = [d for d in negatives if d.document_id not in excluded]
        elif holdout_fraction:
            if primary_test_dir is not None:
                raise ValueError('Use seeded holdout or legacy primary_test_dir with holdout_fraction=0, not both.')
            development, holdout_documents, holdout_split = split_holdout(documents + negatives, config.seed, holdout_fraction)
            documents = [d for d in development if document_label(d)]
            negatives = [d for d in development if not document_label(d)]
        all_docs = documents + negatives
        primary_root = Path(primary_test_dir) if primary_test_dir is not None else Path(corpus_dir).parent / 'test_corpus' / 'blog_posts'
        primary_tests = load_corpus(primary_root) if not holdout_fraction and (primary_test_dir is not None or primary_root.exists()) else []
        for doc in primary_tests:
            doc.document_id = 'primary_test/' + doc.document_id
            doc.root_document_id = doc.document_id
            doc.metadata = dict(doc.metadata or {}, genre='blog', role='primary_positive_test')
        _reject_primary_overlap(all_docs, primary_tests)
        passages = [p for d in all_docs for p in chunk_text(d.clean_text, d.document_id, root_document_id=d.root_document_id, author_id=d.author_id)]
        artifact_dir = Path(artifact_dir)
        old_cache = {}
        if (artifact_dir / 'manifest.json').exists():
            try:
                # Encoder cache compatibility is independent of the verifier feature schema.
                old_manifest = json.loads((artifact_dir / 'manifest.json').read_text())
                compatible = (old_manifest['model_id'] == config.model_id
                              and old_manifest['model_revision'] == config.model_revision
                              and old_manifest['preprocessing_version'] == PREPROCESSING_VERSION
                              and old_manifest['encoding_version'] == ENCODING_VERSION)
                if compatible:
                    for name in ['passages.parquet', 'embeddings.npy']:
                        expected = old_manifest.get('artifact_hashes', {}).get(name)
                        if expected is None or hashlib.sha256((artifact_dir / name).read_bytes()).hexdigest() != expected:
                            raise ValueError('Incompatible encoder cache')
                    frame = pd.read_parquet(artifact_dir / 'passages.parquet')
                    cached = np.load(artifact_dir / 'embeddings.npy', allow_pickle=False)
                    cached_keys = [cache_key(text, config) for text in frame['text']]
                    if (cached.ndim != 2 or len(cached) != len(frame) or not np.isfinite(cached).all()
                            or np.any(np.linalg.norm(cached, axis=1) == 0)
                            or list(frame['embedding_key']) != cached_keys):
                        raise ValueError('Corrupt encoder cache')
                    old_cache = dict(zip(cached_keys, cached))
            except (ValueError, OSError, KeyError):
                pass  # An incompatible cache is rebuilt, never used for scoring.
        keys = [cache_key(p.text, config) for p in passages]
        missing = dict((key, p.text) for key, p in zip(keys, passages) if key not in old_cache)
        encoder = AuthorshipEncoder(config)
        if missing:
            vectors = encoder.encode(list(missing.values()))
            if len(vectors) != len(missing):
                raise RuntimeError('Encoder returned the wrong number of passage embeddings')
            old_cache.update(zip(missing, vectors))
        embeddings = np.array([old_cache[key] for key in keys], dtype=np.float32)
        messages = []
        independent = len({d.clean_text for d in documents})
        if independent < 10:
            messages.append(f'Small historical corpus: {independent} independent documents; chunks are not independent samples.')
        if not negatives:
            messages.append('No negative corpus: using reference similarity and positive-only validation.')
        genre_counts = dict(sorted((genre, sum(d.metadata['genre'] == genre for d in documents))
                                  for genre in {d.metadata['genre'] for d in documents}))
        if len(genre_counts) > 1:
            messages.append('Mixed positive genres: all sources share one positive class with equal document weight; source reports are diagnostics, and topic/length can confound results.')
        short_emails = sum(d.metadata['genre'].endswith('_email') and word_count(d.clean_text) < 150 for d in documents)
        if short_emails:
            messages.append(f'{short_emails} short work emails or Gmail documents have fewer than 150 usable words; extra documents do not make their individual evidence strong.')
        independent_negatives = len({d.clean_text for d in negatives})
        if negatives and independent_negatives < independent:
            messages.append(f'Negative corpus has {independent_negatives} independent documents versus {independent} positives; add more real negative documents.')
        manifest = {'negative_corpus_hashes': negative_hashes, 'negative_corpus_policy': NEGATIVE_CORPUS_POLICY, 'package_version': VERSION, 'feature_schema_version': FEATURE_SCHEMA_VERSION,
                    'preprocessing_version': PREPROCESSING_VERSION, 'encoding_version': ENCODING_VERSION,
                    'model_id': config.model_id, 'model_revision': config.model_revision,
                    'configuration': asdict(config), 'random_seed': config.seed,
                    'build_timestamp': datetime.now(timezone.utc).isoformat(),
                    'build_mode': build_mode, 'sealed_holdout_ids': sorted(sealed_ids),
                    'view_generation_version': 'paragraph-views-v1',
                    'view_size_configuration': {'minimum': 300, 'preferred_min': 350, 'preferred_max': 600, 'maximum': 700, 'max_views': 6},
                    'corpus_hashes': {d.source_file: d.file_hash for d in all_docs},
                    'negative_source_directory': str(negative_root.resolve()) if negatives else None,
                    'source_directory': str(Path(corpus_dir).resolve()), 'mode': 'reference_similarity',
                    'work_source_directory': str(work_root.resolve()) if 'work_email' in genre_counts else None,
                    'gmail_source_directory': str(gmail_root.resolve()) if 'gmail_email' in genre_counts else None,
                    'positive_corpus_counts': genre_counts,
                    'positive_training_policy': 'single positive class; equal document weight across sources',
                    'dataset_counts': {'positive_documents': len(documents), 'independent_positives': independent,
                                       'negative_documents': len(negatives), 'independent_negatives': independent_negatives},
                    'historical_document_ids': [d.document_id for d in documents],
                    'primary_positive_test_ids': [d.document_id for d in primary_tests],
                    'primary_positive_test_documents': [asdict(d) for d in primary_tests],
                    'primary_positive_test_directory': str(primary_root.resolve()) if primary_tests else None,
                    'primary_positive_test_hashes': {d.source_file: d.file_hash for d in primary_tests},
                    'holdout_split': holdout_split,
                    'holdout_documents': [asdict(d) for d in holdout_documents],
                    'documents': [asdict(d) for d in all_docs], 'warnings': messages,
                    'embedding_cache': {'reused': sum(k not in missing for k in keys), 'computed': len(missing)}}
        if primary_tests:
            manifest['dataset_counts'].update({'primary_positive_test_documents': len(primary_tests),
                                               'total_positive_documents': len(documents) + len(primary_tests)})
        if holdout_split:
            manifest['dataset_counts'].update({'holdout_positive_documents': sum(document_label(d) for d in holdout_documents),
                                               'holdout_negative_documents': sum(not document_label(d) for d in holdout_documents),
                                               'total_positive_documents': len(documents) + sum(document_label(d) for d in holdout_documents)})
        fp = cls(all_docs, passages, embeddings, config, manifest)
        fp.encoder = encoder
        if build_mode == 'production':
            fp.evaluation = frozen_evaluation
            fp.manifest['evaluation_configuration'] = frozen
            fp.manifest['evaluation_timestamp'] = frozen['evaluation_timestamp']
            fp.manifest['evaluation_dataset_counts'] = frozen.get('evaluation_dataset_counts', {})
            fp.manifest['production_build_timestamp'] = datetime.now(timezone.utc).isoformat()
            fp._production_refit(frozen)
        else:
            fp.evaluation = fp._evaluate_reference()
            fp._build_supervised(negatives)
            primary_report = fp._evaluate_primary_positive_tests()
            if primary_report is not None:
                fp.evaluation['primary_positive_tests'] = primary_report
            if holdout_split:
                fp.evaluation['holdout'] = fp._evaluate_holdout()
            fp._freeze_configuration()
        for message in fp.manifest['warnings']:
            warnings.warn(message, UserWarning, stacklevel=2)
        fp._save(artifact_dir)
        return fp

    def _build_supervised(self, negatives):
        from .evaluation import run_supervised
        return run_supervised(self, negatives)

    def _group_splits(self, docs, positive_ids):
        from .evaluation import group_splits
        return group_splits(self, docs, positive_ids)

    def _freeze_configuration(self):
        stamp = datetime.now(timezone.utc).isoformat()
        self.manifest['evaluation_timestamp'] = stamp
        thresholds = self.evaluation.get('thresholds', {})
        frozen = {'negative_corpus_hashes': self.manifest['negative_corpus_hashes'], 'negative_corpus_policy': NEGATIVE_CORPUS_POLICY, 'selected_model': self.verifier['kind'] if self.verifier else 'reference_similarity',
                  'feature_schema_version': FEATURE_SCHEMA_VERSION,
                  'character_features_enabled': bool(self.verifier and 'char_ngram' in self.verifier['feature_names']),
                  'selected_feature_schema': self.verifier['feature_names'] if self.verifier else [],
                  'view_generation_version': self.manifest['view_generation_version'],
                  'segmentation': self.manifest['view_size_configuration'],
                  'random_seed': self.config.seed, 'encoder_revision': self.config.model_revision,
                  'encoder_model': self.config.model_id, 'configuration': asdict(self.config),
                  'calibration_method': 'root-oof-logistic' if self.verifier else 'reference_similarity',
                  'match_threshold': thresholds.get('match_threshold'),
                  'mismatch_threshold': thresholds.get('mismatch_threshold'),
                  'evaluation_timestamp': stamp, 'holdout_split': self.manifest.get('holdout_split'),
                  'sealed_holdout_ids': self.manifest.get('sealed_holdout_ids', []),
                  'evaluation_dataset_counts': dict(self.manifest['dataset_counts'])}
        if self.verifier:
            frozen['selected_configuration'] = self.verifier.get('selected_configuration', 'contrast')
            frozen['hard_negative_authors'] = self.verifier.get('hard_negative_authors', [])
            cal = self.verifier['calibrator']
            frozen['calibration_coefficients'] = cal.coef_.tolist()
            frozen['calibration_intercept'] = cal.intercept_.tolist()
        self.manifest['evaluation_configuration'] = frozen
        self.manifest['evaluation_dataset_counts'] = dict(self.manifest['dataset_counts'])
        self.manifest['model_type'] = frozen['selected_model']
        self.manifest['calibration_type'] = frozen['calibration_method']
        self.manifest.update({key: frozen[key] for key in ['match_threshold', 'mismatch_threshold']})

    def _production_refit(self, frozen):
        from .corpus import generate_training_views
        from .evaluation import _fit_comparison_estimator, negative_eligibility
        self.manifest['model_type'] = frozen['selected_model']
        self.manifest['calibration_type'] = frozen['calibration_method']
        self.manifest.update({key: frozen[key] for key in ['match_threshold', 'mismatch_threshold']})
        if frozen['selected_model'] == 'reference_similarity':
            return
        positive_ids = set(self.manifest['historical_document_ids'])
        roots = list({d.clean_text:d for d in self.documents}.values())
        if not negative_eligibility([d.root_document_id for d in roots], [int(d.root_document_id in positive_ids) for d in roots], [d.author_id for d in roots]):
            raise ValueError('Production negative corpus no longer meets supervised eligibility; run evaluation again')
        from sklearn.linear_model import LogisticRegression
        views = [view for doc in self.documents for view in generate_training_views(doc, seed=self.config.seed)]
        positive_ids = set(self.manifest['historical_document_ids'])
        x, all_names = self._comparison_rows(views, sorted(positive_ids))
        names = frozen['selected_feature_schema']
        if frozen.get('character_features_enabled', 'char_ngram' in names) != ('char_ngram' in names):
            raise ValueError('Frozen character decision differs from frozen feature schema')
        if not set(names) <= set(all_names):
            raise ValueError('Frozen feature schema differs from production features')
        x = x[:, [all_names.index(name) for name in names]]
        estimator = _fit_comparison_estimator(frozen['selected_model'], self.config.seed, x, views, positive_ids, hard_negative_authors=frozen.get('hard_negative_authors', []))
        calibrator = LogisticRegression()
        calibrator.classes_ = np.array([0, 1])
        calibrator.coef_ = np.asarray(frozen['calibration_coefficients'])
        calibrator.intercept_ = np.asarray(frozen['calibration_intercept'])
        calibrator.n_features_in_ = 1
        self.verifier = {'kind': frozen['selected_model'], 'estimator': estimator,
                         'calibrator': calibrator, 'feature_names': names,
                         'selected_configuration': frozen.get('selected_configuration', 'contrast'),
                         'hard_negative_authors': frozen.get('hard_negative_authors', [])}
        self.manifest['mode'] = 'supervised'
        self.manifest['dataset_counts']['training_views'] = len(views)

    def _comparison_rows(self, documents, reference_ids, *, negative_reference_ids=None, include_contrast=True, include_character=True):
        rows = []
        names = None
        if negative_reference_ids is None:
            negative_reference_ids = [d.root_document_id for d in self.documents if d.document_id not in self.manifest['historical_document_ids']]
        for doc in documents:
            root = doc.root_document_id
            refs = [i for i in reference_ids if i != root]
            passages = chunk_text(doc.clean_text, doc.document_id, root_document_id=root, author_id=doc.author_id)
            embeddings = self._embed(passages)
            signals, features, scores, reference = self._compare(doc.clean_text, _document_structure(doc), passages, embeddings, refs, [p.text for p in passages])
            vector = self._comparison_features(signals, features, scores, reference, word_count(doc.clean_text), len(passages))
            if include_contrast:
                vector.update(self._negative_contrast(embeddings, negative_reference_ids, signals['authorship_embedding'], excluded_root=root, excluded_author=doc.author_id))
            if not include_character:
                vector.pop('char_ngram', None)
            names = list(vector)
            rows.append(list(vector.values()))
        return np.array(rows), names

    @staticmethod
    def _comparison_features(signals, features, document_scores, reference, words, passages):
        scores = list(document_scores.values())
        vector = dict(signals)
        vector.update({'embedding_mean': float(np.mean(scores)), 'embedding_std': float(np.std(scores)),
                       'embedding_min': min(scores), 'embedding_max': max(scores)})
        vector.update({f'embedding_p{p}': float(np.percentile(scores,p)) for p in [10,25,75,90]})
        vector.update({f"deviation_{d['feature']}": float(np.clip(d['robust_z'], -10, 10)) for d in deviations(features, reference['features'])})
        return vector

    def _negative_contrast(self, embeddings, negative_ids, user_similarity, *, excluded_root=None, excluded_author=None):
        """Compare a candidate to one multi-vector bank per independent negative author."""
        from .corpus import is_eligible_negative
        docs = {d.root_document_id: d for d in self.documents}
        groups = defaultdict(list)
        positive_ids = set(self.manifest['historical_document_ids'])
        for index, passage in enumerate(self.passages):
            root = passage.root_document_id
            doc = docs.get(root)
            if root not in negative_ids or root in positive_ids or root == excluded_root or doc is None:
                continue
            if not is_eligible_negative(doc):
                continue
            author = str(doc.author_id or '').strip().casefold()
            if not author or (excluded_author is not None and author == str(excluded_author).strip().casefold()):
                continue
            groups[author].append(index)
        similarities = [symmetric_maxsim(embeddings, self.embeddings[indices]) for indices in groups.values()]
        best = float(max(similarities)) if similarities else 0.
        median = float(np.median(similarities)) if similarities else 0.
        return {'user_embedding_similarity': float(user_similarity),
                'best_negative_author_similarity': best, 'median_negative_author_similarity': median,
                'user_vs_best_negative_gap': float(user_similarity-best),
                'user_vs_median_negative_gap': float(user_similarity-median)}

    def _supervised_score(self, signals, features, doc_scores, reference, words, passages, contrast=None):
        vector = self._comparison_features(signals, features, doc_scores, reference, words, passages)
        vector.update(contrast or reference.get('negative_contrast', {}))
        x = np.array([[vector[name] for name in self.verifier['feature_names']]])
        estimator, kind = self.verifier['estimator'], self.verifier['kind']
        margin = _margin(estimator, kind, x)
        value = float(self.verifier['calibrator'].predict_proba(margin.reshape(-1,1))[0,1])
        if kind == 'logistic_regression':
            standardized = estimator[0].transform(x)[0]
            contributions = standardized * estimator[-1].coef_[0]
        else:
            # LightGBM's native pred_contrib implements TreeSHAP without a separate SHAP dependency.
            contributions = estimator.predict(x, pred_contrib=True)[0][:-1]
        ordered = sorted(zip(self.verifier['feature_names'], map(float,contributions)), key=lambda p: -abs(p[1]))[:10]
        readable = [{'feature': name, 'label': name.replace('deviation_', 'Deviation in ').replace('_', ' '),
                     'contribution': val} for name,val in ordered]
        return value, float(margin[0]), readable

    def _save(self, directory):
        self.manifest['document_features'] = self._document_features
        directory.mkdir(parents=True, exist_ok=True)
        table = []
        by_id = {d.document_id: d for d in self.documents}
        for p in self.passages:
            row = asdict(p)
            row['embedding_key'] = cache_key(p.text, self.config)
            row['source_file'] = by_id[p.document_id].source_file
            row['stylometry'] = json.dumps(extract_features(p.text))
            row['sentences'] = json.dumps(sentence_spans(p.text))
            table.append(row)
        pd.DataFrame(table).to_parquet(directory / 'passages.parquet', index=False)
        np.save(directory / 'embeddings.npy', self.embeddings, allow_pickle=False)
        ids = self.manifest['historical_document_ids']
        reference = self._reference(ids)
        joblib.dump(reference['vectorizer'], directory / 'vectorizer.joblib')
        if self.verifier is not None:
            joblib.dump(self.verifier, directory / 'verifier.joblib')
        elif (directory / 'verifier.joblib').exists():
            (directory / 'verifier.joblib').unlink()
        if self.manifest.get('build_mode') != 'production':
            predictions = self._prediction_rows()
            self.evaluation['negative_diagnostics'] = [
                {'role': row['split'], 'author_id': row['author_id'], 'root_document_id': row['root_document_id'],
                 'source': row['source'], 'word_count': row['word_count'], 'score': row['compatibility_score'],
                 'raw_margin': row['raw_margin'], 'embedding': row['embedding_score'],
                 'stylometry': row['stylometry_score'], 'character': row['character_score'], 'decision': row['decision'],
                 'source_type': row['source_type'], 'hard_negative': row['hard_negative'],
                 'best_negative_author_similarity': row['best_negative_author_similarity'],
                 'median_negative_author_similarity': row['median_negative_author_similarity'],
                 'user_vs_best_negative_gap': row['user_vs_best_negative_gap']}
                for row in predictions if row['label'] == 0]
            from .report import write_html_report
            write_html_report(self.evaluation, self.manifest, directory / 'report.html')
            (directory / 'evaluation.json').write_text(json.dumps(self.evaluation, indent=2, allow_nan=False))
            pd.DataFrame(predictions).to_parquet(directory / 'evaluation_predictions.parquet', index=False)
        if self.manifest.get('evaluation_configuration'):
            (directory / 'evaluation_config.json').write_text(json.dumps(self.manifest['evaluation_configuration'], indent=2, allow_nan=False))
        self.manifest['artifact_hashes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.name in {'passages.parquet','embeddings.npy','vectorizer.joblib','verifier.joblib','evaluation.json'}}
        (directory / 'manifest.json').write_text(json.dumps(self.manifest, indent=2, allow_nan=False))

    def _prediction_rows(self):
        """Whitelist root diagnostics; never serialize prose into evaluation tables."""
        from .corpus import generate_training_views
        keys = ['root_document_id','author_id','source','label','split','word_count','view_count',
                'embedding_score','stylometry_score','character_score','raw_margin','compatibility_score','score','decision',
                'outer_fold','fold_match_threshold','fold_mismatch_threshold',
                'source_type','user_embedding_similarity','best_negative_author_similarity',
                'median_negative_author_similarity','user_vs_best_negative_gap','user_vs_median_negative_gap','hard_negative']
        rows = [{key: item.get(key) for key in keys} for item in
                self.evaluation.get('supervised', {}).get('nested_outer_scores', [])]
        development = self.evaluation.get('supervised', {}).get('held_out_scores', [])
        if development:
            for item in development:
                row = {key: item.get(key) for key in keys}
                row['score'] = item['compatibility_score']
                rows.append(row)
        else:
            docs = {d.document_id:d for d in self.documents}
            for fold in self.evaluation['folds']:
                doc = docs[fold['candidate_document_id']]
                comp = fold['raw_components']
                rows.append(dict(root_document_id=doc.root_document_id, author_id=doc.author_id,
                                 source=document_source(doc), label=1, split='development_oof',
                                 word_count=word_count(doc.clean_text), view_count=len(generate_training_views(doc, seed=self.config.seed)),
                                 embedding_score=comp['authorship_embedding']*100, stylometry_score=comp['stylometry']*100,
                                 character_score=comp['char_ngram']*100, raw_margin=fold['score']/100,
                                 compatibility_score=fold['score'], score=fold['score'], decision='INCONCLUSIVE_OR_MISMATCH'))
            for doc in self.documents:
                if document_label(doc):
                    continue
                result = self.score(doc.clean_text if doc.source_type == 'email' else doc.raw_markdown, explain=False,
                                    input_format='email' if doc.source_type == 'email' else 'markdown')
                comp = result.diagnostics['raw_components']
                rows.append(dict(root_document_id=doc.root_document_id, author_id=doc.author_id,
                                 source=document_source(doc), label=0, split='development_oof',
                                 word_count=result.word_count, view_count=len(generate_training_views(doc, seed=self.config.seed)),
                                 embedding_score=comp['authorship_embedding']*100, stylometry_score=comp['stylometry']*100,
                                 character_score=comp['char_ngram']*100, raw_margin=result.raw_score,
                                 compatibility_score=result.score, score=result.score, decision=result.decision))
        held_docs = {d['document_id']:Document(**d) for d in self.manifest.get('holdout_documents', [])}
        for item in self.evaluation.get('holdout', {}).get('documents', []):
            doc = held_docs[item['document_id']]
            comp = item['raw_component_scores']
            rows.append(dict(root_document_id=doc.root_document_id, author_id=doc.author_id,
                             source=item['source'], label=item['label'], split='historical_holdout',
                             word_count=item['usable_words'], view_count=len(generate_training_views(doc, seed=self.config.seed)),
                             embedding_score=comp['authorship_embedding']*100, stylometry_score=comp['stylometry']*100,
                             character_score=comp['char_ngram']*100, raw_margin=item['raw_margin'],
                             compatibility_score=item['score'], score=item['score'], decision=item['decision']))
        # Preserve source-root inventory while duplicates share one independent OOF observation.
        if development:
            by_root = {row['root_document_id']: row for row in rows if row['split'] != 'nested_outer'}
            docs_by_root = {doc.root_document_id: doc for doc in self.documents}
            by_prose = {docs_by_root[root].clean_text: row for root, row in by_root.items() if root in docs_by_root}
            for doc in self.documents:
                if doc.root_document_id in by_root or doc.clean_text not in by_prose:
                    continue
                row = dict(by_prose[doc.clean_text], root_document_id=doc.root_document_id,
                           author_id=doc.author_id, source=document_source(doc),
                           word_count=word_count(doc.clean_text),
                           view_count=len(generate_training_views(doc, seed=self.config.seed)))
                rows.append(row)
        all_docs = {d.root_document_id: d for d in self.documents}
        all_docs.update({d.root_document_id: d for d in held_docs.values()})
        for row in rows:
            row['split'] = {'development': 'development_oof', 'holdout': 'historical_holdout'}.get(row['split'], row['split'])
            row.setdefault('hard_negative', False)
            doc = all_docs.get(row['root_document_id'])
            row['source_type'] = getattr(doc, 'source_type', None)
            if row['split'] == 'nested_outer':
                row['score'] = row['compatibility_score']
                continue
            if doc is not None and row.get('best_negative_author_similarity') is None:
                passages = chunk_text(doc.clean_text, doc.document_id)
                negative_ids = [d.root_document_id for d in self.documents if not document_label(d)]
                row.update(self._negative_contrast(self._embed(passages), negative_ids, row['embedding_score']/100, excluded_root=doc.root_document_id, excluded_author=doc.author_id))
        return [{key:row.get(key) for key in keys} for row in rows]

    @classmethod
    def load(cls, artifact_dir='artifacts'):
        directory = Path(artifact_dir)
        try:
            manifest = json.loads((directory / 'manifest.json').read_text())
            if (manifest.get('negative_corpus_policy') != NEGATIVE_CORPUS_POLICY
                    or manifest['feature_schema_version'] != FEATURE_SCHEMA_VERSION
                    or manifest['package_version'] != VERSION
                    or manifest['preprocessing_version'] != PREPROCESSING_VERSION
                    or manifest['encoding_version'] != ENCODING_VERSION):
                raise ValueError('Saved fingerprint schema is incompatible; rebuild the fingerprint.')
            for name, expected in manifest.get('artifact_hashes', {}).items():
                if name not in {'passages.parquet','embeddings.npy','vectorizer.joblib','verifier.joblib','evaluation.json'} or hashlib.sha256((directory/name).read_bytes()).hexdigest() != expected:
                    raise ValueError('Saved fingerprint artifact is corrupt or incompatible; rebuild.')
            config = Config(**manifest['configuration'])
            if config.model_id != manifest['model_id'] or config.model_revision != manifest['model_revision']:
                raise ValueError('Saved model identity is incompatible; rebuild.')
            documents = [Document(**d) for d in manifest['documents']]
            frame = pd.read_parquet(directory / 'passages.parquet')
            passages = [Passage(**{k: row[k] for k in Passage.__dataclass_fields__}) for row in frame.to_dict('records')]
            embeddings = np.load(directory / 'embeddings.npy', allow_pickle=False)
            if embeddings.ndim != 2 or len(embeddings) != len(passages) or not np.isfinite(embeddings).all():
                raise ValueError('Saved embeddings are incompatible or corrupt; rebuild.')
            if list(frame['embedding_key']) != [cache_key(p.text, config) for p in passages]:
                raise ValueError('Saved passage cache identity is incompatible; rebuild.')
            evaluation = json.loads((directory / 'evaluation.json').read_text())
            verifier = joblib.load(directory / 'verifier.joblib') if manifest['mode'] == 'supervised' else None
            fp = cls(documents, passages, embeddings, config, manifest, evaluation, verifier)
            # Reconstruct cheap reference matrices from stored text, reusing the persisted vocabulary.
            reference = fp._reference(manifest['historical_document_ids'], vectorizer=joblib.load(directory / 'vectorizer.joblib'))
            fp._reference_cache[(tuple(sorted(manifest['historical_document_ids'])), ())] = reference
            return fp
        except FileNotFoundError as exc:
            raise ValueError(f'Fingerprint artifacts missing in {directory}; run build first.') from exc
        except (KeyError, TypeError) as exc:
            raise ValueError('Saved fingerprint manifest is incompatible; rebuild.') from exc

    def _reference(self, ids, excluded_texts=(), vectorizer=None):
        key = (tuple(sorted(ids)), tuple(sorted(set(excluded_texts))))
        if key in self._reference_cache and vectorizer is None:
            return self._reference_cache[key]
        excluded_paragraphs = {part.strip() for text in excluded_texts for part in text.split('\n\n') if word_count(part) >= 20}
        indices = [i for i, p in enumerate(self.passages) if p.document_id in ids and p.text not in excluded_texts
                   and not any(part.strip() in excluded_paragraphs for part in p.text.split('\n\n'))]
        if not indices:
            raise ValueError('No independent reference passages remain after excluding held-out/duplicated text.')
        texts = [self.passages[i].text for i in indices]
        vec = vectorizer or TfidfVectorizer(analyzer='char', ngram_range=(3,5), sublinear_tf=True, max_features=50000)
        char_matrix = vec.transform(texts) if vectorizer is not None else vec.fit_transform(texts)
        grouped = defaultdict(list)
        for local, global_index in enumerate(indices):
            grouped[self.passages[global_index].document_id].append(local)
        docs = {d.document_id: d for d in self.documents}
        features = []
        for doc_id, locals_ in grouped.items():
            retained = '\n\n'.join(texts[i] for i in locals_)
            full_count = sum(p.document_id == doc_id for p in self.passages)
            features.append(self._document_features[doc_id] if len(locals_) == full_count else extract_features(retained))
        result = {'indices': indices, 'embeddings': self.embeddings[indices], 'vectorizer': vec,
                  'char_matrix': char_matrix, 'groups': dict(grouped), 'features': features}
        # Nested holdouts create O(n²) vocabularies; keep memory bounded.
        if key not in self._reference_cache and len(self._reference_cache) >= 32:
            self._reference_cache.pop(next(iter(self._reference_cache)))
        self._reference_cache[key] = result
        return result

    def _embed(self, passages):
        missing = {cache_key(p.text, self.config): p.text for p in passages if cache_key(p.text, self.config) not in self._embedding_cache}
        if missing:
            self._embedding_cache.update(zip(missing, self.encoder.encode(list(missing.values()))))
        return np.array([self._embedding_cache[cache_key(p.text, self.config)] for p in passages])

    def _compare(self, text, raw, passages, embeddings, ids, excluded_texts=()):
        reference = self._reference(ids, excluded_texts)
        document_scores = {doc: symmetric_maxsim(embeddings, reference['embeddings'][indices])
                           for doc, indices in reference['groups'].items()}
        char = cosine_similarity(reference['vectorizer'].transform([p.text for p in passages]), reference['char_matrix'])
        char_scores = [float((char[:,i].max(axis=1).mean() + char[:,i].max(axis=0).mean()) / 2)
                       for i in reference['groups'].values()]
        features = extract_features(text, raw)
        signals = {'authorship_embedding': float(np.median(list(document_scores.values()))),
                   'stylometry': stylometry_similarity(features, reference['features']),
                   'char_ngram': float(np.median(char_scores))}
        negative_ids = [d.root_document_id for d in self.documents if d.document_id not in self.manifest['historical_document_ids']]
        reference = dict(reference, negative_contrast=self._negative_contrast(embeddings, negative_ids, signals['authorship_embedding']))
        return signals, features, document_scores, reference

    def _calibration(self, ids):
        values = {key: [] for key in WEIGHTS}
        folds = []
        docs = {d.document_id: d for d in self.documents}
        for doc_id in ids:
            ref_ids = [i for i in ids if i != doc_id]
            if not ref_ids:
                continue
            candidate_indices = [i for i,p in enumerate(self.passages) if p.document_id == doc_id]
            passages = [self.passages[i] for i in candidate_indices]
            excluded = [p.text for p in passages]
            try:
                signals, _, _, ref = self._compare(docs[doc_id].clean_text, _document_structure(docs[doc_id]),
                                                  passages, self.embeddings[candidate_indices], ref_ids, excluded)
            except ValueError:
                continue
            for key in values:
                values[key].append(signals[key])
            folds.append({'candidate_document_id': doc_id, 'reference_document_ids': list(ref['groups']),
                          'statistics_document_ids': list(ref['groups']),
                          'genre': (docs[doc_id].metadata or {}).get('genre', 'unknown'),
                          'source_file': docs[doc_id].source_file,
                          'usable_words': word_count(docs[doc_id].clean_text),
                          'duplicate_passages_removed': sum(p.document_id in ref_ids for p in self.passages) - len(ref['indices']),
                          'raw_components': signals})
        return values, folds

    def _evaluate_reference(self):
        ids = self.manifest['historical_document_ids']
        calibration, folds = self._calibration(ids)
        for fold in folds:
            # Outer candidate is absent from all reference statistics, vocabulary, and normalization folds.
            local_calibration, _ = self._calibration(fold['reference_document_ids'])
            normalized = {k: normalize_similarity(v, local_calibration[k]) for k,v in fold['raw_components'].items()}
            fold['normalization_document_ids'] = fold['reference_document_ids']
            fold['component_scores'] = normalized
            fold['score'] = 100 * sum(WEIGHTS[k] * normalized[k] for k in WEIGHTS)
        scores = [f['score'] for f in folds]
        ablations = {key: [100*f['component_scores'][key] for f in folds] for key in WEIGHTS}
        ablations['embedding_stylometry'] = [100*(.60*f['component_scores']['authorship_embedding'] + .25*f['component_scores']['stylometry'])/.85 for f in folds]
        ablations['ensemble'] = scores
        result = {'mode': self.manifest['mode'], 'folds': folds, 'calibration': calibration,
                  'score_variance': float(np.var(scores)) if scores else 0.,
                  'minimum_held_out_compatibility': min(scores) if scores else None,
                  'mean_held_out_compatibility': float(np.mean(scores)) if scores else None,
                  'component_agreement': [float(np.ptp(list(f['component_scores'].values()))) for f in folds],
                  'ablations': ablations,
                  'positive_genres': {genre: {'documents': len(indices),
                                             'mean_compatibility': float(np.mean([scores[i] for i in indices]))}
                                      for genre, indices in _fold_genre_indices(folds).items()},
                  'limitations': ['Positive-only validation measures consistency, not discrimination or authorship.',
                                 'Each fold excludes the held-out document from vocabulary, statistics, and normalization.']}
        if self.evaluation.get('supervised'):
            result['supervised'] = self.evaluation['supervised']
        return result

    def evaluate(self):
        if self.manifest.get('build_mode') == 'production':
            raise ValueError('Run the evaluate CLI command to evaluate development inputs separately from the production fingerprint')
        self.evaluation = self._evaluate_reference()
        if self.verifier is not None:
            negatives = [d for d in self.documents if d.document_id not in self.manifest['historical_document_ids']]
            self._build_supervised(negatives)
        primary_report = self._evaluate_primary_positive_tests()
        if primary_report is not None:
            self.evaluation['primary_positive_tests'] = primary_report
        if self.manifest.get('holdout_split'):
            self.evaluation['holdout'] = self._evaluate_holdout()
        self.manifest['warnings'] = list(dict.fromkeys(self.manifest['warnings']))
        self._freeze_configuration()
        return self.evaluation

    def _evaluate_holdout(self):
        docs = [Document(**row) for row in self.manifest.get('holdout_documents', [])]
        rows = []
        for doc in docs:
            result = self.score(doc.clean_text if doc.source_type == 'email' else doc.raw_markdown, explain=False,
                                input_format='email' if doc.source_type == 'email' or document_source(doc) in {'work_corpus','gmail_corpus'} else 'markdown')
            rows.append({'document_id': doc.document_id, 'source': document_source(doc),
                         'label': document_label(doc), 'score': result.score,
                         'evidence_strength': result.evidence_strength, 'usable_words': result.word_count,
                         'decision': result.decision, 'raw_margin': result.raw_score,
                         'author_id': doc.author_id, 'root_document_id': doc.root_document_id,
                         'component_scores': result.component_scores,
                         'raw_component_scores': result.diagnostics['raw_components'],
                         'negative_contrast': result.diagnostics['negative_contrast']})
            if not document_label(doc):
                self.evaluation.setdefault('negative_diagnostics', [])
                diagnostic = {'role': 'holdout', 'author_id': doc.author_id, 'root_document_id': doc.root_document_id,
                              'source': document_source(doc), 'word_count': result.word_count, 'score': result.score,
                              'raw_margin': result.raw_score, 'decision': result.decision,
                              'embedding': result.diagnostics['raw_components']['authorship_embedding']*100,
                              'stylometry': result.diagnostics['raw_components']['stylometry']*100, 'character': result.diagnostics['raw_components']['char_ngram']*100}
                old = self.evaluation['negative_diagnostics']
                self.evaluation['negative_diagnostics'] = [r for r in old if not (r['root_document_id'] == doc.root_document_id and r['role'] == 'holdout')] + [diagnostic]
        def summarize(items):
            threshold = self.manifest.get('match_threshold')
            labels = [r['label'] for r in items]
            scores = [r['score']/100 for r in items]
            if threshold is None:
                metrics = {'accuracy': None, 'true_positive_rate': None, 'false_positive_rate': None,
                           'match_threshold': None, 'mismatch_threshold': None, 'inconclusive_rate': 1.,
                           'confusion_matrix': {key: None for key in ['true_positive','true_negative','false_positive','false_negative']}}
                if len(set(labels)) == 2:
                    metrics.update(_classification_metrics(labels, scores))
            else:
                mismatch = self.manifest.get('mismatch_threshold')
                metrics = performance_report(labels, scores, threshold=threshold/100,
                                             mismatch_threshold=mismatch/100 if mismatch is not None else None)
            return {'count': len(items), 'metrics': metrics}
        return dict(summarize(rows), documents=rows,
                    by_source={src: summarize([r for r in rows if r['source']==src]) for src in sorted({r['source'] for r in rows})},
                    threshold=self.manifest.get('match_threshold'), threshold_policy='Frozen grouped development OOF threshold',
                    limitations=['Previously exposed project documents; prospective holdout, not historically untouched.',
                                 'Small source subsets and genre/topic confounding limit generalization.'])

    def _evaluate_primary_positive_tests(self):
        """Score sealed positive documents only after development/model selection."""
        tests = [Document(**row) for row in self.manifest.get('primary_positive_test_documents', [])]
        if not tests:
            return None
        rows = []
        for doc in tests:
            result = self.score(doc.raw_markdown, explain=False)
            rows.append({'document_id': doc.document_id, 'source_file': doc.source_file,
                         'file_hash': doc.file_hash, 'title': (doc.metadata or {}).get('title'),
                         'score': result.score, 'evidence_strength': result.evidence_strength,
                         'usable_words': result.word_count, 'decision': result.decision,
                         'component_scores': result.component_scores})
        accepted = sum(row['decision'] == 'MATCH' for row in rows)
        return {'count': len(rows), 'positive_only': True,
                'selected_model': self.verifier['kind'] if self.verifier is not None else 'reference_similarity',
                'threshold': self.manifest.get('match_threshold'), 'threshold_policy': 'Frozen grouped development OOF threshold',
                'accepted_at_match_threshold': accepted, 'acceptance_rate_at_match_threshold': accepted / len(rows),
                'mean_compatibility': float(np.mean([row['score'] for row in rows])),
                'documents': rows, 'reference_document_ids': self.manifest['historical_document_ids'],
                'development_document_ids': [d.document_id for d in self.documents],
                'limitations': ['Only positives are reserved: no independent false-positive rate, AUROC, or full accuracy estimate.',
                                'Do not use these test results for model selection, calibration, thresholds, or parameter tuning.']}

    def score(self, text, *, explain=True, input_format='markdown', _raw_structure=None):
        if input_format not in {'markdown', 'email', 'plain'}:
            raise ValueError('Input format must be markdown, email, or plain.')
        clean = text if input_format == 'plain' else clean_email(text) if input_format == 'email' else clean_markdown(text)
        structure = _raw_structure if _raw_structure is not None else (clean if input_format == 'email' else text)
        if word_count(clean) < 3:
            raise ValueError('Scoring input has insufficient usable prose (at least three words required).')
        passages = chunk_text(clean, 'candidate')
        embeddings = self._embed(passages)
        signals, features, doc_scores, ref = self._compare(clean, structure, passages, embeddings, self.manifest['historical_document_ids'])
        components = {k: normalize_similarity(v, self.evaluation['calibration'][k]) for k,v in signals.items()}
        ensemble = sum(WEIGHTS[k]*components[k] for k in WEIGHTS)
        result = StyleScore(100*ensemble, ensemble, evidence_strength(word_count(clean), list(components.values())),
                            word_count(clean), {**components, 'character': components['char_ngram'], 'ensemble': ensemble})
        attribution = None
        if self.verifier is not None:
            from .corpus import make_training_views
            view_margins = []
            view_components = []
            view_contributions = []
            for view in make_training_views(clean, 'candidate', seed=self.config.seed):
                vp = chunk_text(view.clean_text, view.document_id, root_document_id='candidate')
                vs, vf, vd, vr = self._compare(view.clean_text, view.clean_text, vp, self._embed(vp), self.manifest['historical_document_ids'])
                _, vm, va = self._supervised_score(vs, vf, vd, vr, word_count(view.clean_text), len(vp))
                view_margins.append(vm)
                view_components.append(vs)
                view_contributions.append(va)
            signals = {key: float(np.median([vs[key] for vs in view_components])) for key in WEIGHTS}
            margin = float(np.median(view_margins))
            calibrated = float(self.verifier['calibrator'].predict_proba(np.array([[margin]]))[0, 1])
            attribution = view_contributions[int(np.argmin(abs(np.asarray(view_margins) - margin)))]
            result.score = 100*calibrated
            result.raw_score = margin
            result.component_scores['ensemble'] = calibrated
        from .evaluation import decision_for_score
        result.match_threshold = self.manifest.get('match_threshold')
        result.mismatch_threshold = self.manifest.get('mismatch_threshold')
        result.decision = decision_for_score(result.score, result.match_threshold, result.mismatch_threshold) if result.match_threshold is not None else 'INCONCLUSIVE_OR_MISMATCH'
        result.feature_deviations = deviations(features, ref['features'])
        result.best_matching_documents = [{'document_id': d, 'similarity': v} for d,v in sorted(doc_scores.items(), key=lambda item: -item[1])]
        notices = list(self.manifest['warnings'])
        if result.word_count < 150:
            notices.append('Short text: fewer than 150 usable words gives low evidence strength.')
        if np.ptp(list(components.values())) >= .65:
            notices.append('Extreme component disagreement: evidence strength downgraded one level; topic/genre may affect similarities.')
        result.diagnostics = {'mode': self.manifest['mode'], 'input_format': input_format, 'warnings': notices, 'raw_components': signals,
                              'negative_contrast': ref['negative_contrast'],
                              'passage_count': len(passages), 'sentence_deletions_evaluated': 0,
                              'contributions': {k: 100*WEIGHTS[k]*components[k] for k in WEIGHTS}}
        if attribution is not None:
            result.diagnostics['view_margin_summary'] = {key: float(value) for key, value in zip(['minimum','p25','median','p75','maximum','variance'], [min(view_margins),np.percentile(view_margins,25),margin,np.percentile(view_margins,75),max(view_margins),np.var(view_margins)])}
            result.diagnostics['contributions'] = attribution
            result.diagnostics['contribution_units'] = 'Uncalibrated verifier margin (signed standardized coefficients or TreeSHAP).'
        from .explain import add_analogues
        add_analogues(self, result, passages, embeddings, ref)
        if explain:
            from .explain import add_explanations
            add_explanations(self, result, clean, passages, embeddings, ref, structure)
        return result


# Compatibility imports for the existing public Python API.
from .evaluation import choose_verifier, _classification_metrics, _estimator, _margin, _author_key, _fit_comparison_estimator, fit_calibrator, performance_report
