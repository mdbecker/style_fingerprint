"""Validate the explicit maintained documentation inventory and local links."""
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit

MAINTAINED_DOCS=frozenset({'README.md','specification.md','historical-specifications.md','implementation.md',
                         'development.md','corpus.md','evaluation.md','negative-corpus.md',
                         'negative-inventory.md','negative_sources.json'})


def prose(text):
    return re.sub(r'(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$', '', text)


def anchors(text):
    found=set();counts={}
    for title in re.findall(r'(?m)^#{1,6}\s+(.+?)\s*#*$',prose(text)):
        slug=re.sub(r'[^\w\- ]','',title.lower()).replace(' ','-')
        n=counts.get(slug,0);counts[slug]=n+1
        found.add(slug+(f'-{n}' if n else ''))
    return found


def check_documentation(root):
    root=Path(root);directory=root/'docs';errors=[]
    actual={str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}
    for name in sorted(actual-MAINTAINED_DOCS):
        kind='Generated transcript' if re.match(r'(?:red|green)[-_]',Path(name).name,re.I) else 'Unmaintained document'
        errors.append(f'{kind}: docs/{name}')
    errors.extend(f'Missing maintained document: docs/{name}' for name in sorted(MAINTAINED_DOCS-actual))
    pages=[root/'README.md',root/'AGENTS.md']+[directory/name for name in sorted(MAINTAINED_DOCS) if name.endswith('.md')]
    for p in pages:
        if not p.exists():errors.append(f'Missing required page: {p.name}');continue
        text=prose(p.read_text())
        links=re.findall(r'\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)',text)
        links+=re.findall(r'(?m)^\s*\[[^\]]+\]:\s*(\S+)',text)
        for link in links:
            link=link.strip('<>');parsed=urlsplit(link)
            if parsed.scheme or parsed.netloc:continue
            target=p.parent/unquote(parsed.path) if parsed.path else p
            if not target.exists():errors.append(f'{p.relative_to(root)}: broken local link {link}')
            elif parsed.fragment and target.suffix=='.md' and unquote(parsed.fragment) not in anchors(target.read_text()):
                errors.append(f'{p.relative_to(root)}: broken heading link {link}')
    return errors


if __name__=='__main__':
    errors=check_documentation(Path(__file__).resolve().parents[1])
    print('\n'.join(errors) if errors else 'Documentation inventory and links pass.')
    raise SystemExit(bool(errors))
