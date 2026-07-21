import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.panini import API_ENDPOINT
from fifa_panini.commands.stickers import Stickers, StickersResponse


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class StickersTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.tmp_path = Path(self.tempdir.name)

    def write_config(self, content=''):
        config = self.tmp_path / 'config.toml'
        config.write_text(content)
        return config

    def stickers_response_text(self):
        return json.dumps(
            [
                {'millis': 60000, 'action': 'poll_interval'},
                {
                    'stacks': {
                        'album': [[1, 0], [2, 0], [44, 3], [98, 1]],
                        'temp': [17, 44, 114, 2],
                    },
                    'action': 'init',
                },
            ]
        )

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
                'stickers',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/init.json json={}\n')

    def test_sends_stickers_request_with_info_body(self):
        captured = {}
        command = Stickers(dry_run=False, **panini_settings(cookie='session=value'))

        class FakeResponse:
            headers = {}
            text = '{"ok":true}'

        def fake_post(_session, url, data, headers, timeout):
            captured['url'] = url
            captured['data'] = data
            captured['cookie'] = headers['Cookie']
            captured['content_type'] = headers['Content-Type']
            captured['timeout'] = timeout
            return FakeResponse()

        with patch('fifa_panini.commands.panini.requests.Session.post', fake_post):
            response = command.get_stickers()

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/init.json')
        self.assertEqual(captured['data'], {'json': '{}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_cli_move_dry_run_posts_move_payload(self):
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
                'stickers',
                '--move',
                '44, 114, 143',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'DRY RUN POST https://example.test/api/move_stickers.json '
            'json={"from":"temp","to":{"swap":[44,114,143]}}\n',
        )

    def test_sends_move_request_with_move_body(self):
        captured = {}
        command = Stickers(dry_run=False, **panini_settings(cookie='session=value'))

        class FakeResponse:
            headers = {}
            text = '{"ok":true}'

        def fake_post(_session, url, data, headers, timeout):
            captured['url'] = url
            captured['data'] = data
            captured['cookie'] = headers['Cookie']
            captured['content_type'] = headers['Content-Type']
            captured['timeout'] = timeout
            return FakeResponse()

        with patch('fifa_panini.commands.panini.requests.Session.post', fake_post):
            response = command.move_stickers([44, 114, 143])

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/move_stickers.json')
        self.assertEqual(captured['data'], {'json': '{"from":"temp","to":{"swap":[44,114,143]}}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_move_skips_existing_stickers_output(self):
        config = self.write_config()

        with patch.object(
            Stickers,
            'move_stickers',
            lambda _self, _stickers: StickersResponse(text='[{"action":"move_stickers"}]'),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'stickers',
                    '--move',
                    '44, 114, 143',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Moved stickers to swap: 44, 114, 143\n')

    def test_move_rejects_api_error_response(self):
        config = self.write_config()

        response = StickersResponse(
            text='[{"error":{"message":"move_stickers.temp_to_swap"},"action":"move_stickers"}]'
        )
        with patch.object(Stickers, 'move_stickers', lambda _self, _stickers: response):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'stickers',
                    '--move',
                    '44, 114, 143',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: move_stickers.temp_to_swap\n')

    def test_move_rejects_missing_confirmation_response(self):
        config = self.write_config()

        with patch.object(Stickers, 'move_stickers', lambda _self, _stickers: StickersResponse(text='[]')):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'stickers',
                    '--move',
                    '44, 114, 143',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response did not include move_stickers confirmation.\n')

    def test_prints_owned_duplicates_and_stickers_to_glue(self):
        config = self.write_config()

        with patch.object(Stickers, 'get_stickers', lambda _self: StickersResponse(text=self.stickers_response_text())):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'stickers',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '\n'.join(
                [
                    'Owned stickers: 1, 2, 44, 98',
                    'New DUPLICATE stickers: 44, 2',
                    'Swap stickers: (none)',
                    'New Stickers to glue: 17, 114',
                    '',
                ]
            ),
        )

    def test_prints_trade_offer_and_ask_from_swap_flags(self):
        config = self.write_config()

        with patch.object(Stickers, 'get_stickers', lambda _self: StickersResponse(text=self.stickers_response_text())):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'stickers',
                    '--swap-out',
                    '1, 2, 77',
                    '--swap-in',
                    '98, 114, 200, 201',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '\n'.join(
                [
                    'Owned stickers: 1, 2, 44, 98',
                    'New DUPLICATE stickers: 44, 2',
                    'Swap stickers: (none)',
                    'New Stickers to glue: 17, 114',
                    'Offer: 44',
                    'Ask: 200, 201',
                    '',
                ]
            ),
        )

    def test_rejects_invalid_swap_flag_sticker_number(self):
        config = self.write_config()

        with patch.object(Stickers, 'get_stickers', lambda _self: StickersResponse(text=self.stickers_response_text())):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'stickers',
                    '--swap-in',
                    '1, nope, 3',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: --swap-in includes an invalid sticker number: nope\n')

    def test_rejects_invalid_move_flag_sticker_number(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=value',
                'stickers',
                '--move',
                '44, nope, 143',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: --move includes an invalid sticker number: nope\n')

    def test_raises_click_exception_when_init_action_is_missing(self):
        config = self.write_config()

        with patch.object(Stickers, 'get_stickers', lambda _self: StickersResponse(text='[]')):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'stickers',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response did not include init sticker stacks.\n')
