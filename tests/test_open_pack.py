import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.panini.open_pack import OPEN_PACK_PATH, OpenPack, PackResponse
from fifa_panini.utils.panini import API_ENDPOINT

GOOD_OPEN_PACK_RESPONSE_TEXT = (
    '[{"stickers":[194,513,705,1433,1441],"action":"open_pack"},'
    '{"has_new_challenge":true,"has_just_completed_challenge":false,"num_available_challenges":1,'
    '"action":"challenge_summary"}]'
)
BAD_OPEN_PACK_RESPONSE_TEXT = (
    '[{"error":{"message":"packs.cannot_open"},"action":"open_pack"},'
    '{"has_new_challenge":true,"has_just_completed_challenge":false,"num_available_challenges":1,'
    '"action":"challenge_summary"}]'
)
WAIT_OPEN_PACK_RESPONSE_TEXT = (
    '[{"wait":{"reason":"You\'ve reached your daily limit of 4 packs.\\nPlease retry in:",'
    '"countdown_seconds":69790},"action":"open_pack"},'
    '{"has_new_challenge":true,"has_just_completed_challenge":false,"num_available_challenges":1,'
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


class OpenPackTestCase(unittest.TestCase):
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
                'open',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/open_pack.json json={}\n')

    def test_sends_open_pack_request_with_shared_cookie(self):
        captured = {}
        command = OpenPack(dry_run=False, **panini_settings(cookie='session=value'))

        class FakeHeaders:
            @staticmethod
            def items():
                return [('Content-Type', 'application/json')]

        class FakeResponse:
            headers = FakeHeaders()
            text = '{"ok":true}'

        def fake_post(_session, url, data, headers, timeout):
            captured['url'] = url
            captured['data'] = data
            captured['cookie'] = headers['Cookie']
            captured['content_type'] = headers['Content-Type']
            captured['timeout'] = timeout
            return FakeResponse()

        with patch('fifa_panini.utils.panini.requests.Session.post', fake_post):
            response = command.panini_client.post_json(OPEN_PACK_PATH, request_name='open pack')

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/open_pack.json')
        self.assertEqual(captured['data'], {'json': '{}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_prints_opened_pack_summary_for_success_response(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            lambda _self, *_args, **_kwargs: PackResponse(
                text=GOOD_OPEN_PACK_RESPONSE_TEXT,
                headers={'Content-Type': 'application/json'},
            ),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'open',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'Opened stickers: 194, 513, 705, 1433, 1441\n',
        )
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(GOOD_OPEN_PACK_RESPONSE_TEXT, result.output)

    def test_ignores_error_and_wait_from_unrelated_actions(self):
        config = self.write_config()
        response_text = (
            '[{"stickers":[194,513],"action":"open_pack"},'
            '{"error":{"message":"challenge.failed"},"action":"challenge_summary"},'
            '{"wait":{"reason":"retry later"},"action":"daily_packs_status"}]'
        )

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            lambda _self, *_args, **_kwargs: PackResponse(
                text=response_text,
                headers={'Content-Type': 'application/json'},
            ),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'open',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Opened stickers: 194, 513\n')

    def test_raises_click_exception_for_error_response(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            lambda _self, *_args, **_kwargs: PackResponse(
                text=BAD_OPEN_PACK_RESPONSE_TEXT,
                headers={'Content-Type': 'application/json'},
            ),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'open',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: packs.cannot_open\n')
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(BAD_OPEN_PACK_RESPONSE_TEXT, result.output)

    def test_raises_click_exception_for_wait_response(self):
        config = self.write_config()

        with (
            patch(
                'fifa_panini.utils.panini.PaniniClient.post_json',
                lambda _self, *_args, **_kwargs: PackResponse(
                    text=WAIT_OPEN_PACK_RESPONSE_TEXT,
                    headers={'Content-Type': 'application/json'},
                ),
            ),
            patch('fifa_panini.commands.panini.open_pack.dt.datetime', FixedDateTime),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'open',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            "Error: You've reached your daily limit of 4 packs.\nPlease retry in: 2026-07-22 07:23:10 UTC\n",
        )
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(WAIT_OPEN_PACK_RESPONSE_TEXT, result.output)

    def test_loads_cookie_from_config(self):
        config = self.write_config('\n'.join(['[panini]', 'cookie = "session=value"']))

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'open', '--dry-run'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'DRY RUN POST https://paninicollection.fifa.com/api/open_pack.json json={}\n',
        )
