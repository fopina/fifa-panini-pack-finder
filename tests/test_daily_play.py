import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.daily_play import DEFAULT_DAILY_PLAY_ENDPOINT, DailyPlay
from fifa_panini.commands.try_code import CodeResponse

GOOD_DAILY_PLAY_RESPONSE_TEXT = (
    '{"success":{"paniniCode":{"code":"2CVJ-81ZE-91MT",'
    '"usedAt":"2026-07-21T10:49:12+01:00","isNew":false}},"errors":[]}'
)
ERROR_DAILY_PLAY_RESPONSE_TEXT = '{"success":{},"errors":["daily.code_unavailable",{"message":"try later"}]}'


class DailyPlayTestCase(unittest.TestCase):
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
                return GOOD_DAILY_PLAY_RESPONSE_TEXT.encode()

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with patch('fifa_panini.commands.daily_play.urlopen', fake_urlopen):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'daily-play',
                    '--cookie',
                    'session=value',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '2CVJ-81ZE-91MT\n',
        )
        request, timeout = requests[0]
        self.assertEqual(request.full_url, DEFAULT_DAILY_PLAY_ENDPOINT)
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.get_header('Cookie'), 'session=value')
        self.assertEqual(timeout, 30.0)

    def test_hides_unused_flags(self):
        result = CliRunner().invoke(CLI.click, ['daily-play', '--help'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('--cookie', result.output)
        self.assertNotIn('--api-endpoint', result.output)
        self.assertNotIn('--dry-run', result.output)
        self.assertNotIn('--timeout', result.output)
        self.assertNotIn('--env', result.output)

    def test_fetches_current_code(self):
        command = DailyPlay(
            cookie='session=value',
        )
        calls = 0

        def fake_send_code():
            nonlocal calls
            calls += 1
            return CodeResponse(text=GOOD_DAILY_PLAY_RESPONSE_TEXT, headers={'Content-Type': 'application/json'})

        with patch.object(command, 'send_code', fake_send_code):
            command()

        self.assertEqual(calls, 1)

    def test_loads_settings_from_config(self):
        config = self.write_config(
            '\n'.join(
                [
                    '[daily-play]',
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
                return GOOD_DAILY_PLAY_RESPONSE_TEXT.encode()

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with patch('fifa_panini.commands.daily_play.urlopen', fake_urlopen):
            result = CliRunner().invoke(CLI.click, ['--config', str(config), 'daily-play'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '2CVJ-81ZE-91MT\n',
        )
        self.assertEqual(requests[0][0].get_header('Cookie'), 'session=value')

    def test_prints_only_code_for_success_response(self):
        config = self.write_config()

        with patch.object(
            DailyPlay,
            'send_code',
            lambda _self: CodeResponse(
                text=GOOD_DAILY_PLAY_RESPONSE_TEXT, headers={'Content-Type': 'application/json'}
            ),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'daily-play',
                    '--cookie',
                    'session=value',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, '2CVJ-81ZE-91MT\n')
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(GOOD_DAILY_PLAY_RESPONSE_TEXT, result.output)

    def test_raises_click_exception_for_error_response(self):
        config = self.write_config()

        with patch.object(
            DailyPlay,
            'send_code',
            lambda _self: CodeResponse(
                text=ERROR_DAILY_PLAY_RESPONSE_TEXT, headers={'Content-Type': 'application/json'}
            ),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'daily-play',
                    '--cookie',
                    'session=value',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response errors: daily.code_unavailable, {"message":"try later"}\n')
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(ERROR_DAILY_PLAY_RESPONSE_TEXT, result.output)

    def test_raises_click_exception_when_code_is_missing(self):
        config = self.write_config()

        for response_text in (
            '{"success":{"paniniCode":{}},"errors":[]}',
            '{"success":{"paniniCode":{"code":null}},"errors":[]}',
            '{"success":{"paniniCode":{"code":""}},"errors":[]}',
            '{"success":{},"errors":[]}',
        ):
            with self.subTest(response_text=response_text):
                with patch.object(
                    DailyPlay,
                    'send_code',
                    lambda _self, response_text=response_text: CodeResponse(
                        text=response_text,
                        headers={'Content-Type': 'application/json'},
                    ),
                ):
                    result = CliRunner().invoke(
                        CLI.click,
                        [
                            '--config',
                            str(config),
                            'daily-play',
                            '--cookie',
                            'session=value',
                        ],
                    )

                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(result.output, 'Error: Response did not include a daily promo code.\n')
                self.assertNotIn('Response headers:', result.output)
                self.assertNotIn('Response text:', result.output)

    def test_raises_click_exception_when_response_is_not_json(self):
        config = self.write_config()

        with patch.object(
            DailyPlay,
            'send_code',
            lambda _self: CodeResponse(text='not json', headers={'Content-Type': 'application/json'}),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'daily-play',
                    '--cookie',
                    'session=value',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Response was not valid JSON', result.output)

    def test_requires_cookie(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'daily-play',
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
                'daily-play',
                '--cookie',
                'session=abc\u2026',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(r'Cookie contains \u2026', result.output)
