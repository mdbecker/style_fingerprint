"""Public project files must not enumerate private message identities."""
from pathlib import Path
import re
import subprocess


def test_given_public_sources_when_audited_then_private_numeric_message_paths_are_absent():
    root=Path(__file__).resolve().parents[1]
    excluded={'work_corpus','gmail_corpus','artifacts','prototype','.cache','model_cache','.venv','.pytest_cache','__pycache__','.git'}
    pattern=re.compile(r'(?:work|gmail)(?:_corpus)?/\d+\.[tT][xX][tT]')
    offenders=[]
    for p in root.rglob('*'):
        if not p.is_file() or any(part in excluded or part.endswith('.egg-info') for part in p.relative_to(root).parts): continue
        try: text=p.read_text()
        except (UnicodeError,OSError): continue
        if pattern.search(text): offenders.append(str(p.relative_to(root)))
    assert not offenders, f'Publishable files contain private message identities: {offenders}'


def test_given_nested_private_inputs_when_git_checks_then_both_trees_are_ignored(tmp_path):
    root=Path(__file__).resolve().parents[1]
    (tmp_path/'.gitignore').write_bytes((root/'.gitignore').read_bytes())
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    paths=[f'{source}/nested/synthetic-message.txt' for source in ['work_corpus','gmail_corpus']]
    result=subprocess.run(['git','-C',str(tmp_path),'-c','core.excludesFile=/dev/null','check-ignore','--no-index',*paths],capture_output=True,text=True,check=True)
    assert set(result.stdout.splitlines())==set(paths)


def test_given_private_negative_emails_when_git_checks_then_author_subtrees_are_ignored(tmp_path):
    root=Path(__file__).resolve().parents[1]
    (tmp_path/'.gitignore').write_bytes((root/'.gitignore').read_bytes())
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    path='negative_posts/email/invented-writer/invented-message.md'
    result=subprocess.run(['git','-C',str(tmp_path),'-c','core.excludesFile=/dev/null','check-ignore','--no-index',path],capture_output=True,text=True)
    assert result.returncode == 0 and result.stdout.strip()==path


def test_given_local_downloaded_negative_corpus_when_git_checks_then_prose_and_downloads_are_ignored(tmp_path):
    root=Path(__file__).resolve().parents[1]
    (tmp_path/'.gitignore').write_bytes((root/'.gitignore').read_bytes())
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    paths=['negative_posts/local/blogs/invented-writer/post.md',
           'negative_posts/local/email/invented-writer/message.md',
           'artifacts/negative_collection/email/archive.mbox']
    result=subprocess.run(['git','-C',str(tmp_path),'-c','core.excludesFile=/dev/null','check-ignore','--no-index',*paths],capture_output=True,text=True)
    assert set(result.stdout.splitlines()) == set(paths)
