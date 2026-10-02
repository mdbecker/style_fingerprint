"""Markdown and plain-text email ingestion with nonoverlapping passages."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import html
import re
import random
import yaml

WORD_RE = re.compile(r"\b[\w]+(?:['’][\w]+)*\b", re.UNICODE)


@dataclass
class Document:
    document_id: str
    source_file: str
    raw_markdown: str
    clean_text: str
    file_hash: str
    author: str | None = None
    metadata: dict | None = None
    root_document_id: str | None = None
    author_id: str | None = None

    def __post_init__(self):
        if self.root_document_id is None:
            self.root_document_id = self.document_id
        if self.author_id is None:
            self.author_id = (self.metadata or {}).get('author_id') or self.author


@dataclass
class TrainingView(Document):
    """A correlated training observation, retaining its original document identity."""

    @property
    def view_id(self):
        return self.document_id

    @property
    def text(self):
        return self.clean_text

    @property
    def word_count(self):
        return word_count(self.clean_text)


@dataclass
class Passage:
    document_id: str
    passage_id: int
    text: str
    start_char: int
    end_char: int
    word_count: int
    root_document_id: str | None = None
    author_id: str | None = None

    def __post_init__(self):
        if self.root_document_id is None:
            self.root_document_id = self.document_id


def word_count(text):
    return len(WORD_RE.findall(text))


def split_frontmatter(text):
    match = re.match(r'\A\ufeff?---\s*\n(.*?)\n(?:---|\.\.\.)\s*(?:\n|$)', text, re.S)
    if not match:
        return {}, text
    try:
        metadata = yaml.safe_load(match[1]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f'Invalid YAML front matter: {exc}') from exc
    if not isinstance(metadata, dict):
        raise ValueError('YAML front matter must be a mapping')
    return metadata, text[match.end():]


def prose_markup(text):
    """Remove non-author prose before stripping structural Markdown markers."""
    _, text = split_frontmatter(text)
    text = re.sub(r'(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$', '\n', text)
    # Unclosed code fence consumes the rest of the file.
    text = re.sub(r'(?ms)^\s*(?:`{3,}|~{3,})[^\n]*\n.*\Z', '\n', text)
    text = re.sub(r'(?is)\{%\s*(codeblock|highlight)\b.*?%\}.*?\{%\s*end\1\s*%\}', '\n', text)
    text = re.sub(r'(?s)\{%.*?%\}|\{\{.*?\}\}', '', text)
    text = re.sub(r'(?m)^(?: {4}|\t).*(?:\n|$)', '', text)
    text = re.sub(r'(?is)<!--.*?-->|<(script|style|nav|pre)\b[^>]*>.*?</\1\s*>', '', text)
    text = re.sub(r'(?is)<(div|section)\b[^>]*(?:id|class)=["\'][^"\']*(?:toc|navigation)[^"\']*["\'][^>]*>.*?</\1\s*>', '', text)
    text = re.sub(r'!\[[^\]]*\]\([^\n]*?\)|!\[[^\]]*\]\[[^\]]*\]', '', text)
    text = re.sub(r'(`+).*?\1', '', text)
    text = re.sub(r'(?im)^\s*(?:#{1,6}\s*)?(?:table of contents|contents)\s*#*\s*(?=\n(?:\s*\n)*\s*[-*+]\s+\[[^\]]+\]\(#)', '', text)
    text = re.sub(r'(?m)^\s*(?:[-*+]\s+)?\[[^\]]+\]\(#[^)]*\)\s*$', '', text)
    text = re.sub(r'(?im)^\s*\[(?:previous|next)(?: post| article)?\]\([^)]*\)(?:\s*[|·/]\s*\[(?:previous|next)(?: post| article)?\]\([^)]*\))*\s*$','', text)
    text = re.sub(r'\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)
    text = re.sub(r'(?m)^\s*\[[^\]]+\]:\s*\S+.*$', '', text)
    text = re.sub(r'(?m)^\s*(?:[-*+]\s+)?\[[^\]]+\]\(#[^)]*\)\s*$', '', text)
    text = re.sub(r'(?i)https?://[^\s<>]+|www\.[^\s<>]+', '', text)
    text = re.sub(r'(?i)<(?:br\s*/?|/?(?:p|div|li|h[1-6]))\b[^>]*>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text)


def clean_markdown(text):
    text = prose_markup(text)
    text = re.sub(r'(?m)^\s{0,3}(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)', '', text)
    text = re.sub(r'(?m)^\s*(?:[-*_]{3,}|={3,})\s*$', '', text)
    text = re.sub(r'(?<!\w)[*_]{1,3}|[*_]{1,3}(?!\w)', '', text)
    text = re.sub(r'(?m)[ \t]+$', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def load_corpus(directory):
    root = Path(directory)
    paths = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in {'.md', '.markdown', '.mdown'})
    if not paths:
        raise ValueError(f'No Markdown posts found under {root}')
    docs = []
    for path in paths:
        raw = path.read_text(encoding='utf-8')
        metadata, _ = split_frontmatter(raw)
        clean = clean_markdown(raw)
        if not word_count(clean):
            raise ValueError(f'{path}: no usable prose')
        docs.append(Document(path.relative_to(root).as_posix(), str(path.resolve()), raw, clean,
                             hashlib.sha256(path.read_bytes()).hexdigest(),
                             str(metadata['author']) if metadata.get('author') else None,
                             {str(k): str(v) for k, v in metadata.items()}))
    return docs


def clean_email(text, author='Michael Becker'):
    """Conservative plain-text email cleaning; do not infer missing thread dates."""
    _, text = split_frontmatter(text)
    text = text.replace('\r\n', '\n').replace('\r', '\n').lstrip('\ufeff')
    lines = text.splitlines()
    # Exported headers are recognized only at the beginning of a message.
    while lines and re.match(r'^(?:From|To|Cc|Bcc|Subject|Sent|Date):', lines[0], re.I):
        lines.pop(0)
    kept = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'^(?:On .+wrote:|[-_]{2,}\s*(?:Original Message|Forwarded message))', stripped, re.I):
            break
        if stripped == '--' or (stripped == author and word_count('\n'.join(lines[index:])) <= 80 and any(
                re.search(r'(?i)(?:scientist|engineer|manager|director|Email:|@)', item)
                for item in lines[index + 1:index + 5])):
            break
        if stripped.startswith('>') or re.fullmatch(r'\[?Image\]?', stripped, re.I):
            continue
        stripped = re.sub(r'https?://\S+|www\.\S+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '', stripped)
        stripped = re.sub(r'^(?:·|§|o)\s{2,}', '- ', stripped)
        kept.append(re.sub(r'[ \t]+', ' ', stripped).rstrip())
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(kept)).strip()


def load_work_corpus(directory):
    return load_email_corpus(directory, source='work')


def load_email_corpus(directory, source='work'):
    """Load individually authored plain-text messages as positive documents."""
    root = Path(directory)
    paths = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() == '.txt')
    if not paths:
        raise ValueError(f'No plain-text {source} emails found under {root}')
    docs = []
    for path in paths:
        raw = path.read_text(encoding='utf-8')
        metadata, _ = split_frontmatter(raw)
        metadata = {str(k): str(v) for k, v in metadata.items()}
        metadata.update({'genre': f'{source}_email'})
        metadata.setdefault('author', 'Michael Becker')
        metadata.setdefault('author_id', 'mdbecker')
        clean = clean_email(raw, metadata['author'])
        if word_count(clean) < 3:
            raise ValueError(f'{path}: fewer than three words of usable email prose')
        docs.append(Document(source + '/' + path.relative_to(root).as_posix(), str(path.resolve()),
                             raw, clean, hashlib.sha256(path.read_bytes()).hexdigest(),
                             metadata['author'], metadata))
    return docs


def sentence_spans(text):
    """Conservative punctuation segmenter; offsets refer to the cleaned input."""
    protected = re.sub(r'\b(?:Dr|Mr|Mrs|Ms|Prof|St|vs|etc|e\.g|i\.e)\.', lambda m: m[0].replace('.', '\x00'), text)
    spans = []
    start = 0
    for match in re.finditer(r'[.!?]+["\'’”)]*(?=\s+|$)|\n\s*\n', protected):
        end = match.end() if not match[0].startswith('\n') else match.start()
        left, right = start, end
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right-1].isspace():
            right -= 1
        if word_count(text[left:right]):
            spans.append({'text': text[left:right], 'start_char': left, 'end_char': right, 'index': len(spans)})
        start = match.end()
    left = start
    while left < len(text) and text[left].isspace():
        left += 1
    if word_count(text[left:]):
        spans.append({'text': text[left:], 'start_char': left, 'end_char': len(text), 'index': len(spans)})
    return spans


def chunk_text(text, document_id, target=300, minimum=100, maximum=700,
               *, root_document_id=None, author_id=None):
    if not word_count(text):
        return []
    units = []
    for paragraph in re.finditer(r'\S(?:.*?\S)?(?=\n\s*\n|$)', text, re.S):
        start, end = paragraph.span()
        if word_count(paragraph[0]) <= maximum:
            units.append((start, end))
        else:
            # Oversized paragraphs are split at sentence boundaries, then words if needed.
            words = list(WORD_RE.finditer(text, start, end))
            left = start
            while len(words) > maximum:
                split = words[maximum].start()
                candidates = [s['end_char'] + left for s in sentence_spans(text[left:split])
                              if word_count(text[left:s['end_char'] + left]) >= minimum]
                cut = candidates[-1] if candidates else words[maximum-1].end()
                units.append((left, cut))
                left = cut
                while left < end and text[left].isspace():
                    left += 1
                words = list(WORD_RE.finditer(text, left, end))
            if left < end:
                units.append((left, end))
    groups = []
    begin = finish = None
    for start, end in units:
        if begin is None:
            begin, finish = start, end
        elif word_count(text[begin:end]) > maximum or word_count(text[begin:finish]) >= target:
            groups.append((begin, finish))
            begin, finish = start, end
        else:
            finish = end
    if begin is not None:
        groups.append((begin, finish))
    if len(groups) > 1 and word_count(text[slice(*groups[-1])]) < minimum:
        if word_count(text[groups[-2][0]:groups[-1][1]]) <= maximum:
            groups[-2:] = [(groups[-2][0], groups[-1][1])]
    return [Passage(document_id, i, text[start:end], start, end, word_count(text[start:end]),
                    root_document_id or document_id, author_id)
            for i, (start, end) in enumerate(groups)]


def generate_training_views(document, *, seed=42):
    """Choose bounded contiguous paragraph windows; oversized paragraphs use sentences.

    The full document is always retained, even when it exceeds the window cap.
    An indivisible oversized sentence is retained only in that full-document view.
    """
    text = document.clean_text
    size = word_count(text)
    units = []
    for paragraph in re.finditer(r'\S(?:.*?\S)?(?=\n\s*\n|$)', text, re.S):
        start, end = paragraph.span()
        if word_count(paragraph[0]) <= 700:
            units.append((start, end))
        else:
            units.extend((start + s['start_char'], start + s['end_char'])
                         for s in sentence_spans(paragraph[0]))
    windows = []
    if size > 600:
        for index, (start, _) in enumerate(units):
            for _, end in units[index:]:
                count = word_count(text[start:end])
                if count > 700:
                    break
                if count >= 300 and (start, end) != (0, len(text)):
                    windows.append((start, end, count))
        preferred = [w for w in windows if 350 <= w[2] <= 600]
        rng = random.Random(f'{seed}:{document.root_document_id}')
        rng.shuffle(preferred)
        remainder = [w for w in windows if w not in preferred]
        rng.shuffle(remainder)
        windows = (preferred + remainder)[:2 if size <= 1000 else 5]
    else:
        windows = []
    spans = [(a, b) for a, b, _ in sorted(windows)] + [(0, len(text))]
    return [TrainingView(
        f'{document.root_document_id}::view_{index:02d}', document.source_file,
        text[start:end], text[start:end],
        hashlib.sha256(text[start:end].encode()).hexdigest(), document.author,
        dict(document.metadata or {}), document.root_document_id, document.author_id)
        for index, (start, end) in enumerate(spans)]


def make_training_views(text, root_document_id, *, seed=42, author_id=None):
    """Text-only convenience API for deterministic training/scoring views."""
    document = Document(root_document_id, '', text, text,
                        hashlib.sha256(text.encode()).hexdigest(), author_id=author_id)
    return generate_training_views(document, seed=seed)
