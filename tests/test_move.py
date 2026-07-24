import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.panini import INFO_PATH, MOVE_STICKERS_PATH, Move, MoveResponse
from fifa_panini.utils.panini import API_ENDPOINT


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class MoveTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.tmp_path = Path(self.tempdir.name)

    def write_config(self, content=''):
        config = self.tmp_path / 'config.toml'
        config.write_text(content)
        return config

    def info_response_text(self):
        return json.dumps(
            [
                {'millis': 60000, 'action': 'poll_interval'},
                {
                    'stacks': {
                        'album': [[1, 0], [2, 0], [44, 3]],
                        'swap': [98, 107],
                        'temp': [44, 114, 143],
                    },
                    'action': 'init',
                },
            ]
        )

    def test_cli_exposes_command_and_dry_run_prints_grouped_move_payloads(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            lambda _self, *_args, **_kwargs: MoveResponse(text=self.info_response_text()),
        ):
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
                    'move',
                    '--dry-run',
                    'swap',
                    '44, 98, 1, 114',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '\n'.join(
                [
                    'DRY RUN POST https://example.test/api/move_stickers.json '
                    'json={"from":"temp","to":{"swap":[44,114]}}',
                    'DRY RUN POST https://example.test/api/move_stickers.json '
                    'json={"from":"album","to":{"swap":[1]}}',
                    'Already in swap: 98',
                    '',
                ]
            ),
        )

    def test_sends_info_lookup_and_multiple_move_requests(self):
        config = self.write_config()
        calls = []

        def fake_post_json(_self, path, payload=None, request_name=None):
            calls.append((path, payload, request_name))
            if path == INFO_PATH:
                return MoveResponse(text=self.info_response_text())
            return MoveResponse(text='[{"action":"move_stickers"}]')

        with patch('fifa_panini.utils.panini.PaniniClient.post_json', fake_post_json):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'move',
                    'album',
                    '114, 98, 107, 1',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            calls,
            [
                (INFO_PATH, None, 'info'),
                (MOVE_STICKERS_PATH, {'from': 'temp', 'to': {'album': [114]}}, 'move stickers'),
                (MOVE_STICKERS_PATH, {'from': 'swap', 'to': {'album': [98, 107]}}, 'move stickers'),
            ],
        )
        self.assertEqual(
            result.output,
            '\n'.join(
                [
                    'Moved stickers from temp to album: 114',
                    'Moved stickers from swap to album: 98, 107',
                    'Already in album: 1',
                    '',
                ]
            ),
        )

    def test_sends_move_request_with_move_body(self):
        captured = {}
        command = Move(target='swap', stickers='44', dry_run=False, **panini_settings(cookie='session=value'))

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

        with patch('fifa_panini.utils.panini.requests.Session.post', fake_post):
            response = command.panini_client.post_json(
                MOVE_STICKERS_PATH,
                payload={'from': 'temp', 'to': {'swap': [44, 114, 143]}},
                request_name='move stickers',
            )

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/move_stickers.json')
        self.assertEqual(captured['data'], {'json': '{"from":"temp","to":{"swap":[44,114,143]}}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_rejects_api_error_response(self):
        config = self.write_config()
        responses = [
            MoveResponse(text=self.info_response_text()),
            MoveResponse(text='[{"error":{"message":"move_stickers.temp_to_swap"},"action":"move_stickers"}]'),
        ]

        with patch('fifa_panini.utils.panini.PaniniClient.post_json', lambda _self, *_args, **_kwargs: responses.pop(0)):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'move',
                    'swap',
                    '114',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: move_stickers.temp_to_swap\n')

    def test_rejects_missing_confirmation_response(self):
        config = self.write_config()
        responses = [
            MoveResponse(text=self.info_response_text()),
            MoveResponse(text='[]'),
        ]

        with patch('fifa_panini.utils.panini.PaniniClient.post_json', lambda _self, *_args, **_kwargs: responses.pop(0)):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'move',
                    'swap',
                    '114',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response did not include move_stickers confirmation.\n')

    def test_rejects_invalid_sticker_number(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=value',
                'move',
                'swap',
                '44, nope, 143',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: STICKERS includes an invalid sticker number: nope\n')

    def test_rejects_missing_stickers(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            lambda _self, *_args, **_kwargs: MoveResponse(text=self.info_response_text()),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'move',
                    'swap',
                    '999',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Sticker(s) not found in album, swap, or temp: 999\n')
