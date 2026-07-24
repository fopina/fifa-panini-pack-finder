import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.panini.claim import CLAIM_PACKS_PATH, Claim
from fifa_panini.utils.panini import API_ENDPOINT

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
    '{"action":"received_packs"},'
    '{"new_packs_in_sec":68705,"has_new_packs_waiting":false,"action":"daily_packs_status"},'
    '{"has_new_challenge":false,"has_just_completed_challenge":false,"num_available_challenges":1,'
    '"action":"challenge_summary"}]'
)
FIXED_TIME = dt.datetime(2026, 7, 21, 12, 0, 0, tzinfo=dt.timezone.utc)


class FixedNow:
    @staticmethod
    def astimezone():
        return FIXED_TIME


class FixedDateTime:
    @staticmethod
    def now():
        return FixedNow()


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
            text = GOOD_CLAIM_RESPONSE_TEXT

        def fake_post(_session, url, data, headers, timeout):
            requests.append((url, data, headers, timeout))
            return FakeResponse()

        with (
            patch('fifa_panini.utils.panini.requests.Session.post', fake_post),
            patch('fifa_panini.commands.panini.claim.dt.datetime', FixedDateTime),
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
        url, data, headers, timeout = requests[0]
        self.assertEqual(url, 'https://paninicollection.fifa.com/api/receive_daily_packs.json')
        self.assertEqual(data, {'json': '{}', 'locale': 'en'})
        self.assertEqual(headers['Cookie'], 'session=value')
        self.assertEqual(headers['Content-Type'], 'application/x-www-form-urlencoded')
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
            text = GOOD_CLAIM_RESPONSE_TEXT

        def fake_post(_session, url, data, headers, timeout):
            requests.append((url, data, headers, timeout))
            return FakeResponse()

        with (
            patch('fifa_panini.utils.panini.requests.Session.post', fake_post),
            patch('fifa_panini.commands.panini.claim.dt.datetime', FixedDateTime),
        ):
            result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'claim'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(requests[0][2]['Cookie'], 'session=value')

    def test_prints_claim_summary_for_success_response(self):
        config = self.write_config()

        with (
            patch(
                'fifa_panini.utils.panini.PaniniClient.post_json',
                lambda _self, *_args, **_kwargs: ClaimResponseStub(GOOD_CLAIM_RESPONSE_TEXT),
            ),
            patch('fifa_panini.commands.panini.claim.dt.datetime', FixedDateTime),
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

    def test_ignores_error_from_unrelated_action(self):
        config = self.write_config()
        response_text = (
            '[{"action":"receive_daily_packs"},'
            '{"amount":2,"total_packs":52,"action":"received_packs"},'
            '{"new_packs_in_sec":68779,"action":"daily_packs_status"},'
            '{"error":{"message":"challenge.failed"},"action":"challenge_summary"}]'
        )

        with (
            patch(
                'fifa_panini.utils.panini.PaniniClient.post_json',
                lambda _self, *_args, **_kwargs: ClaimResponseStub(response_text),
            ),
            patch('fifa_panini.commands.panini.claim.dt.datetime', FixedDateTime),
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

    def test_raises_click_exception_for_error_response(self):
        config = self.write_config()

        with (
            patch(
                'fifa_panini.utils.panini.PaniniClient.post_json',
                lambda _self, *_args, **_kwargs: ClaimResponseStub(BAD_CLAIM_RESPONSE_TEXT),
            ),
            patch('fifa_panini.commands.panini.claim.dt.datetime', FixedDateTime),
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
            text = '{"claimed":true}'

        def fake_post(_session, url, data, headers, timeout):
            requests.append((url, data, headers, timeout))
            return FakeResponse()

        with patch('fifa_panini.utils.panini.requests.Session.post', fake_post):
            response = command.panini_client.post_json(CLAIM_PACKS_PATH, request_name='claim packs')

        self.assertEqual(response.text, '{"claimed":true}')
        self.assertEqual(response.headers, {'Content-Type': 'application/json'})
        self.assertEqual(requests[0][0], 'https://paninicollection.fifa.com/api/receive_daily_packs.json')
        self.assertEqual(requests[0][1], {'json': '{}', 'locale': 'en'})


class ClaimResponseStub:
    def __init__(self, text):
        self.text = text
        self.headers = {'Content-Type': 'application/json'}
