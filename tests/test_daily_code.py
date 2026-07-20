import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.daily_code import DEFAULT_DAILY_CODE_ENDPOINT, DailyCode
from fifa_panini.commands.try_code import CodeResponse


class DailyCodeTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.tmp_path = Path(self.tempdir.name)

    def write_config(self, content=''):
        config = self.tmp_path / 'config.toml'
        config.write_text(content)
        return config

    def test_cli_exposes_command(self):
        config = self.write_config()
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

        with patch('fifa_panini.commands.daily_code.urlopen', fake_urlopen):
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

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'Response headers:\nContent-Type: application/json\nResponse text:\n{"code":"daily26pack"}\n',
        )
        request, timeout = requests[0]
        self.assertEqual(request.full_url, DEFAULT_DAILY_CODE_ENDPOINT)
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.get_header('Cookie'), 'session=value')
        self.assertEqual(timeout, 30.0)

    def test_hides_unused_flags(self):
        result = CliRunner().invoke(CLI.click, ['daily-code', '--help'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('--cookie', result.output)
        self.assertNotIn('--endpoint', result.output)
        self.assertNotIn('--dry-run', result.output)
        self.assertNotIn('--timeout', result.output)
        self.assertNotIn('--env', result.output)

    def test_fetches_current_code(self):
        command = DailyCode(
            cookie='session=value',
        )
        calls = 0

        def fake_send_code():
            nonlocal calls
            calls += 1
            return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

        with patch.object(command, 'send_code', fake_send_code):
            command()

        self.assertEqual(calls, 1)

    def test_loads_settings_from_config(self):
        config = self.write_config(
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

        with patch('fifa_panini.commands.daily_code.urlopen', fake_urlopen):
            result = CliRunner().invoke(CLI.click, ['--config', str(config), 'daily-code'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'Response headers:\nContent-Type: application/json\nResponse text:\n{"code":"daily26pack"}\n',
        )
        self.assertEqual(requests[0][0].get_header('Cookie'), 'session=value')

    def test_requires_cookie(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'daily-code',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Missing required setting(s): cookie', result.output)

    def test_rejects_cookie_with_unicode_ellipsis(self):
        config = self.write_config()

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

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(r'Cookie contains \u2026', result.output)
