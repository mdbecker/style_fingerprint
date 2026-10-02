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
from .corpus import Document, Passage, load_corpus, load_work_corpus, load_email_corpus, clean_email, clean_markdown, chunk_text, word_count, sentence_spans
from .embeddings import AuthorshipEncoder, cache_key, cosine_matrix, symmetric_maxsim
from .holdout import split_holdout, source as document_source, label as document_label
from .features import extract_features, stylometry_similarity, deviations, normalize_similarity, evidence_strength


def _document_structure(document):
    return document.clean_text if (document.metadata or {}).get('genre', '').endswith('_email') else document.raw_markdown


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
    def build(cls, corpus_dir='blog_posts', artifact_dir='artifacts', *, config=None, negative_dir=None, work_dir=None, gmail_dir=None, primary_test_dir=None, holdout_fraction=.2):
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
        negatives = load_corpus(negative_root) if negative_root.exists() and any(p.suffix.lower() in {'.md','.markdown','.mdown'} for p in negative_root.rglob('*')) else []
        for d in negatives:
            d.document_id = 'negative/' + d.document_id
            d.metadata = dict(d.metadata or {}, genre='negative_posts')
        holdout_documents = []
        holdout_split = None
        if holdout_fraction:
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
            doc.metadata = dict(doc.metadata or {}, genre='blog', role='primary_positive_test')
        _reject_primary_overlap(all_docs, primary_tests)
        passages = [p for d in all_docs for p in chunk_text(d.clean_text, d.document_id)]
        artifact_dir = Path(artifact_dir)
        old_cache = {}
        if (artifact_dir / 'manifest.json').exists():
            try:
                old = cls.load(artifact_dir)
                old_cache = old._embedding_cache
            except (ValueError, OSError, KeyError):
                pass  # An incompatible artifact is rebuilt, never used for scoring.
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
        manifest = {'package_version': VERSION, 'feature_schema_version': FEATURE_SCHEMA_VERSION,
                    'preprocessing_version': PREPROCESSING_VERSION, 'encoding_version': ENCODING_VERSION,
                    'model_id': config.model_id, 'model_revision': config.model_revision,
                    'configuration': asdict(config), 'random_seed': config.seed,
                    'build_timestamp': datetime.now(timezone.utc).isoformat(),
                    'corpus_hashes': {d.source_file: d.file_hash for d in all_docs},
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
        fp.evaluation = fp._evaluate_reference()
        # Supervised mode is attached only when independent negative data meets the threshold.
        fp._build_supervised(negatives)
        primary_report = fp._evaluate_primary_positive_tests()
        if primary_report is not None:
            fp.evaluation['primary_positive_tests'] = primary_report
        if holdout_split:
            fp.evaluation['holdout'] = fp._evaluate_holdout()
        for message in fp.manifest['warnings']:
            warnings.warn(message, UserWarning, stacklevel=2)
        fp._save(artifact_dir)
        return fp

    def _build_supervised(self, negatives):
        unique = {d.clean_text: d for d in negatives}
        negative_docs = list(unique.values())
        known_authors = {_author_key(d) for d in negative_docs if _author_key(d)}
        adequate = len(negative_docs) >= 10
        positives = [d for d in self.documents if d.document_id in self.manifest['historical_document_ids']]
        positives = list({d.clean_text: d for d in positives}.values())
        if not adequate or len(positives) < 6:
            if negatives:
                self.manifest['warnings'].append('Supervised mode requires 10 independent negatives and 6 independent positives for nested validation; using reference similarity.')
            return
        self.manifest['negative_grouping'] = 'author' if len(known_authors) >= 3 else 'document'
        if len(known_authors) < 3:
            self.manifest['warnings'].append('Few known negative authors: using document holdouts; results do not establish generalization to unseen authors.')
        author_counts = {_author_key(d): sum(_author_key(other) == _author_key(d) for other in negative_docs) for d in negative_docs if _author_key(d)}
        if author_counts and max(author_counts.values()) > len(negative_docs) / 2:
            self.manifest['warnings'].append('One author dominates the negative corpus; overall metrics may hide poor generalization to other authors. Inspect per-author held-out results.')
        from sklearn.linear_model import LogisticRegression
        docs = positives + negative_docs
        positive_ids = {d.document_id for d in positives}
        kinds = ['logistic_regression']
        try:
            import lightgbm
            kinds.append('lightgbm')
        except (ImportError, OSError):
            self.manifest['warnings'].append('LightGBM unavailable; install the supervised extra and its native OpenMP runtime to compare it with logistic regression.')
        outer_splits = self._group_splits(docs, positive_ids)
        labels = np.array([int(d.document_id in positive_ids) for d in docs])
        predictions = {kind: np.zeros(len(docs)) for kind in kinds}
        margins = {kind: np.zeros(len(docs)) for kind in kinds}
        folds = []
        nested_predictions = np.zeros(len(docs))
        names = None
        for train, test in outer_splits:
            train_docs = [docs[i] for i in train]
            ref_ids = [d.document_id for d in train_docs if d.document_id in positive_ids]
            x_train, names = self._comparison_rows(train_docs, ref_ids)
            x_test, _ = self._comparison_rows([docs[i] for i in test], ref_ids)
            inner_splits = self._group_splits(train_docs, positive_ids)
            inner_metrics = {}
            for kind in kinds:
                inner_margins = np.zeros(len(train_docs))
                for inner_train, inner_test in inner_splits:
                    inner_docs = [train_docs[i] for i in inner_train]
                    inner_refs = [d.document_id for d in inner_docs if d.document_id in positive_ids]
                    xi, _ = self._comparison_rows(inner_docs, inner_refs)
                    xt, _ = self._comparison_rows([train_docs[i] for i in inner_test], inner_refs)
                    estimator = _fit_comparison_estimator(kind, self.config.seed, xi, inner_docs, positive_ids)
                    inner_margins[inner_test] = _margin(estimator, kind, xt)
                from sklearn.metrics import roc_auc_score
                inner_metrics[kind] = float(roc_auc_score(labels[train], inner_margins))
                calibrator = fit_calibrator(inner_margins, labels[train], self.config.seed,
                                            positive_genres=[(d.metadata or {}).get('genre', 'unknown') for d in train_docs])
                estimator = _fit_comparison_estimator(kind, self.config.seed, x_train, train_docs, positive_ids)
                margins[kind][test] = _margin(estimator, kind, x_test)
                predictions[kind][test] = calibrator.predict_proba(margins[kind][test].reshape(-1,1))[:,1]
            nested_kind = choose_verifier(inner_metrics['logistic_regression'], inner_metrics.get('lightgbm'))
            nested_predictions[test] = predictions[nested_kind][test]
            folds.append({'nested_selected_model': nested_kind,
                          'selection_document_ids': [d.document_id for d in train_docs],
                          'inner_selection_auroc': inner_metrics,
                          'test_document_ids': [docs[i].document_id for i in test],
                          'training_document_ids': [docs[i].document_id for i in train],
                          'training_negative_author_ids': sorted({_author_key(docs[i]) for i in train if not labels[i] and _author_key(docs[i])}),
                          'test_negative_author_ids': sorted({_author_key(docs[i]) for i in test if not labels[i] and _author_key(docs[i])}),
                          'test_positive_ids': [docs[i].document_id for i in test if labels[i]],
                          'reference_document_ids': ref_ids,
                          'calibration_training_ids': [docs[i].document_id for i in train],
                          'inner_folds': [{'training_document_ids': [train_docs[i].document_id for i in itrain],
                                           'test_document_ids': [train_docs[i].document_id for i in itest],
                                           'training_negative_author_ids': sorted({_author_key(train_docs[i]) for i in itrain if train_docs[i].document_id not in positive_ids and _author_key(train_docs[i])}),
                                           'test_negative_author_ids': sorted({_author_key(train_docs[i]) for i in itest if train_docs[i].document_id not in positive_ids and _author_key(train_docs[i])}),
                                           'reference_document_ids': [train_docs[i].document_id for i in itrain if train_docs[i].document_id in positive_ids]}
                                          for itrain,itest in inner_splits]})
        model_metrics = {kind: _classification_metrics(labels, prediction) for kind, prediction in predictions.items()}
        selected = choose_verifier(model_metrics['logistic_regression']['auroc'], model_metrics.get('lightgbm', {}).get('auroc'))
        x, names = self._comparison_rows(docs, list(positive_ids))
        estimator = _fit_comparison_estimator(selected, self.config.seed, x, docs, positive_ids)
        calibrator = fit_calibrator(margins[selected], labels, self.config.seed,
                                    positive_genres=[(d.metadata or {}).get('genre', 'unknown') for d in docs])
        if selected == 'logistic_regression':
            importance = abs(estimator[-1].coef_[0]).tolist()
        else:
            importance = estimator.feature_importances_.astype(float).tolist()
        self.verifier = {'kind': selected, 'estimator': estimator, 'calibrator': calibrator, 'feature_names': names}
        self.manifest['mode'] = 'supervised'
        self.evaluation['mode'] = 'supervised'
        self.evaluation['supervised'] = {'models': model_metrics, 'selected_model': selected,
                                        'nested_selection_metrics': performance_report(labels, nested_predictions),
                                        'training_performance': performance_report(labels, calibrator.predict_proba(_margin(estimator, selected, x).reshape(-1,1))[:,1]),
                                        'cv_method': 'Nested stratified group cross-validation; model choice and calibration restricted to outer training folds',
                                        'calibration_enabled': True, 'calibration_class_prior': 'equal class mass, independent of author/fold sample counts',
                                        'positive_genre_weighting': 'equal document weight across positive sources',
                                        'negative_grouping': self.manifest['negative_grouping'],
                                        'metrics': model_metrics[selected],
                                        'folds': folds, 'selection_margin_auroc': .02,
                                        'feature_importance': dict(zip(names, importance)),
                                        'held_out_scores': [{'document_id': d.document_id, 'label': int(labels[i]), 'score': float(predictions[selected][i]),
                                                             'author': d.author, 'author_id': _author_key(d), 'source_url': (d.metadata or {}).get('source_url'),
                                                             'genre': (d.metadata or {}).get('genre', 'unknown')} for i,d in enumerate(docs)],
                                        'per_positive_genre': {genre: {'documents': len(indices),
                                                                       'mean_compatibility': float(np.mean(predictions[selected][indices]) * 100),
                                                                       'accept_rate_at_50': float(np.mean(predictions[selected][indices] >= .5))}
                                                               for genre, indices in _genre_indices(docs, positive_ids).items()},
                                        'negative_author_counts': {author: sum(_author_key(d) == author for d in negative_docs) for author in sorted(known_authors)},
                                        'per_negative_author': {author: {'documents': sum(_author_key(d) == author for d in negative_docs),
                                                                         'mean_compatibility': float(np.mean([predictions[selected][i] * 100 for i,d in enumerate(docs) if not labels[i] and _author_key(d) == author])),
                                                                         'false_accept_rate_at_50': float(np.mean([predictions[selected][i] >= .5 for i,d in enumerate(docs) if not labels[i] and _author_key(d) == author]))} for author in sorted(known_authors)},
                                        'limitations': ['Model selection and reported metrics share grouped validation; these are exploratory, not an independent final test.',
                                                        'Calibration uses out-of-fold margins, with inner calibration folds restricted to each outer training corpus.']}

    def _group_splits(self, docs, positive_ids):
        from sklearn.model_selection import StratifiedGroupKFold
        labels = [int(d.document_id in positive_ids) for d in docs]
        groups = [d.document_id if d.document_id in positive_ids or not _author_key(d) or self.manifest.get('negative_grouping') == 'document' else 'author:' + _author_key(d) for d in docs]
        if self.manifest.get('holdout_split'):
            mapping = self.manifest['holdout_split']['document_groups']
            groups = [mapping[d.document_id] for d in docs]
        positive_count = sum(labels)
        negative_groups = len({g for g,y in zip(groups, labels) if not y})
        positive_groups = len({g for g,y in zip(groups, labels) if y})
        splits = min(3, positive_groups, negative_groups)
        if splits < 2:
            raise ValueError('Insufficient independent groups for supervised calibration')
        splitter = StratifiedGroupKFold(n_splits=splits, shuffle=True, random_state=self.config.seed)
        result = list(splitter.split(np.zeros(len(docs)), labels, groups))
        if any(len(set(np.asarray(labels)[train])) < 2 or sum(np.asarray(labels)[train]) < 2 for train,_ in result):
            # Two balanced document/author partitions preserve at least two positive reference documents.
            positive = [i for i,y in enumerate(labels) if y]
            ng = sorted({g for g,y in zip(groups,labels) if not y})
            assignment = {g: i % 2 for i,g in enumerate(ng)}
            buckets = [[], []]
            pg = sorted({groups[i] for i in positive})
            pa = {g: i % 2 for i,g in enumerate(pg)}
            for i in positive:
                buckets[pa[groups[i]]].append(i)
            for i,y in enumerate(labels):
                if not y:
                    buckets[assignment[groups[i]]].append(i)
            result = [(np.array(sorted(set(range(len(docs))) - set(test))), np.array(sorted(test))) for test in buckets]
        return result

    def _comparison_rows(self, documents, reference_ids):
        rows = []
        names = None
        for doc in documents:
            refs = [i for i in reference_ids if i != doc.document_id]
            indices = [i for i,p in enumerate(self.passages) if p.document_id == doc.document_id]
            passages = [self.passages[i] for i in indices]
            signals, features, scores, reference = self._compare(doc.clean_text, _document_structure(doc), passages, self.embeddings[indices], refs, [p.text for p in passages])
            vector = self._comparison_features(signals, features, scores, reference, word_count(doc.clean_text), len(passages))
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
        vector.update({'usable_words': float(words), 'candidate_passages': float(passages)})
        vector.update({f"deviation_{d['feature']}": float(np.clip(d['robust_z'], -10, 10)) for d in deviations(features, reference['features'])})
        return vector

    def _supervised_score(self, signals, features, doc_scores, reference, words, passages):
        vector = self._comparison_features(signals, features, doc_scores, reference, words, passages)
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
        from .report import write_html_report
        write_html_report(self.evaluation, self.manifest, directory / 'report.html')
        (directory / 'evaluation.json').write_text(json.dumps(self.evaluation, indent=2, allow_nan=False))
        self.manifest['artifact_hashes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.name in {'passages.parquet','embeddings.npy','vectorizer.joblib','verifier.joblib','evaluation.json'}}
        (directory / 'manifest.json').write_text(json.dumps(self.manifest, indent=2, allow_nan=False))

    @classmethod
    def load(cls, artifact_dir='artifacts'):
        directory = Path(artifact_dir)
        try:
            manifest = json.loads((directory / 'manifest.json').read_text())
            if (manifest['feature_schema_version'] != FEATURE_SCHEMA_VERSION
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
        return self.evaluation

    def _evaluate_holdout(self):
        docs = [Document(**row) for row in self.manifest.get('holdout_documents', [])]
        rows = []
        for doc in docs:
            result = self.score(doc.raw_markdown, explain=False,
                                input_format='email' if document_source(doc) in {'work_corpus','gmail_corpus'} else 'markdown')
            rows.append({'document_id': doc.document_id, 'source': document_source(doc),
                         'label': document_label(doc), 'score': result.score,
                         'evidence_strength': result.evidence_strength, 'usable_words': result.word_count})
        def summarize(items):
            metrics = performance_report([r['label'] for r in items], [r['score']/100 for r in items])
            return {'count': len(items), 'metrics': metrics}
        return dict(summarize(rows), documents=rows,
                    by_source={src: summarize([r for r in rows if r['source']==src]) for src in sorted({r['source'] for r in rows})},
                    threshold=50, threshold_policy='Fixed cutoff; never tuned on holdout',
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
                         'usable_words': result.word_count, 'accepted_at_50': result.score >= 50,
                         'component_scores': result.component_scores})
        accepted = sum(row['accepted_at_50'] for row in rows)
        return {'count': len(rows), 'positive_only': True,
                'selected_model': self.verifier['kind'] if self.verifier is not None else 'reference_similarity',
                'threshold': 50, 'threshold_policy': 'fixed illustrative cutoff; not tuned on primary tests',
                'accepted_at_50': accepted, 'acceptance_rate_at_50': accepted / len(rows),
                'mean_compatibility': float(np.mean([row['score'] for row in rows])),
                'documents': rows, 'reference_document_ids': self.manifest['historical_document_ids'],
                'development_document_ids': [d.document_id for d in self.documents],
                'limitations': ['Only positives are reserved: no independent false-positive rate, AUROC, or full accuracy estimate.',
                                'Do not use these test results for model selection, calibration, thresholds, or parameter tuning.']}

    def score(self, text, *, explain=True, input_format='markdown', _raw_structure=None):
        if input_format not in {'markdown', 'email'}:
            raise ValueError('Input format must be markdown or email.')
        clean = clean_email(text) if input_format == 'email' else clean_markdown(text)
        structure = _raw_structure if _raw_structure is not None else (clean if input_format == 'email' else text)
        if word_count(clean) < 3:
            raise ValueError('Scoring input has insufficient usable prose (at least three words required).')
        passages = chunk_text(clean, 'candidate')
        embeddings = self._embed(passages)
        signals, features, doc_scores, ref = self._compare(clean, structure, passages, embeddings, self.manifest['historical_document_ids'])
        components = {k: normalize_similarity(v, self.evaluation['calibration'][k]) for k,v in signals.items()}
        ensemble = sum(WEIGHTS[k]*components[k] for k in WEIGHTS)
        result = StyleScore(100*ensemble, ensemble, evidence_strength(word_count(clean), list(components.values())),
                            word_count(clean), {**components, 'ensemble': ensemble})
        attribution = None
        if self.verifier is not None:
            calibrated, margin, attribution = self._supervised_score(signals, features, doc_scores, ref, word_count(clean), len(passages))
            result.score = 100*calibrated
            result.raw_score = margin
            result.component_scores['ensemble'] = calibrated
        result.feature_deviations = deviations(features, ref['features'])
        result.best_matching_documents = [{'document_id': d, 'similarity': v} for d,v in sorted(doc_scores.items(), key=lambda item: -item[1])]
        notices = list(self.manifest['warnings'])
        if result.word_count < 150:
            notices.append('Short text: fewer than 150 usable words gives low evidence strength.')
        if np.ptp(list(components.values())) >= .65:
            notices.append('Extreme component disagreement: evidence strength downgraded one level; topic/genre may affect similarities.')
        result.diagnostics = {'mode': self.manifest['mode'], 'input_format': input_format, 'warnings': notices, 'raw_components': signals,
                              'passage_count': len(passages), 'sentence_deletions_evaluated': 0,
                              'contributions': {k: 100*WEIGHTS[k]*components[k] for k in WEIGHTS}}
        if attribution is not None:
            result.diagnostics['contributions'] = attribution
            result.diagnostics['contribution_units'] = 'Uncalibrated verifier margin (signed standardized coefficients or TreeSHAP).'
        from .explain import add_analogues
        add_analogues(self, result, passages, embeddings, ref)
        if explain:
            from .explain import add_explanations
            add_explanations(self, result, clean, passages, embeddings, ref, structure)
        return result


def choose_verifier(logistic_auc, lightgbm_auc):
    return 'lightgbm' if lightgbm_auc is not None and lightgbm_auc - logistic_auc >= .02 - 1e-12 else 'logistic_regression'


def _classification_metrics(labels, scores):
    from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve, brier_score_loss
    labels, scores = np.asarray(labels), np.asarray(scores)
    fpr, tpr, _ = roc_curve(labels, scores)
    eer_index = int(np.argmin(abs(fpr - (1-tpr))))
    ece = 0.
    for low in np.linspace(0, .9, 10):
        mask = (scores >= low) & (scores < low+.1 if low < .9 else scores <= 1)
        if mask.any():
            ece += mask.mean() * abs(labels[mask].mean() - scores[mask].mean())
    return {'auroc': float(roc_auc_score(labels, scores)),
            'average_precision': float(average_precision_score(labels, scores)),
            'eer': float((fpr[eer_index] + 1-tpr[eer_index]) / 2),
            'tpr_at_1pct_fpr': float(max(tpr[fpr <= .01], default=0)),
            'tpr_at_5pct_fpr': float(max(tpr[fpr <= .05], default=0)),
            'brier': float(brier_score_loss(labels, scores)), 'calibration_error': float(ece)}


def _estimator(kind, seed):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    if kind == 'logistic_regression':
        return make_pipeline(StandardScaler(), LogisticRegression(C=.1, max_iter=2000, random_state=seed, class_weight='balanced'))
    from lightgbm import LGBMClassifier
    return LGBMClassifier(n_estimators=50, num_leaves=7, max_depth=3, min_child_samples=2,
                          learning_rate=.05, random_state=seed, n_jobs=1, verbosity=-1, deterministic=True, force_col_wise=True)


def _margin(estimator, kind, x):
    if kind == 'logistic_regression':
        return np.asarray(estimator.decision_function(x))
    return np.asarray(estimator.predict(x, raw_score=True))


def _author_key(document):
    metadata = document.metadata or {}
    return str(metadata.get('author_id') or document.author or '').strip().casefold()


def _fit_comparison_estimator(kind, seed, x, documents, positive_ids):
    labels = [int(d.document_id in positive_ids) for d in documents]
    return _estimator(kind, seed).fit(x, labels)


def fit_calibrator(margins, labels, seed, positive_genres=None):
    from sklearn.linear_model import LogisticRegression
    labels = np.asarray(labels)
    if set(labels) != {0,1}:
        raise ValueError('Calibration needs both positive and negative validation examples')
    weights = np.array([1 / np.sum(labels == y) for y in labels])
    if positive_genres is not None:
        if len(positive_genres) != len(labels):
            raise ValueError('Calibration genre labels must match the example count')
        # Legacy metadata argument is accepted, but sources no longer affect weights.
    return LogisticRegression(C=1, random_state=seed, tol=1e-10, max_iter=2000).fit(np.asarray(margins).reshape(-1,1), labels, sample_weight=weights)


def performance_report(labels, scores):
    labels=np.asarray(labels,dtype=int);scores=np.asarray(scores,dtype=float)
    predicted=scores>=.5
    tp=int(np.sum(predicted & (labels==1)));tn=int(np.sum(~predicted & (labels==0)))
    fp=int(np.sum(predicted & (labels==0)));fn=int(np.sum(~predicted & (labels==1)))
    result={'accuracy':float((tp+tn)/len(labels)) if len(labels) else None,
            'true_positive_rate':tp/(tp+fn) if tp+fn else None,
            'false_positive_rate':fp/(fp+tn) if fp+tn else None,
            'confusion_matrix':{'true_positive':tp,'true_negative':tn,'false_positive':fp,'false_negative':fn}}
    if len(set(labels))==2: result.update(_classification_metrics(labels,scores))
    return result
