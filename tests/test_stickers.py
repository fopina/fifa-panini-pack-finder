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
                    'DUPLICATE stickers: 44, 2',
                    'Stickers to glue: 17, 114',
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
                    'DUPLICATE stickers: 44, 2',
                    'Stickers to glue: 17, 114',
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
