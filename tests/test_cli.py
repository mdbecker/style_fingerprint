import json


def test_given_cli_when_built_scored_explained_evaluated_then_all_four_commands_work(corpus, encoder, tmp_path, capsys):
    from style_fingerprint.cli import main
    artifacts = tmp_path / 'artifacts'
    assert main(['build', '--no-holdout','--corpus',str(corpus),'--artifacts',str(artifacts)]) == 0
    capsys.readouterr()
    file = corpus / 'post-0.markdown'
    assert main(['score',str(file),'--artifacts',str(artifacts)]) == 0
    compact = capsys.readouterr().out
    assert 'Style compatibility:' in compact and 'Evidence strength:' in compact
    assert 'Historical analogues' not in compact
    assert main(['explain',str(file),'--artifacts',str(artifacts)]) == 0
    detailed = capsys.readouterr().out
    assert 'Strongest matches' in detailed and 'Largest mismatches' in detailed
    assert 'Historical analogues' in detailed
    assert main(['evaluate','--artifacts',str(artifacts),'--json']) == 0
    assert len(json.loads(capsys.readouterr().out)['folds']) == 6


def test_given_invalid_cli_input_when_scored_then_actionable_failure(tmp_path, capsys):
    from style_fingerprint.cli import main
    assert main(['score','missing.md','--artifacts',str(tmp_path)]) == 1
    assert 'Error:' in capsys.readouterr().err
