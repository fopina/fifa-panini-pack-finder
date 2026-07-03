from click.testing import CliRunner

from fifa_panini.cli import CLI, DEFAULT_STATE_FILE, TryCode


def test_try_code_formats_four_digit_suffixes():
    command = TryCode(code_base='ABC-', cookie='session=value')

    assert command.format_code(42) == 'ABC-0042'


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
            'ABC-',
        ],
    )

    assert result.exit_code == 0
    assert result.output == 'DRY RUN POST https://example.test/redeem code=ABC-0000\n'


def test_try_code_resumes_from_state_file(tmp_path):
    state_file = tmp_path / 'state.json'
    state_file.write_text('{"code_base": "ABC-", "current_code": "ABC-0041", "next_suffix": 42}\n')
    command = TryCode(code_base='ABC-', cookie='session=value', state_file=state_file)

    assert command.next_code() == 'ABC-0042'


def test_try_code_stops_when_response_is_not_invalid(tmp_path, monkeypatch):
    attempts = []
    command = TryCode(
        code_base='ABC-',
        cookie='session=value',
        dry_run=False,
        state_file=tmp_path / 'state.json',
        config=tmp_path / 'config.toml',
    )
    command.config.write_text('')

    def fake_send_code(code):
        attempts.append(code)
        if len(attempts) == 1:
            return '{"error":"code.invalid"}'
        return '{"ok":true}'

    monkeypatch.setattr(command, 'send_code', fake_send_code)
    monkeypatch.setattr('fifa_panini.cli.time.sleep', lambda _seconds: None)

    command()

    assert attempts == ['ABC-0000', 'ABC-0001']


def test_try_code_loads_settings_from_config(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text(
        '\n'.join(
            [
                'code_base = "ABC-"',
                'cookie = "session=value"',
                'endpoint = "https://example.test/redeem"',
                f'state_file = "{tmp_path / "state.json"}"',
            ]
        )
    )

    result = CliRunner().invoke(CLI.click, ['try-code', '--config', str(config), '--dry-run'])

    assert result.exit_code == 0
    assert result.output == 'DRY RUN POST https://example.test/redeem code=ABC-0000\n'


def test_default_state_file_sits_next_to_config_file(tmp_path, monkeypatch):
    config = tmp_path / 'settings' / 'config.toml'
    config.parent.mkdir()
    config.write_text('code_base = "ABC-"\ncookie = "session=value"\n')

    attempts = []

    def fake_send_code(self, code):
        attempts.append(code)
        return '{"ok":true}'

    monkeypatch.setattr(TryCode, 'send_code', fake_send_code)

    result = CliRunner().invoke(CLI.click, ['try-code', '--config', str(config)])

    assert result.exit_code == 0
    assert attempts == ['ABC-0000']
    assert (config.parent / DEFAULT_STATE_FILE).exists()


def test_config_command_masks_cookie(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('code_base = "ABC-"\ncookie = "session=value"\n')

    result = CliRunner().invoke(CLI.click, ['config', '--config', str(config)])

    assert result.exit_code == 0
    assert '"cookie": "<masked>"' in result.output
