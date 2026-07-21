import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.claim import CLAIM_PACKS_BODY, Claim
from fifa_panini.commands.panini import API_ENDPOINT

GOOD_CLAIM_RESPONSE_TEXT = (
    '[{"action":"receive_daily_packs"},'
    '{"amount":2,"from_entered_code":false,"was_premium_code":false,"total_packs":52,"action":"received_packs"},'
    '{"new_packs_in_sec":68779,"has_new_packs_waiting":false,"action":"daily_packs_status"},'
    '{"has_new_challenge":false,"has_just_completed_challenge":false,"num_available_challenges":1,'
    '"action":"challenge_summary"}]'
)
BAD_CLAIM_RESPONSE_TEXT = (
    '[{"action":"receive_daily_packs"},'
    '{"error":{"message":"no_packs"},"action":"receive_daily_packs"},'
    '{"new_packs_in_sec":68705,"has_new_packs_waiting":false,"action":"daily_packs_status"},'
    '{"has_new_challenge":false,"has_just_completed_challenge":false,"num_available_challenges":1,'
    '"action":"challenge_summary"}]'
)
FIXED_TIME = dt.datetime(2026, 7, 21, 12, 0, 0, tzinfo=dt.timezone.utc)


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class ClaimTestCase(unittest.TestCase):
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
                return GOOD_CLAIM_RESPONSE_TEXT.encode()

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with (
            patch('fifa_panini.commands.claim.urlopen', fake_urlopen),
            patch.object(Claim, 'current_time', staticmethod(lambda: FIXED_TIME)),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'claim',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'Claimed packs: 2\nTotal packs: 52\nNew packs available at: 2026-07-22 07:06:19 UTC\n',
        )
        request, timeout = requests[0]
        self.assertEqual(request.full_url, 'https://paninicollection.fifa.com/api/receive_daily_packs.json')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.data, CLAIM_PACKS_BODY)
        self.assertEqual(request.get_header('Cookie'), 'session=value')
        self.assertEqual(request.get_header('Content-type'), 'application/x-www-form-urlencoded')
        self.assertEqual(timeout, 30.0)

    def test_dry_run_prints_request(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=value',
                '--api-endpoint',
                'https://example.test/api/',
                'claim',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'DRY RUN POST https://example.test/api/receive_daily_packs.json json={}\n',
        )

    def test_loads_cookie_from_panini_config(self):
        config = self.write_config('[panini]\ncookie = "session=value"\n')
        requests = []

        class FakeResponse:
            headers = {'Content-Type': 'application/json'}

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc_value, _traceback):
                return False

            def read(self):
                return GOOD_CLAIM_RESPONSE_TEXT.encode()

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with (
            patch('fifa_panini.commands.claim.urlopen', fake_urlopen),
            patch.object(Claim, 'current_time', staticmethod(lambda: FIXED_TIME)),
        ):
            result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'claim'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(requests[0][0].get_header('Cookie'), 'session=value')

    def test_prints_claim_summary_for_success_response(self):
        config = self.write_config()

        with (
            patch.object(Claim, 'claim_packs', lambda _self: ClaimResponseStub(GOOD_CLAIM_RESPONSE_TEXT)),
            patch.object(Claim, 'current_time', staticmethod(lambda: FIXED_TIME)),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'claim',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'Claimed packs: 2\nTotal packs: 52\nNew packs available at: 2026-07-22 07:06:19 UTC\n',
        )
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(GOOD_CLAIM_RESPONSE_TEXT, result.output)

    def test_raises_click_exception_for_error_response(self):
        config = self.write_config()

        with (
            patch.object(Claim, 'claim_packs', lambda _self: ClaimResponseStub(BAD_CLAIM_RESPONSE_TEXT)),
            patch.object(Claim, 'current_time', staticmethod(lambda: FIXED_TIME)),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'claim',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: no_packs. New packs available at: 2026-07-22 07:05:05 UTC\n')
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(BAD_CLAIM_RESPONSE_TEXT, result.output)

    def test_requires_cookie(self):
        config = self.write_config()

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'claim'])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Missing required setting(s): cookie', result.output)

    def test_rejects_cookie_with_unicode_ellipsis(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=abc\u2026',
                'claim',
                '--dry-run',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(r'Cookie contains \u2026', result.output)

    def test_sends_claim_request(self):
        command = Claim(**panini_settings(cookie='session=value'))
        requests = []

        class FakeResponse:
            headers = {'Content-Type': 'application/json'}

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc_value, _traceback):
                return False

            def read(self):
                return b'{"claimed":true}'

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with patch('fifa_panini.commands.claim.urlopen', fake_urlopen):
            response = command.claim_packs()

        self.assertEqual(response.text, '{"claimed":true}')
        self.assertEqual(response.headers, {'Content-Type': 'application/json'})
        self.assertEqual(requests[0][0].full_url, 'https://paninicollection.fifa.com/api/receive_daily_packs.json')
        self.assertEqual(requests[0][0].data, b'json=%7b%7d&locale=en')


class ClaimResponseStub:
    def __init__(self, text):
        self.text = text
        self.headers = {'Content-Type': 'application/json'}
