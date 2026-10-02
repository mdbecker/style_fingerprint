"""Four local commands: build, score, explain, and evaluate."""
import argparse
import json
from pathlib import Path
import sys
from .config import Config
from .model import StyleFingerprint


def _parser():
    parser = argparse.ArgumentParser(description='Personal historical writing style compatibility (not authorship proof).')
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build', help='Build or rebuild the historical fingerprint')
    build.add_argument('--corpus', default='blog_posts')
    build.add_argument('--negative-corpus', default=None)
    build.add_argument('--primary-positive-tests', default=None, help='Legacy positive-only Markdown tests; requires --no-holdout')
    work = build.add_mutually_exclusive_group()
    work.add_argument('--work-corpus', default=None, help='Positive .txt emails (defaults to sibling work_corpus)')
    work.add_argument('--no-work-corpus', action='store_true', help='Exclude work email positives')
    gmail = build.add_mutually_exclusive_group()
    gmail.add_argument('--gmail-corpus', default=None, help='Positive .txt personal documents (defaults to sibling gmail_corpus)')
    gmail.add_argument('--no-gmail-corpus', action='store_true', help='Exclude Gmail positives')
    build.add_argument('--seed', type=int, default=42, help='Reproducible holdout and cross-validation seed')
    build.add_argument('--holdout-fraction', type=float, default=.2, help='Email/negative holdout fraction; blogs reserve at least 50 percent')
    build.add_argument('--no-holdout', action='store_true', help='Development-only diagnostic; no independent holdout')
    build.add_argument('--device', choices=['auto','cpu','cuda','mps'], default='auto')
    build.add_argument('--offline', action='store_true', help='Require the pinned checkpoint in the local cache')
    for name in ['score','explain']:
        sub = commands.add_parser(name, help='Score candidate prose' if name == 'score' else 'Explain candidate matches and mismatches')
        sub.add_argument('file', nargs='?')
        sub.add_argument('--text', help='Score raw text instead of a file')
        sub.add_argument('--input-format', choices=['markdown', 'email'], default='markdown', help='Use the same email cleaning as the positive work corpus')
    commands.add_parser('evaluate', help='Document-grouped validation of the saved corpus')
    for sub in commands.choices.values():
        sub.add_argument('--artifacts', default='artifacts')
        sub.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    return parser


def _print_score(result, detailed):
    print(f'Style compatibility: {result.score:.1f} / 100')
    print(f'Evidence strength: {result.evidence_strength}')
    print(f'Usable words: {result.word_count}')
    print('Components: ' + ', '.join(f'{k.replace("_", " ")} {100*v:.1f}' for k,v in result.component_scores.items() if k != 'ensemble'))
    if detailed:
        for name, rows in [('Strongest matches', result.strongest_matches), ('Largest mismatches', result.largest_mismatches)]:
            print(f'\n{name}')
            for row in rows:
                print(f'- {row["description"]}')
        print('\nComponent / verifier contributions')
        print(json.dumps(result.diagnostics['contributions'], indent=2))
        print('\nUnusually inconsistent passages')
        for row in result.anomalous_passages:
            passage_score = f'{row["score"]:.1f} / 100' if row['score'] is not None else 'insufficient prose to score individually'
            print(f'- Passage {row["passage_id"]+1}: {passage_score}; closest similarity {row["max_reference_similarity"]:.3f}')
            print(f'  {row["text"][:250]}')
            if row['no_close_analogue']:
                print('  No close historical analogue.')
        print('\nSentence deletion sensitivity')
        for row in result.anomalous_sentences[:5]:
            print(f'- Sentence {row["index"]+1}: removing it changes {row["original_score"]:.1f} → {row["score_without"]:.1f} (+{row["delta"]:.2f})')
            print(f'  {row["sentence"]}')
        print('\nHistorical analogues')
        for row in result.nearest_reference_passages:
            print(f'- Candidate passage {row["candidate_passage_id"]+1}: {row["source_file"]} §{row["passage_id"]+1} ({row["similarity"]:.3f})')
            print(f'  {row["excerpt"]}')
    for notice in result.diagnostics['warnings']:
        print(f'Warning: {notice}', file=sys.stderr)


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            fp = StyleFingerprint.build(args.corpus, args.artifacts, negative_dir=args.negative_corpus,
                                        work_dir=False if args.no_work_corpus else args.work_corpus,
                                        gmail_dir=False if args.no_gmail_corpus else args.gmail_corpus,
                                        primary_test_dir=args.primary_positive_tests,
                                        holdout_fraction=0 if args.no_holdout else args.holdout_fraction,
                                        config=Config(seed=args.seed, device=args.device, local_files_only=args.offline))
            if args.json:
                print(json.dumps(fp.manifest, indent=2))
            else:
                print(f'Built {len(fp.manifest["historical_document_ids"])} historical documents into {args.artifacts} ({fp.manifest["mode"]}).')
                cache = fp.manifest['embedding_cache']
                print(f'Passage embeddings: {cache["computed"]} computed, {cache["reused"]} reused.')
                print(f'HTML report: {Path(args.artifacts) / "report.html"}')
                if fp.evaluation.get('holdout'):
                    print(f'{fp.evaluation["holdout"]["count"]} independent holdout documents reserved.')
                primary = fp.evaluation.get('primary_positive_tests')
                if primary:
                    print(f'{primary["count"]} primary positive test documents reserved outside training.')
        elif args.command == 'evaluate':
            fp = StyleFingerprint.load(args.artifacts)
            report = fp.evaluate()
            fp._save(Path(args.artifacts))
            if args.json:
                print(json.dumps(report, indent=2, allow_nan=False))
            else:
                if report.get('holdout'):
                    print('Independent holdout performance:')
                    print(json.dumps(report['holdout']['metrics'], indent=2))
                    print('By source: ' + json.dumps(report['holdout']['by_source'], indent=2))
                    print(f'HTML report: {Path(args.artifacts) / "report.html"}')
                primary = report.get('primary_positive_tests')
                if primary:
                    print(f'Primary positive tests: {primary["accepted_at_50"]}/{primary["count"]} at the fixed 50 cutoff; mean compatibility {primary["mean_compatibility"]:.1f}.')
                    for row in primary['documents']:
                        print(f'{row["document_id"]}: {row["score"]:.1f} / 100 ({row["evidence_strength"]})')
                    print('Positive-only test set: no independent false-positive rate or full accuracy estimate.')
                print(f'Document-grouped evaluation: {len(report["folds"])} held-out historical posts')
                for fold in report['folds']:
                    print(f'{fold["candidate_document_id"]}: {fold["score"]:.1f} / 100')
                print(f'Held-out variance: {report["score_variance"]:.3f}')
                if 'supervised' in report:
                    print(json.dumps(report['supervised']['metrics'], indent=2))
                else:
                    print('Positive-only evaluation: discrimination and authorship cannot be established.')
        else:
            if bool(args.file) == bool(args.text):
                raise ValueError('Supply exactly one candidate FILE or --text.')
            text = Path(args.file).read_text(encoding='utf-8') if args.file else args.text
            fp = StyleFingerprint.load(args.artifacts)
            result = fp.score(text, explain=(args.command == 'explain' or args.json), input_format=args.input_format)
            if args.json:
                print(json.dumps(result.to_dict(), indent=2, allow_nan=False))
            else:
                _print_score(result, args.command == 'explain')
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
