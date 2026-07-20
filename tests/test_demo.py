import click
import pytest
from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.bf_code import BfCode
from fifa_panini.commands.daily_code import DEFAULT_DAILY_CODE_ENDPOINT, DailyCode
from fifa_panini.commands.try_code import DEFAULT_STATE_FILE, TOTAL_SUFFIXES, CodeResponse, TryCode


def test_bf_code_formats_four_character_suffixes():
    command = BfCode(code_base='ABCD-EFGH-IJKL', cookie='session=value')

    assert command.format_code(0) == 'ABCD-EFGH-AAAA'
    assert command.format_code(35) == 'ABCD-EFGH-AAA9'
    assert command.format_code(42) == 'ABCD-EFGH-AABG'


def test_bf_code_rejects_invalid_code_base(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('')

    result = CliRunner().invoke(
        CLI.click,
        [
            '--config',
            str(config),
            'bf-code',
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
            '--config',
            str(config),
            'try-code',
            '--dry-run',
            '--cookie',
            'session=value',
            '--endpoint',
            'https://example.test/redeem',
            '--code',
            'ABCD-EFGH-IJKL',
        ],
    )

    assert result.exit_code == 0
    assert result.output == 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-IJKL\n'


def test_cli_exposes_bf_code_command(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('')

    result = CliRunner().invoke(
        CLI.click,
        [
            '--config',
            str(config),
            'bf-code',
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


def test_bf_code_resumes_from_state_file(tmp_path):
    state_file = tmp_path / 'state.json'
    state_file.write_text('{"code_base": "ABCD-EFGH-IJKL", "current_code": "ABCD-EFGH-AABF", "next_suffix": 42}\n')
    command = BfCode(code_base='ABCD-EFGH-IJKL', cookie='session=value', state_file=state_file)

    assert command.next_code() == 'ABCD-EFGH-AABG'


def test_bf_code_progress_resumes_from_saved_suffix(tmp_path, monkeypatch):
    state_file = tmp_path / 'state.json'
    state_file.write_text('{"code_base": "ABCD-EFGH-IJKL", "current_code": "ABCD-EFGH-AABF", "next_suffix": 42}\n')
    progress_kwargs = {}

    class FakeProgress:
        def __init__(self, **kwargs):
            progress_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc_value, _traceback):
            return False

        def set_description(self, _description):
            pass

        def update(self):
            pass

        @staticmethod
        def write(*_args, **_kwargs):
            pass

    command = BfCode(
        code_base='ABCD-EFGH-IJKL',
        cookie='session=value',
        dry_run=False,
        state_file=state_file,
    )

    monkeypatch.setattr('fifa_panini.commands.bf_code.tqdm', FakeProgress)
    monkeypatch.setattr(
        command,
        'send_code',
        lambda code: CodeResponse(
            text='{"error":"code.already_used"}' if code == command.code_base else '{"ok":true}',
            headers={'Content-Type': 'application/json'},
        ),
    )

    command()

    assert progress_kwargs['total'] == TOTAL_SUFFIXES
    assert progress_kwargs['initial'] == 42
    assert progress_kwargs['unit'] == 'code'


def test_try_code_sends_only_passed_code(tmp_path, monkeypatch):
    attempts = []
    command = TryCode(
        code='ABCD-EFGH-IJKL',
        cookie='session=value',
        dry_run=False,
    )

    def fake_send_code(code):
        attempts.append(code)
        return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

    monkeypatch.setattr(command, 'send_code', fake_send_code)

    command()

    assert attempts == ['ABCD-EFGH-IJKL']


def test_bf_code_stops_when_response_is_not_invalid(tmp_path, monkeypatch):
    attempts = []
    command = BfCode(
        code_base='ABCD-EFGH-IJKL',
        cookie='session=value',
        dry_run=False,
        state_file=tmp_path / 'state.json',
    )

    def fake_send_code(code):
        attempts.append(code)
        if code == command.code_base:
            return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
        if len(attempts) == 2:
            return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
        return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json', 'X-Pack': 'found'})

    monkeypatch.setattr(command, 'send_code', fake_send_code)
    monkeypatch.setattr('fifa_panini.commands.bf_code.time.sleep', lambda _seconds: None)

    command()

    assert attempts == ['ABCD-EFGH-IJKL', 'ABCD-EFGH-AAAA', 'ABCD-EFGH-AAAB']


def test_bf_code_fails_when_code_base_is_not_already_used(tmp_path, monkeypatch):
    attempts = []
    command = BfCode(
        code_base='ABCD-EFGH-IJKL',
        cookie='session=value',
        dry_run=False,
        state_file=tmp_path / 'state.json',
    )

    def fake_send_code(code):
        attempts.append(code)
        return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})

    monkeypatch.setattr(command, 'send_code', fake_send_code)

    with pytest.raises(click.ClickException) as error:
        command()

    assert attempts == ['ABCD-EFGH-IJKL']
    assert 'Code base check failed for ABCD-EFGH-IJKL' in str(error.value)
    assert '"code.already_used"' in str(error.value)


def test_bf_code_uses_configured_request_delay(tmp_path, monkeypatch):
    attempts = []
    sleeps = []
    command = BfCode(
        code_base='ABCD-EFGH-IJKL',
        cookie='session=value',
        dry_run=False,
        request_delay=0.25,
        state_file=tmp_path / 'state.json',
    )

    def fake_send_code(code):
        attempts.append(code)
        if code == command.code_base:
            return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
        if len(attempts) == 2:
            return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
        return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

    monkeypatch.setattr(command, 'send_code', fake_send_code)
    monkeypatch.setattr('fifa_panini.commands.bf_code.time.sleep', sleeps.append)

    command()

    assert sleeps == [0.25]


def test_bf_code_skips_request_delay_when_zero(tmp_path, monkeypatch):
    attempts = []
    sleeps = []
    command = BfCode(
        code_base='ABCD-EFGH-IJKL',
        cookie='session=value',
        dry_run=False,
        request_delay=0,
        state_file=tmp_path / 'state.json',
    )

    def fake_send_code(code):
        attempts.append(code)
        if code == command.code_base:
            return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
        if len(attempts) == 2:
            return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
        return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

    monkeypatch.setattr(command, 'send_code', fake_send_code)
    monkeypatch.setattr('fifa_panini.commands.bf_code.time.sleep', sleeps.append)

    command()

    assert sleeps == []


def test_bf_code_rejects_negative_request_delay(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('')

    result = CliRunner().invoke(
        CLI.click,
        [
            '--config',
            str(config),
            'bf-code',
            '--dry-run',
            '--cookie',
            'session=value',
            '--code-base',
            'ABCD-EFGH-IJKL',
            '--request-delay=-1',
        ],
    )

    assert result.exit_code != 0
    assert '--request-delay must be greater than or equal to 0' in result.output


def test_try_code_rejects_cookie_with_unicode_ellipsis(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('')

    result = CliRunner().invoke(
        CLI.click,
        [
            '--config',
            str(config),
            'try-code',
            '--dry-run',
            '--cookie',
            'session=abc\u2026',
            '--code',
            'ABCD-EFGH-IJKL',
        ],
    )

    assert result.exit_code != 0
    assert r'Cookie contains \u2026' in result.output


def test_try_code_loads_settings_from_config(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text(
        '\n'.join(
            [
                '[try-code]',
                'code = "ABCD-EFGH-IJKL"',
                'cookie = "session=value"',
                'endpoint = "https://example.test/redeem"',
            ]
        )
    )

    result = CliRunner().invoke(CLI.click, ['--config', str(config), 'try-code', '--dry-run'])

    assert result.exit_code == 0
    assert result.output == 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-IJKL\n'


def test_bf_code_loads_settings_from_config(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text(
        '\n'.join(
            [
                '[bf-code]',
                'code_base = "ABCD-EFGH-IJKL"',
                'cookie = "session=value"',
                'endpoint = "https://example.test/redeem"',
                f'state_file = "{tmp_path / "state.json"}"',
                'request_delay = 0',
            ]
        )
    )

    result = CliRunner().invoke(CLI.click, ['--config', str(config), 'bf-code', '--dry-run'])

    assert result.exit_code == 0
    assert result.output == 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-AAAA\n'


def test_default_state_file_sits_next_to_config_file(tmp_path, monkeypatch):
    config = tmp_path / 'settings' / 'config.toml'
    config.parent.mkdir()
    config.write_text('[bf-code]\ncode_base = "ABCD-EFGH-IJKL"\ncookie = "session=value"\n')

    attempts = []

    def fake_send_code(self, code):
        attempts.append(code)
        if code == self.code_base:
            return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
        return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

    monkeypatch.setattr(BfCode, 'send_code', fake_send_code)

    result = CliRunner().invoke(CLI.click, ['--config', str(config), 'bf-code'])

    assert result.exit_code == 0
    assert attempts == ['ABCD-EFGH-IJKL', 'ABCD-EFGH-AAAA']
    assert 'Response headers:\nContent-Type: application/json\nResponse text:\n{"ok":true}\n' in result.output
    assert (config.parent / DEFAULT_STATE_FILE).exists()


def test_config_command_masks_cookie(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[bf-code]\ncode_base = "ABCD-EFGH-IJKL"\ncookie = "session=value"\n')

    result = CliRunner().invoke(CLI.click, ['--config', str(config), 'config'])

    assert result.exit_code == 0
    assert '"cookie": "<masked>"' in result.output


def test_cli_exposes_daily_code_command(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    config.write_text('')
    requests = []

    class FakeResponse:
        headers = {'Content-Type': 'application/json'}

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc_value, _traceback):
            return False

        def read(self):
            return b'{"code":"daily26pack"}'

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr('fifa_panini.commands.daily_code.urlopen', fake_urlopen)

    result = CliRunner().invoke(
        CLI.click,
        [
            '--config',
            str(config),
            'daily-code',
            '--cookie',
            'session=value',
        ],
    )

    assert result.exit_code == 0
    assert result.output == 'Response headers:\nContent-Type: application/json\nResponse text:\n{"code":"daily26pack"}\n'
    request, timeout = requests[0]
    assert request.full_url == DEFAULT_DAILY_CODE_ENDPOINT
    assert request.get_method() == 'GET'
    assert request.get_header('Cookie') == 'session=value'
    assert timeout == 30.0


def test_daily_code_hides_unused_flags():
    result = CliRunner().invoke(CLI.click, ['daily-code', '--help'])

    assert result.exit_code == 0
    assert '--cookie' in result.output
    assert '--endpoint' not in result.output
    assert '--dry-run' not in result.output
    assert '--timeout' not in result.output
    assert '--env' not in result.output


def test_daily_code_fetches_current_code(monkeypatch):
    command = DailyCode(
        cookie='session=value',
    )
    calls = 0

    def fake_send_code():
        nonlocal calls
        calls += 1
        return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

    monkeypatch.setattr(command, 'send_code', fake_send_code)

    command()

    assert calls == 1


def test_daily_code_loads_settings_from_config(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    config.write_text(
        '\n'.join(
            [
                '[daily-code]',
                'cookie = "session=value"',
            ]
        )
    )
    requests = []

    class FakeResponse:
        headers = {'Content-Type': 'application/json'}

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc_value, _traceback):
            return False

        def read(self):
            return b'{"code":"daily26pack"}'

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr('fifa_panini.commands.daily_code.urlopen', fake_urlopen)

    result = CliRunner().invoke(CLI.click, ['--config', str(config), 'daily-code'])

    assert result.exit_code == 0
    assert result.output == 'Response headers:\nContent-Type: application/json\nResponse text:\n{"code":"daily26pack"}\n'
    assert requests[0][0].get_header('Cookie') == 'session=value'


def test_daily_code_requires_cookie(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('')

    result = CliRunner().invoke(
        CLI.click,
        [
            '--config',
            str(config),
            'daily-code',
        ],
    )

    assert result.exit_code != 0
    assert 'Missing required setting(s): cookie' in result.output


def test_daily_code_rejects_cookie_with_unicode_ellipsis(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('')

    result = CliRunner().invoke(
        CLI.click,
        [
            '--config',
            str(config),
            'daily-code',
            '--cookie',
            'session=abc\u2026',
        ],
    )

    assert result.exit_code != 0
    assert r'Cookie contains \u2026' in result.output
