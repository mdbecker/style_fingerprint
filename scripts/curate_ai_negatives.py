"""Deterministic, local bookkeeping for externally generated, manually reviewed prose."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys

import yaml

# Support invocation as a script without requiring an editable installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from style_fingerprint.corpus import (WORD_RE, clean_markdown, clean_email, load_corpus,
                                      load_email_corpus, sentence_spans, split_frontmatter,
                                      valid_synthetic_metadata, word_count)

INITIAL_PROMPT = '''Read the source passage below.

Write an actual message or document about a closely related situation, preserving the same medium, audience, and communicative purpose as the source. Keep comparable specificity and a similar length within 150–700 words.

Perform the communication itself: make the request, propose the changes, report the experience, or explain the technical work. Do not write advice about composing it, commentary about that type of writing, or a fictional story in place of a practical message.

Write it as though it were written independently by a different author. Use a noticeably different style and tone from the source.

Do not quote the source, closely paraphrase its sentences, mention the source, mention this instruction, or describe what you are doing.

Return only the new prose.

SOURCE:

'''
RETRY_PROMPT = '''Try again.

Keep the subject broadly similar, but write a new version as a different author using a substantially different style and tone. Preserve the source’s medium, audience, purpose, and specificity. Produce the actual communication.

Do not quote or closely paraphrase the source or the previous version.

Return only the new prose.'''
SIGNALS = frozenset(f'T{i:02}' for i in range(1, 31))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def storage(repo):
    return Path(repo).resolve() / 'artifacts/ai_negative_generation'


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def records(repo):
    path = storage(repo) / 'reviews.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def job_path(repo, job_id):
    if not re.fullmatch(r'synth-\d{4,}', job_id):
        raise ValueError('Invalid job ID')
    return storage(repo) / 'jobs' / f'{job_id}.json'


def git_tracked(repo, path):
    try:
        relative = path.resolve().relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        return False
    result = subprocess.run(['git', '-C', str(repo), 'ls-files', '--error-unmatch', '--', relative],
                            capture_output=True)
    ignored = subprocess.run(['git', '-C', str(repo), 'check-ignore', '--no-index', '--', relative],
                             capture_output=True)
    return result.returncode == 0 and ignored.returncode == 1


def source_text(path):
    raw = path.read_text()
    return clean_email(raw) if path.suffix.lower() == '.txt' else clean_markdown(raw)


def was_private_root(repo, path):
    """A previously observed private positive root cannot lose its recorded taint."""
    for record_path in (storage(repo) / 'jobs').glob('*.json'):
        job = json.loads(record_path.read_text())
        parent = Path(job['parent_path'])
        parent = parent if parent.is_absolute() else Path(repo) / parent
        if parent.resolve() == path and job['lineage_visibility'] == 'untracked':
            return True
    return False


def provenance(repo, path, seen=None):
    """Resolve every synthetic ancestor through local records; never trust a visibility claim."""
    path = Path(path).resolve()
    sha = digest(path.read_bytes())
    seen = set() if seen is None else seen
    if sha in seen:
        raise ValueError('Cyclic synthetic provenance')
    seen.add(sha)
    metadata, _ = split_frontmatter(path.read_text())
    if metadata.get('source_type') != 'ai_synthetic':
        lineage = 'synthetic-lineage-' + digest(str(path).encode())[:20]
        visibility = 'tracked' if git_tracked(repo, path) and not was_private_root(repo, path) else 'untracked'
        return lineage, visibility, sha
    if not valid_synthetic_metadata(metadata):
        raise ValueError('Invalid synthetic provenance')
    matches = [r for r in records(repo) if r['decision'] == 'approved' and r['output_sha256'] == sha]
    if not matches:
        raise ValueError('Unresolvable synthetic provenance')
    previous = json.loads(job_path(repo, matches[0]['job_id']).read_text())
    parent = Path(previous['parent_path'])
    parent = parent if parent.is_absolute() else Path(repo) / parent
    lineage, ancestor_visibility, parent_sha = provenance(repo, parent, seen)
    if parent_sha != metadata['synthetic_parent_sha256'] or lineage != metadata['synthetic_lineage_id']:
        raise ValueError('Synthetic provenance changed')
    visibility = 'tracked' if (git_tracked(repo, path) and ancestor_visibility == 'tracked'
                               and previous['lineage_visibility'] == 'tracked'
                               and metadata['lineage_visibility'] == 'tracked') else 'untracked'
    return lineage, visibility, sha


def excerpt(text, rng):
    spans = sentence_spans(text)
    if word_count(text) <= 600:
        return text
    eligible = [i for i, span in enumerate(spans) if word_count(text[span['start_char']:]) >= 300]
    start = rng.choice(eligible or [0])
    left = spans[start]['start_char']
    right = spans[start]['end_char']
    for span in spans[start:]:
        if word_count(text[left:span['end_char']]) > 600:
            break
        right = span['end_char']
        if word_count(text[left:right]) >= 450:
            break
    # Unpunctuated/very long sentences still use a contiguous usable excerpt.
    if word_count(text[left:right]) > 600 or word_count(text[left:right]) < 300:
        words = list(WORD_RE.finditer(text[left:]))
        right = left + words[min(450, len(words)) - 1].end()
    return text[left:right]


def positive_directories(repo, configured=None):
    if configured:
        return [Path(root).resolve() for root in configured]
    manifest = Path(repo) / 'artifacts/manifest.json'
    saved = json.loads(manifest.read_text()) if manifest.exists() else {}
    roots = [saved.get('source_directory') or Path(repo) / 'blog_posts']
    roots += [saved[key] for key in ('work_source_directory', 'gmail_source_directory') if saved.get(key)]
    return [Path(root).resolve() for root in roots]


def sample(repo, *, generator_id, sequence, parent=None, positive_roots=None):
    repo = Path(repo).resolve()
    if not generator_id.strip() or sequence < 1:
        raise ValueError('A generator ID and positive generation sequence are required')
    identifier = f'synth-{sequence:04}'
    target = job_path(repo, identifier)
    if target.exists():
        existing = json.loads(target.read_text())
        existing_parent = Path(existing['parent_path'])
        existing_parent = existing_parent if existing_parent.is_absolute() else repo / existing_parent
        if existing['generator_id'] != generator_id or (parent is not None and existing_parent.resolve() != Path(parent).resolve()):
            raise ValueError('Job already exists with different inputs')
        return existing
    rng = random.Random(42 + sequence)
    counts = Counter(r['synthetic_lineage_id'] for r in records(repo) if r['decision'] == 'approved')
    if parent is None:
        roots = positive_directories(repo, positive_roots)
        candidates = []
        for root in roots:
            root = Path(root)
            markdown = any(p.suffix.lower() in {'.md', '.markdown', '.mdown'} for p in root.rglob('*') if p.is_file())
            documents = load_corpus(root) if markdown else load_email_corpus(root)
            for doc in documents:
                path = Path(doc.source_file)
                lineage, _, _ = provenance(repo, path)
                if counts[lineage] < 20:
                    candidates.append((counts[lineage], str(path)))
        if not candidates:
            raise ValueError('No eligible positive roots below the 20-example lineage cap')
        minimum = min(count for count, _ in candidates)
        parent = Path(rng.choice(sorted(path for count, path in candidates if count == minimum)))
    else:
        parent = Path(parent).resolve()
        metadata, _ = split_frontmatter(parent.read_text())
        if metadata.get('source_type') != 'ai_synthetic':
            roots = positive_directories(repo, positive_roots)
            if parent.suffix.lower() not in {'.txt', '.md', '.markdown', '.mdown'} or not any(parent.is_relative_to(root) for root in roots):
                raise ValueError('Parent must be an eligible configured positive root or reviewed synthetic ancestor')
    lineage, visibility, sha = provenance(repo, parent)
    if counts[lineage] >= 20:
        raise ValueError('A lineage may contribute at most 20 approved MVP examples')
    text = source_text(parent)
    if not word_count(text):
        raise ValueError('Source has no usable prose')
    try:
        parent_path = parent.relative_to(repo).as_posix()
    except ValueError:
        parent_path = str(parent)
    passage = excerpt(text, rng)
    job = dict(job_id=identifier, generator_id=generator_id, generation_attempt=1,
               consecutive_rejections=0, synthetic_lineage_id=lineage, lineage_visibility=visibility,
               parent_path=parent_path, parent_sha256=sha, synthetic_parent_id=digest(str(parent).encode())[:24],
               excerpt=passage, prompt=INITIAL_PROMPT + passage, completed=False)
    save_json(target, job)
    return job


def rotate(repo, job_id, generator_id):
    path = job_path(repo, job_id)
    job = json.loads(path.read_text())
    if not generator_id.strip() or generator_id == job['generator_id'] or job['completed']:
        raise ValueError('Choose another generator for an unfinished job')
    job.update(generator_id=generator_id, consecutive_rejections=0)
    save_json(path, job)


def check_content(body, source):
    if split_frontmatter(body)[0]:
        raise ValueError('Input must contain only prose, without front matter')
    text = clean_markdown(body)
    if not 150 <= word_count(text) <= 700:
        raise ValueError('Output must contain 150–700 usable words')
    source_words = WORD_RE.findall(source.casefold())
    words = WORD_RE.findall(text.casefold())
    source_windows = {tuple(source_words[i:i + 12]) for i in range(len(source_words) - 11)}
    if any(tuple(words[i:i + 12]) in source_windows for i in range(len(words) - 11)):
        raise ValueError('Output copies a source sequence of at least 12 words')
    sentences = {s['text'].strip().casefold() for s in sentence_spans(source) if word_count(s['text']) >= 8}
    if any(s['text'].strip().casefold() in sentences for s in sentence_spans(text)):
        raise ValueError('Output copies a long source sentence')
    return body.strip() + '\n'


def valid_source_fit(evidence):
    return isinstance(evidence, dict) and all(isinstance(evidence.get(k), str) and evidence[k].strip()
        for k in ("medium", "audience", "purpose", "specificity"))


def review(repo, job_id, body, *, approve, signals=(), source_fit=None):
    repo = Path(repo).resolve()
    target = job_path(repo, job_id)
    job = json.loads(target.read_text())
    if job['completed']:
        raise ValueError('Job was already approved')
    if not str(job['generator_id']).strip():
        raise ValueError('A nonempty generator ID is required')
    if job['consecutive_rejections'] >= 5:
        raise ValueError('Rotate to another generator after five consecutive rejections')
    labels = sorted(set(signals))
    accepted = None
    if approve:
        if not valid_source_fit(source_fit):
            raise ValueError("Approval requires manual source fit evidence for medium, audience, purpose, and specificity")
        if not labels or not set(labels) <= SIGNALS:
            raise ValueError('Approval requires at least one valid reviewer signal ID')
        parent = Path(job['parent_path'])
        parent = parent if parent.is_absolute() else repo / parent
        lineage, visibility, sha = provenance(repo, parent)
        if sha != job['parent_sha256']:
            raise ValueError('Parent content changed since sampling')
        if lineage != job['synthetic_lineage_id'] or visibility != job['lineage_visibility']:
            raise ValueError('Job provenance changed; tracked admission refused')
        counts = Counter(r['synthetic_lineage_id'] for r in records(repo) if r['decision'] == 'approved')
        if counts[lineage] >= 20:
            raise ValueError('A lineage may contribute at most 20 approved MVP examples')
        prose = check_content(body, source_text(parent))
        metadata = dict(source_type='ai_synthetic', human_authored=False, author_id=lineage,
                        synthetic_lineage_id=lineage, synthetic_parent_id=job['synthetic_parent_id'],
                        synthetic_parent_sha256=sha, lineage_visibility=visibility,
                        generator_id=job['generator_id'], generation_attempt=job['generation_attempt'])
        accepted = repo / 'negative_posts/ai' / visibility / f'{job_id}.md'
        if accepted.parent.resolve() != accepted.parent:
            raise ValueError('Synthetic destination must not redirect through a symlink')
        accepted.parent.mkdir(parents=True, exist_ok=True)
        raw = '---\n' + yaml.safe_dump(metadata, sort_keys=False) + '---\n\n' + prose
        # Exclusive creation protects already curated prose from accidental overwrite.
        with accepted.open('x') as handle:
            handle.write(raw)
        output_hash = digest(raw.encode())
        job['completed'] = True
    else:
        output_hash = digest(body.encode())
        job['consecutive_rejections'] += 1
    attempt_path = storage(repo) / 'attempts' / f'{job_id}-{job["generation_attempt"]:02}.txt'
    attempt_path.parent.mkdir(parents=True, exist_ok=True)
    attempt_path.write_text(body)
    record = dict(job_id=job_id, attempt=job['generation_attempt'], generator_id=job['generator_id'],
                  synthetic_lineage_id=job['synthetic_lineage_id'], decision='approved' if approve else 'rejected',
                  signals=labels if approve else [], source_fit=source_fit if approve else None, accepted_path=accepted.relative_to(repo).as_posix() if accepted else None,
                  lineage_visibility=job['lineage_visibility'], parent_sha256=job['parent_sha256'], output_sha256=output_hash)
    with (storage(repo) / 'reviews.jsonl').open('a') as handle:
        handle.write(json.dumps(record) + '\n')
    job['generation_attempt'] += 1
    save_json(target, job)
    return accepted if approve else RETRY_PROMPT


def status(repo):
    approved = [r for r in records(repo) if r['decision'] == 'approved']
    generators = Counter(r['generator_id'] for r in approved)
    lineages = Counter(r['synthetic_lineage_id'] for r in approved)
    signals = Counter(signal for r in approved for signal in r['signals'])
    intact = all((Path(repo) / r['accepted_path']).exists() and
                 digest((Path(repo) / r['accepted_path']).read_bytes()) == r['output_sha256'] for r in approved)
    fit_reviewed = all(valid_source_fit(r.get('source_fit')) for r in approved)
    total = len(approved)
    complete = (total >= 100 and len(generators) >= 3 and sum(n >= 20 for n in generators.values()) >= 3
                and max(generators.values(), default=0) <= total / 2 and len(lineages) >= 5
                and max(lineages.values(), default=0) <= 20 and len(signals) >= 12 and intact and fit_reviewed)
    return dict(approved=total, rejected=sum(r['decision'] == 'rejected' for r in records(repo)),
                generators=dict(generators), lineages=dict(lineages), signals=dict(signals),
                visibility=dict(Counter(r['lineage_visibility'] for r in approved)),
                accepted_files_intact=intact, source_fit_reviewed=fit_reviewed, complete=complete)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    sampling = commands.add_parser('sample')
    sampling.add_argument('--generator-id', required=True)
    sampling.add_argument('--sequence', type=int, required=True)
    sampling.add_argument('--parent', type=Path)
    sampling.add_argument('--positive-root', action='append', type=Path)
    reviewing = commands.add_parser('review')
    reviewing.add_argument('--job', required=True)
    reviewing.add_argument('--input', required=True, type=Path)
    decision = reviewing.add_mutually_exclusive_group(required=True)
    decision.add_argument('--approve', action='store_true')
    decision.add_argument('--reject', action='store_true')
    reviewing.add_argument('--signals', default='')
    reviewing.add_argument('--source-fit', type=Path, help='Local JSON evidence for medium, audience, purpose, specificity')
    reviewing.add_argument('--generator-id', help='Rotate an unfinished job to a different generator')
    commands.add_parser('status')
    args = parser.parse_args(argv)
    try:
        if args.command == 'sample':
            job = sample(args.repo, generator_id=args.generator_id, sequence=args.sequence,
                         parent=args.parent, positive_roots=args.positive_root)
            print(job['prompt'])
        elif args.command == 'review':
            if args.generator_id:
                rotate(args.repo, args.job, args.generator_id)
            print(review(args.repo, args.job, args.input.read_text(), approve=args.approve,
                         signals=[s.strip() for s in args.signals.split(',') if s.strip()],
                         source_fit=json.loads(args.source_fit.read_text()) if args.source_fit else None))
        else:
            print(json.dumps(status(args.repo), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
