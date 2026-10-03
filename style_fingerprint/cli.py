"""Local fingerprint commands and the writing self-editor."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from .config import Config
from .model import StyleFingerprint


def _parser():
    parser = argparse.ArgumentParser(description='Personal historical writing style compatibility (not authorship proof).')
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ['build', 'evaluate']:
        build = commands.add_parser(command, help='Refit production from frozen evaluation choices' if command == 'build' else 'Run grouped development evaluation and freeze choices')
        build.add_argument('--corpus', default=None)
        build.add_argument('--negative-corpus', default=None)
        build.add_argument('--primary-positive-tests', default=None, help='Legacy positive-only Markdown tests; requires --no-holdout')
        work = build.add_mutually_exclusive_group()
        work.add_argument('--work-corpus', default=None, help='Positive .txt emails (defaults to sibling work_corpus)')
        work.add_argument('--no-work-corpus', action='store_true', help='Exclude work email positives')
        gmail = build.add_mutually_exclusive_group()
        gmail.add_argument('--gmail-corpus', default=None, help='Positive .txt personal documents (defaults to sibling gmail_corpus)')
        gmail.add_argument('--no-gmail-corpus', action='store_true', help='Exclude Gmail positives')
        build.add_argument('--seed', type=int, default=None, help='Reproducible holdout and cross-validation seed')
        build.add_argument('--holdout-fraction', type=float, default=None, help='Email/negative holdout fraction; blogs reserve at least 50 percent')
        build.add_argument('--no-holdout', action='store_true', help='Development-only diagnostic; no independent holdout')
        build.add_argument('--device', choices=['auto','cpu','cuda','mps'], default='auto')
        build.add_argument('--offline', action='store_true', help='Require the pinned checkpoint in the local cache')
    for command in ['build', 'evaluate']:
        commands.choices[command].add_argument('--holdout-manifest', help='Sealed JSON manifest with holdout_v2 document IDs permanently excluded from fitting')
    commands.choices['build'].add_argument('--exclude-historical-holdout', action='store_true', help='Keep the consumed historical holdout out of production fitting')
    for name in ['score','explain']:
        sub = commands.add_parser(name, help='Score candidate prose' if name == 'score' else 'Explain candidate matches and mismatches')
        sub.add_argument('file', nargs='?')
        sub.add_argument('--text', help='Score raw text instead of a file')
        sub.add_argument('--input-format', choices=['markdown', 'email'], default='markdown', help='Use the same email cleaning as the positive work corpus')
    serve = commands.add_parser('serve', help='Start the local writing self-editor')
    serve.add_argument('--device', choices=['auto', 'mps', 'cuda', 'cpu'], default='auto')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8000)
    for sub in commands.choices.values():
        sub.add_argument('--artifacts', default='artifacts')
        sub.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    return parser


def _print_score(result, detailed):
    print(f'Style compatibility: {result.score:.1f} / 100')
    print(f'Decision: {result.decision}')
    print(f'Match threshold: {result.match_threshold if result.match_threshold is not None else "unavailable"}')
    print(f'Mismatch threshold: {result.mismatch_threshold if result.mismatch_threshold is not None else "unavailable"}')
    print(f'Evidence strength: {result.evidence_strength}')
    print(f'Usable words: {result.word_count}')
    print('Components: ' + ', '.join(f'{k.replace("_", " ")} {100*v:.1f}' for k,v in result.component_scores.items() if k not in {'ensemble', 'char_ngram'}))
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
        if args.command == 'serve':
            import uvicorn
            from .web import create_app
            uvicorn.run(create_app(args.artifacts, device=args.device), host=args.host, port=args.port, access_log=False)
        elif args.command in {'build', 'evaluate'}:
            bank = Path(args.artifacts)
            if args.command == 'build' and not (bank / 'evaluation_config.json').exists():
                print('No frozen evaluation configuration: running evaluation once before production refit.', file=sys.stderr if args.json else sys.stdout)
            saved = json.loads((bank / 'manifest.json').read_text()) if (bank / 'manifest.json').exists() else {}
            corpus_dir = args.corpus or saved.get('source_directory', 'blog_posts')
            if args.no_work_corpus:
                work_dir = False
            else:
                work_dir = args.work_corpus if args.work_corpus is not None else (saved.get('work_source_directory') or False if saved and args.corpus is None else None)
            if args.no_gmail_corpus:
                gmail_dir = False
            else:
                gmail_dir = args.gmail_corpus if args.gmail_corpus is not None else (saved.get('gmail_source_directory') or False if saved and args.corpus is None else None)
            negative_dir = args.negative_corpus or (saved.get('negative_source_directory') if args.corpus is None else None)
            frozen_path = bank / 'evaluation_config.json'
            frozen = json.loads(frozen_path.read_text()) if frozen_path.exists() and args.command == 'build' else None
            base_config = Config(**frozen['configuration']) if frozen else Config(**saved['configuration']) if saved and args.corpus is None else Config()
            config = replace(base_config, seed=args.seed if args.seed is not None else base_config.seed,
                             device=args.device or base_config.device,
                             local_files_only=True if args.offline else base_config.local_files_only)
            if args.no_holdout:
                holdout_fraction = 0
            elif args.holdout_fraction is not None:
                holdout_fraction = args.holdout_fraction
            elif saved and args.corpus is None:
                holdout_fraction = (saved.get('holdout_split') or {}).get('fraction', 0)
            else:
                holdout_fraction = .2
            if args.primary_positive_tests is None and args.corpus is None:
                args.primary_positive_tests = saved.get('primary_positive_test_directory')
            fp = StyleFingerprint.build(corpus_dir, bank, negative_dir=negative_dir,
                                        work_dir=work_dir, gmail_dir=gmail_dir,
                                        primary_test_dir=args.primary_positive_tests,
                                        holdout_fraction=holdout_fraction, config=config,
                                        build_mode='production' if args.command == 'build' else 'evaluation',
                                        holdout_manifest=args.holdout_manifest,
                                        include_historical_holdout=not getattr(args, 'exclude_historical_holdout', False))
            if args.json:
                print(json.dumps(fp.manifest if args.command == 'build' else fp.evaluation, indent=2, allow_nan=False))
            else:
                print(f'{args.command.capitalize()} completed: {len(fp.manifest["historical_document_ids"])} historical documents ({fp.manifest["mode"]}).')
                print(f'HTML report: {bank / "report.html"}')
                primary = fp.evaluation.get('primary_positive_tests')
                if primary:
                    print(f'{primary["count"]} primary positive test documents. Primary positive test acceptance: {primary["accepted_at_match_threshold"]}.')
                print(f'Document-grouped evaluation: {len(fp.evaluation["folds"])} held-out historical posts')
                if args.command == 'evaluate':
                    print(json.dumps(fp.evaluation.get('supervised', {}).get('metrics', {}), indent=2))
                    print('Development thresholds: ' + json.dumps(fp.evaluation.get('thresholds', {})))
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
