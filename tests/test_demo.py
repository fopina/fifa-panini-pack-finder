from click.testing import CliRunner

from fifa_panini.cli import CLI, DEFAULT_STATE_FILE, CodeResponse, TryCode


def test_try_code_formats_four_character_suffixes():
    command = TryCode(code_base='ABCD-EFGH-IJKL', cookie='session=value')

    assert command.format_code(0) == 'ABCD-EFGH-AAAA'
    assert command.format_code(35) == 'ABCD-EFGH-AAA9'
    assert command.format_code(42) == 'ABCD-EFGH-AABG'


def test_try_code_rejects_invalid_code_base(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('')

    result = CliRunner().invoke(
        CLI.click,
        [
            'try-code',
            '--config',
            str(config),
            '--dry-run',
            '--cookie',
            'session=value',
            '--code-base',
            'ABCD-EFGH-ijkl',
        ],
    )

    assert result.exit_code != 0
    assert '--code-base must be in XXXX-XXXX-XXXX format' in result.output


def test_cli_exposes_try_code_command(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('')

    result = CliRunner().invoke(
        CLI.click,
        [
            'try-code',
            '--config',
            str(config),
            '--dry-run',
            '--cookie',
            'session=value',
            '--endpoint',
            'https://example.test/redeem',
            '--code-base',
            'ABCD-EFGH-IJKL',
        ],
    )

    assert result.exit_code == 0
    assert result.output == 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-AAAA\n'


def test_try_code_resumes_from_state_file(tmp_path):
    state_file = tmp_path / 'state.json'
    state_file.write_text('{"code_base": "ABCD-EFGH-IJKL", "current_code": "ABCD-EFGH-AABF", "next_suffix": 42}\n')
    command = TryCode(code_base='ABCD-EFGH-IJKL', cookie='session=value', state_file=state_file)

    assert command.next_code() == 'ABCD-EFGH-AABG'


def test_try_code_stops_when_response_is_not_invalid(tmp_path, monkeypatch):
    attempts = []
    command = TryCode(
        code_base='ABCD-EFGH-IJKL',
        cookie='session=value',
        dry_run=False,
        state_file=tmp_path / 'state.json',
        config=tmp_path / 'config.toml',
    )
    command.config.write_text('')

    def fake_send_code(code):
        attempts.append(code)
        if len(attempts) == 1:
            return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
        return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json', 'X-Pack': 'found'})

    monkeypatch.setattr(command, 'send_code', fake_send_code)
    monkeypatch.setattr('fifa_panini.cli.time.sleep', lambda _seconds: None)

    command()

    assert attempts == ['ABCD-EFGH-AAAA', 'ABCD-EFGH-AAAB']


def test_try_code_loads_settings_from_config(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text(
        '\n'.join(
            [
                'code_base = "ABCD-EFGH-IJKL"',
                'cookie = "session=value"',
                'endpoint = "https://example.test/redeem"',
                f'state_file = "{tmp_path / "state.json"}"',
            ]
        )
    )

    result = CliRunner().invoke(CLI.click, ['try-code', '--config', str(config), '--dry-run'])

    assert result.exit_code == 0
    assert result.output == 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-AAAA\n'


def test_default_state_file_sits_next_to_config_file(tmp_path, monkeypatch):
    config = tmp_path / 'settings' / 'config.toml'
    config.parent.mkdir()
    config.write_text('code_base = "ABCD-EFGH-IJKL"\ncookie = "session=value"\n')

    attempts = []

    def fake_send_code(self, code):
        attempts.append(code)
        return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

    monkeypatch.setattr(TryCode, 'send_code', fake_send_code)

    result = CliRunner().invoke(CLI.click, ['try-code', '--config', str(config)])

    assert result.exit_code == 0
    assert attempts == ['ABCD-EFGH-AAAA']
    assert 'Response headers:\nContent-Type: application/json\nResponse text:\n{"ok":true}\n' in result.output
    assert (config.parent / DEFAULT_STATE_FILE).exists()


def test_config_command_masks_cookie(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('code_base = "ABCD-EFGH-IJKL"\ncookie = "session=value"\n')

    result = CliRunner().invoke(CLI.click, ['config', '--config', str(config)])

    assert result.exit_code == 0
    assert '"cookie": "<masked>"' in result.output
