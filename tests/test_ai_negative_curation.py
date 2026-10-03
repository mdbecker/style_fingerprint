"""Blind curation outcomes use invented prose and real local Git provenance."""
import json
import subprocess
import pytest
from scripts import curate_ai_negatives as curate
from style_fingerprint.corpus import load_negative_corpus

FIT = dict(medium='Research blog prose', audience='Technical readers', purpose='Reports an experiment', specificity='Concrete observations')

BODY = ' '.join(f'The instrument recorded measurement {n} while observers checked a separate calibration.' for n in range(22))

@pytest.fixture
def repo(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / '.gitignore').write_text('artifacts/\nnegative_posts/ai/untracked/\nprivate/\n')
    (tmp_path / 'blog_posts').mkdir()
    for n in range(6):
        (tmp_path / 'blog_posts' / f'{n}.md').write_text(f'A source about experiment {n}. ' + ' '.join(f'Original observation {i} suggests careful investigation.' for i in range(90)))
    subprocess.run(['git', '-C', str(tmp_path), 'add', '.'], check=True)
    return tmp_path


def test_given_tracked_source_when_approved_then_loaded_and_grouped_by_lineage(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    path = curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])
    assert path.parent == repo / 'negative_posts/ai/tracked'
    doc = load_negative_corpus(repo / 'negative_posts')[0]
    assert doc.source_type == 'ai_synthetic'
    assert doc.author_id == job['synthetic_lineage_id']
    assert doc.metadata['human_authored'] == 'False'
    second = curate.sample(repo, generator_id='writer-b', sequence=2, parent=repo / job['parent_path'])
    assert second['synthetic_lineage_id'] == job['synthetic_lineage_id']
    assert curate.status(repo)['approved'] == 1


def test_given_private_ancestor_when_copied_then_descendants_remain_ignored(repo):
    source = repo / 'private/source.md'
    source.parent.mkdir()
    source.write_text('Private original observation. ' * 160)
    job = curate.sample(repo, generator_id='writer-a', sequence=1, parent=source, positive_roots=[source.parent])
    accepted = curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])
    assert accepted.parent.name == 'untracked'
    copied = repo / 'blog_posts/copied.md'
    copied.write_text(accepted.read_text())
    subprocess.run(['git', '-C', str(repo), 'add', str(copied)], check=True)
    descendant = curate.sample(repo, generator_id='writer-b', sequence=2, parent=copied)
    assert descendant['lineage_visibility'] == 'untracked'
    output = ' '.join(f'Survey team {i} mapped the coastline before inspecting the harbor.' for i in range(24))
    assert curate.review(repo, descendant['job_id'], output, approve=True, source_fit=FIT, signals=['T13']).parent.name == 'untracked'


def test_given_rejection_when_recorded_then_retry_is_blind_and_no_negative_is_loaded(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    assert curate.review(repo, job['job_id'], BODY, approve=False) == curate.RETRY_PROMPT
    assert load_negative_corpus(repo / 'negative_posts') == []
    assert 'different style and tone' in curate.RETRY_PROMPT
    assert 'T13' not in curate.RETRY_PROMPT and 'signal' not in curate.RETRY_PROMPT
    assert 'SOURCE:' in job['prompt'] and 'signal' not in job['prompt']
    assert json.loads((repo / 'artifacts/ai_negative_generation/reviews.jsonl').read_text())['signals'] == []


@pytest.mark.parametrize('body,signals', [(BODY, []), (BODY, ['T99']), ('too short', ['T13'])])
def test_given_missing_review_or_bad_content_when_approved_then_admission_fails(repo, body, signals):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    with pytest.raises(ValueError):
        curate.review(repo, job['job_id'], body, approve=True, source_fit=FIT, signals=signals)
    assert load_negative_corpus(repo / 'negative_posts') == []


def test_given_copied_source_or_changed_parent_when_approved_then_admission_fails(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    with pytest.raises(ValueError, match='cop'):
        curate.review(repo, job['job_id'], job['excerpt'], approve=True, source_fit=FIT, signals=['T13'])
    (repo / job['parent_path']).write_text('Changed source')
    with pytest.raises(ValueError, match='changed'):
        curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])


def test_given_tampered_visibility_when_approved_then_provenance_is_recomputed(repo):
    source = repo / 'private/source.md'
    source.parent.mkdir()
    source.write_text('Original private research. ' * 100)
    job = curate.sample(repo, generator_id='writer-a', sequence=1, parent=source, positive_roots=[source.parent])
    record = repo / 'artifacts/ai_negative_generation/jobs' / (job['job_id'] + '.json')
    data = json.loads(record.read_text()); data['lineage_visibility'] = 'tracked'
    record.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='provenance'):
        curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])


def test_given_completed_job_when_reviewed_twice_then_it_is_refused(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])
    with pytest.raises(ValueError):
        curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])


def test_given_same_sequence_when_sampled_again_then_selection_is_reproducible(repo):
    first = curate.sample(repo, generator_id='writer-a', sequence=7)
    second = curate.sample(repo, generator_id='writer-a', sequence=7)
    assert first == second
    assert 300 <= len(first['excerpt'].split()) <= 600
    assert not any(term in first['prompt'] for term in ('T01', 'AI tell', 'acceptance', 'review'))


def test_given_unknown_generator_or_oversized_output_when_admitted_then_it_is_refused(repo):
    with pytest.raises(ValueError):
        curate.sample(repo, generator_id='', sequence=1)
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    with pytest.raises(ValueError):
        curate.review(repo, job['job_id'], BODY * 4, approve=True, source_fit=FIT, signals=['T13'])


def test_given_five_rejections_when_reviewed_then_rotation_is_required(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    for _ in range(5):
        curate.review(repo, job['job_id'], BODY, approve=False)
    with pytest.raises(ValueError, match='generator'):
        curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])
    curate.rotate(repo, job['job_id'], 'writer-b')
    assert curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13']).exists()


def test_given_twenty_accepted_roots_when_sampled_again_then_lineage_cap_is_enforced(repo):
    first = curate.sample(repo, generator_id='writer-a', sequence=1)
    source = repo / first['parent_path']
    for sequence in range(1, 21):
        job = curate.sample(repo, generator_id='writer-a', sequence=sequence, parent=source)
        curate.review(repo, job['job_id'], BODY + f' Calibration round {sequence}.', approve=True, source_fit=FIT, signals=['T13'])
    with pytest.raises(ValueError, match='20'):
        curate.sample(repo, generator_id='writer-a', sequence=21, parent=source)


def test_given_unresolvable_synthetic_ancestry_when_sampled_then_it_cannot_be_tracked(repo):
    source = repo / 'blog_posts/forged.md'
    source.write_text('---\nsource_type: ai_synthetic\nhuman_authored: false\n'
                      'synthetic_lineage_id: synthetic-lineage-abcdef123456\nlineage_visibility: tracked\n'
                      'synthetic_parent_id: missing\nsynthetic_parent_sha256: ' + 'a'*64 + '\n---\n' + BODY)
    subprocess.run(['git', '-C', str(repo), 'add', str(source)], check=True)
    with pytest.raises(ValueError, match='provenance'):
        curate.sample(repo, generator_id='writer-a', sequence=1, parent=source, positive_roots=[source.parent])


def test_given_redirected_destination_when_approved_then_it_is_refused(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    destination = repo / 'negative_posts/ai'
    destination.mkdir(parents=True)
    elsewhere = repo / 'redirected'
    elsewhere.mkdir()
    (destination / 'tracked').symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(ValueError, match='destination'):
        curate.review(repo, job['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])


def test_given_existing_sequence_and_same_named_different_source_when_sampled_then_it_is_refused(repo):
    original = repo / 'blog_posts/0.md'
    curate.sample(repo, generator_id='writer-a', sequence=1, parent=original)
    other = repo / 'private/0.md'
    other.parent.mkdir(); other.write_text('Some other source prose. ' * 100)
    with pytest.raises(ValueError):
        curate.sample(repo, generator_id='writer-a', sequence=1, parent=other)


def test_given_human_negative_root_when_selected_as_parent_then_generation_is_refused(repo):
    source = repo / 'negative_posts/other.md'
    source.parent.mkdir()
    source.write_text('An alternative writer discusses unrelated laboratory experiments. ' * 100)
    subprocess.run(['git', '-C', str(repo), 'add', str(source)], check=True)
    with pytest.raises(ValueError, match='positive'):
        curate.sample(repo, generator_id='writer-a', sequence=1, parent=source)


def test_given_configured_positive_roots_when_sampled_then_email_roots_are_available(repo):
    source = repo / 'private/source.txt'
    source.parent.mkdir(); source.write_text('Original correspondence about the work. ' * 100)
    job = curate.sample(repo, generator_id='writer-a', sequence=1, positive_roots=[source.parent])
    assert job['parent_path'] == 'private/source.txt'
    assert job['lineage_visibility'] == 'untracked'


def test_given_a_previously_private_root_when_later_added_to_git_then_lineage_stays_untracked(repo):
    source = repo / 'private/source.md'
    source.parent.mkdir(); source.write_text('Original private observations about data processing. ' * 100)
    first = curate.sample(repo, generator_id='writer-a', sequence=1, parent=source, positive_roots=[source.parent])
    curate.review(repo, first['job_id'], BODY, approve=True, source_fit=FIT, signals=['T13'])
    ignore = repo / '.gitignore'
    ignore.write_text(ignore.read_text().replace('private/\n', ''))
    subprocess.run(['git', '-C', str(repo), 'add', '--force', str(source)], check=True)
    next_job = curate.sample(repo, generator_id='writer-b', sequence=2, parent=source, positive_roots=[source.parent])
    assert next_job['lineage_visibility'] == 'untracked'


def test_given_an_ignored_source_forced_into_git_when_sampled_then_it_is_still_private(repo):
    source = repo / 'private/source.md'
    source.parent.mkdir(); source.write_text('Private observations from a local message. ' * 100)
    subprocess.run(['git', '-C', str(repo), 'add', '--force', str(source)], check=True)
    job = curate.sample(repo, generator_id='writer-a', sequence=1, parent=source, positive_roots=[source.parent])
    assert job['lineage_visibility'] == 'untracked'


def test_given_signal_without_source_fit_when_approved_then_admission_fails(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    with pytest.raises(ValueError, match='source fit'):
        curate.review(repo, job['job_id'], BODY, approve=True, signals=['T16'])


@pytest.mark.parametrize('field', ['medium', 'audience', 'purpose', 'specificity'])
def test_given_failed_fit_dimension_when_approved_then_admission_fails(repo, field):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    fit = dict(medium='Research blog prose', audience='Technical readers', purpose='Reports an experiment', specificity='Concrete observations')
    fit[field] = ''
    with pytest.raises(ValueError, match='source fit'):
        curate.review(repo, job['job_id'], BODY, approve=True, signals=['T16'], source_fit=fit)


def test_given_fit_review_when_approved_then_evidence_stays_local(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    fit = dict(medium='Research blog prose', audience='Technical readers', purpose='Reports an experiment', specificity='Concrete observations')
    path = curate.review(repo, job['job_id'], BODY, approve=True, signals=['T16'], source_fit=fit)
    assert curate.records(repo)[-1]['source_fit'] == fit
    assert 'source_fit' not in path.read_text()


def test_given_neutral_prompt_when_sampled_then_requires_actual_source_function(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    assert 'same medium, audience, and communicative purpose' in job['prompt']
    assert 'actual message or document' in job['prompt']
    assert 'AI tell' not in job['prompt']


def test_given_legacy_approval_without_fit_when_status_checked_then_review_is_incomplete(repo):
    job = curate.sample(repo, generator_id='writer-a', sequence=1)
    curate.review(repo, job['job_id'], BODY, approve=True, signals=['T16'], source_fit=FIT)
    log = repo / 'artifacts/ai_negative_generation/reviews.jsonl'
    row = json.loads(log.read_text()); row.pop('source_fit'); log.write_text(json.dumps(row)+'\n')
    assert curate.status(repo)['source_fit_reviewed'] is False
    assert not curate.status(repo)['complete']
