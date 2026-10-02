"""Collect explicitly curated, attributed blog excerpts; never crawl automatically."""
import argparse
from datetime import datetime, timezone
import hashlib
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
    if format == 'rst':
        # PEP headers, directives, indented code/quotes, and reference appendices
        # are excluded before applying the existing prose cleaner.
        source = source.split('\n\n', 1)[1] if '\n\n' in source else ''
        source = re.split(r'(?m)^(?:Copyright|References|Acknowledgements)\s*\n[=~-]+', source)[0]
        source = re.sub(r'(?m)^(?:[ \t]+\S|\.\.).*$', '', source)
    elif format != 'markdown':
        raise ValueError('Source format must be html, markdown, or rst')
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


def collect(sources, destination, *, fetch=_fetch):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    pending = []
    for source in sources:
        required = {'author','author_id','title','date','source_url','download_url','repository_revision','license','file','format'}
        if required - source.keys():
            raise ValueError(f'Missing source provenance: {sorted(required-source.keys())}')
        target = root / source['file']
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('Sample paths must remain inside the negative corpus')
        data = fetch(source['download_url'])
        prose = extract_prose(data.decode('utf-8'), source['format'], source.get('selector'))
        maximum = int(source.get('maximum_words', 190))
        minimum = int(source.get('minimum_words', 150))
        if not 3 <= minimum <= maximum:
            raise ValueError('Sample word limits must satisfy 3 <= minimum <= maximum')
        excerpt = sample_prose(prose, maximum=maximum, minimum=minimum)
        metadata = {k: v for k,v in source.items() if k not in {'file','format','selector'}}
        metadata.update({'retrieved_at': datetime.now(timezone.utc).isoformat(),
                         'source_sha256': hashlib.sha256(data).hexdigest(),
                         'sample_sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
                         'sampling': f'Contiguous sentence-complete prose excerpt, {minimum}–{maximum} whitespace words; markup/code/navigation/quoted blocks/equations removed.',
                         'excerpt_words': len(excerpt.split()), 'excerpt': True})
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
