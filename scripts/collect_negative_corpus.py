"""Collect explicitly curated, attributed blog excerpts; never crawl automatically."""
import argparse
from datetime import datetime, timezone
import hashlib
import gzip
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
import yaml
from style_fingerprint.corpus import clean_markdown, sentence_spans


class _Paragraphs(HTMLParser):
    def __init__(self, selector):
        super().__init__(convert_charrefs=True)
        self.selector = selector
        self.stack = []
        self.paragraphs = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        selected = tag == self.selector or attrs.get('id') == self.selector or self.selector in classes
        blocked = tag in {'pre','code','script','style','nav','blockquote','math'} or any(c.startswith(('katex','MathJax')) for c in classes)
        # HTML void elements must not remain on the ancestor stack.
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
            self.stack.append((tag, selected, blocked))
        if tag == 'p' and any(s[1] for s in self.stack) and not any(s[2] for s in self.stack):
            self.current = []

    def handle_endtag(self, tag):
        if tag == 'p' and self.current is not None:
            paragraph = re.sub(r'\s+', ' ', ''.join(self.current)).strip()
            if paragraph:
                self.paragraphs.append(paragraph)
            self.current = None
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.current is not None and not any(s[2] for s in self.stack):
            self.current.append(data)


def extract_prose(source, format, selector=None):
    if format == 'html':
        if not selector:
            raise ValueError('HTML sources need an explicit article selector')
        parser = _Paragraphs(selector)
        parser.feed(source)
        return _remove_math('\n\n'.join(parser.paragraphs))
    if format != 'markdown':
        raise ValueError('Source format must be html or markdown')
    paragraphs = clean_markdown(source).split('\n\n')
    # Omit headings, translation/navigation notices, and very short media captions.
    return _remove_math('\n\n'.join(p for p in paragraphs if len(p.split()) >= 12 and not re.match(r'(?i)^(translations|discussions|updated|update:|video:)', p)))


def _remove_math(text):
    text = re.sub(r'(?s)\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)', '', text)
    return re.sub(r'\$[^$\n]+\$', '', text)


def sample_prose(prose, maximum=190, minimum=150):
    # Use a contiguous sentence-complete excerpt; never stitch unrelated passages.
    sentences = sentence_spans(prose)
    for start in range(len(sentences)):
        left = sentences[start]['start_char']
        right = left
        for sentence in sentences[start:]:
            candidate = prose[left:sentence['end_char']]
            if len(candidate.split()) > maximum:
                break
            right = sentence['end_char']
        if len(prose[left:right].split()) >= minimum:
            return prose[left:right]
    raise ValueError(f'No sentence-complete excerpt between {minimum} and {maximum} words; review this source manually.')


def _fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'PersonalStyleCorpus/0.1 (curated research excerpts)'}), timeout=30) as response:
        return response.read()


def selected_email(data, message_id, author=''):
    """Extract one explicitly curated public message, never combine a thread."""
    from style_fingerprint.corpus import clean_negative_email
    if data.startswith(b'\x1f\x8b'):
        data = gzip.decompress(data)
    matches = []
    for record in re.split(br'(?m)^From [^\n]*\n', data):
        if not record.strip():
            continue
        message = BytesParser(policy=policy.default).parsebytes(record)
        if str(message.get('Message-ID', '')).strip().strip('<>') == message_id.strip().strip('<>'):
            matches.append(message)
    if len(matches) != 1:
        raise ValueError('Expected exactly one selected message in the public archive')
    message = matches[0]
    part = message.get_body(preferencelist=('plain', 'html')) if message.is_multipart() else message
    if part is None or part.get_content_type() not in {'text/plain', 'text/html'}:
        raise ValueError('The selected message has no prose body')
    return clean_negative_email(part.get_content(), author)


def collect(sources, destination, *, fetch=_fetch):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    pending = []
    downloads = {}
    for source in sources:
        required = {'author','author_id','title','date','source_url','download_url','repository_revision','license','file','format'}
        if required - source.keys():
            raise ValueError(f'Missing source provenance: {sorted(required-source.keys())}')
        from style_fingerprint.corpus import negative_source_type
        kind = negative_source_type(source, source['file'])
        if kind is None or source['format'] not in {'html', 'markdown', 'mbox'}:
            raise ValueError('Source is not eligible human email or technical-blog prose')
        if source['format'] == 'mbox' and (kind != 'email' or not source.get('message_id')):
            raise ValueError('Public email archives require an explicit selected message ID')
        target = root / source['file']
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('Sample paths must remain inside the negative corpus')
        url = source['download_url']
        if url not in downloads:
            downloads[url] = fetch(url)
        data = downloads[url]
        source_hash = hashlib.sha256(data).hexdigest()
        if source.get('expected_source_sha256') and source['expected_source_sha256'] != source_hash:
            raise ValueError('Downloaded source hash differs from the pinned snapshot checksum')
        prose = (selected_email(data, source['message_id'], source['author']) if source['format'] == 'mbox'
                 else extract_prose(data.decode('utf-8'), source['format'], source.get('selector')))
        maximum = int(source.get('maximum_words', 190))
        minimum = int(source.get('minimum_words', 150))
        if not 3 <= minimum <= maximum:
            raise ValueError('Sample word limits must satisfy 3 <= minimum <= maximum')
        preserve = bool(source.get('preserve_message')) and kind == 'email'
        from style_fingerprint.corpus import word_count
        if preserve and not minimum <= word_count(prose) <= maximum:
            raise ValueError('Selected authored email body is outside its curated word limits')
        excerpt = prose if preserve else sample_prose(prose, maximum=maximum, minimum=minimum)
        metadata = {k: v for k,v in source.items() if k not in {'file','format','selector'}}
        metadata.update({'source_type': kind, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                         'source_sha256': source_hash,
                         'sample_sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
                         'sampling': ('One complete newly authored email body; quotations, signatures and boilerplate removed.' if preserve
                                      else f'Contiguous sentence-complete prose excerpt, {minimum}–{maximum} whitespace words; markup/code/navigation/quoted blocks/equations removed.'),
                         'excerpt_words': len(excerpt.split()), 'excerpt': not preserve})
        rendered = '---\n' + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True) + '---\n\n' + excerpt + '\n'
        if target.exists():
            from style_fingerprint.corpus import split_frontmatter
            existing_metadata, existing_body = split_frontmatter(target.read_text())
            # Unchanged snapshots are reproducible even though retrieval time would differ.
            if (existing_body.strip() != excerpt or existing_metadata.get('source_sha256') != metadata['source_sha256']
                    or any(existing_metadata.get(k) != v for k,v in metadata.items() if k != 'retrieved_at')):
                raise ValueError(f'Refusing to overwrite changed sample: {target}')
            rendered = target.read_text()
            metadata = existing_metadata
        pending.append((target, rendered))
        rows.append({'file': source['file'], **metadata})
    # Validate all samples before replacing any existing corpus files.
    for target, rendered in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered)
    (root / 'manifest.json').write_text(json.dumps({'schema_version':1, 'documents':rows}, indent=2, ensure_ascii=False))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', default='docs/negative_sources.json')
    parser.add_argument('--output', default='negative_posts')
    args = parser.parse_args()
    sources = json.loads(Path(args.sources).read_text())['sources']
    def polite_fetch(url):
        data = _fetch(url)
        time.sleep(.2)
        return data
    rows = collect(sources, args.output, fetch=polite_fetch)
    print(f'Collected {len(rows)} independent excerpts by {len({r["author_id"] for r in rows})} authors.')


if __name__ == '__main__':
    main()
