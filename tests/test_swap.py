import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.panini import API_ENDPOINT
from fifa_panini.commands.swap import Swap, SwapResponse


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class SwapTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.tmp_path = Path(self.tempdir.name)

    def write_config(self, content=''):
        config = self.tmp_path / 'config.toml'
        config.write_text(content)
        return config

    def swap_response_text(self, swap_stickers=None):
        if swap_stickers is None:
            swap_stickers = [[3, 0], 5]

        return json.dumps(
            [
                {'millis': 60000, 'action': 'poll_interval'},
                {
                    'stacks': {
                        'album': [[1, 0], [2, 0]],
                        'swap': swap_stickers,
                        'temp': [17, 44, 114],
                    },
                    'action': 'init',
                },
            ]
        )

    def swap_requests_response_text(self, requests=None):
        if requests is None:
            requests = [
                {
                    'demand': {'allow_duplicates': True, 'groups': [], 'stickers': [107, 108, 109]},
                    'id': '1784658490062',
                    'offer': {'full_stack': True, 'groups': [], 'stickers': [492, 672, 737]},
                    'only_team': True,
                }
            ]

        return json.dumps(
            [
                {
                    'state': 'unrestricted',
                    'is_in_team': True,
                    'swap_requests': requests,
                    'action': 'swap_requests',
                },
                {
                    'has_new_challenge': False,
                    'has_just_completed_challenge': False,
                    'num_available_challenges': 1,
                    'action': 'challenge_summary',
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
                'swap',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '\n'.join(
                [
                    'DRY RUN POST https://example.test/api/init.json json={}',
                    'DRY RUN POST https://example.test/api/swap_requests.json json={}',
                    '',
                ]
            ),
        )

    def test_sends_swap_request_with_info_body(self):
        captured = {}
        command = Swap(dry_run=False, **panini_settings(cookie='session=value'))

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
            response = command.get_swap()

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/init.json')
        self.assertEqual(captured['data'], {'json': '{}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_sends_swap_requests_request_with_info_body(self):
        captured = {}
        command = Swap(dry_run=False, **panini_settings(cookie='session=value'))

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
            response = command.get_swap_requests()

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/swap_requests.json')
        self.assertEqual(captured['data'], {'json': '{}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_prints_swap_stack_stickers(self):
        config = self.write_config()

        with (
            patch.object(Swap, 'get_swap_stack', lambda _self: SwapResponse(text=self.swap_response_text())),
            patch.object(
                Swap,
                'get_swap_requests',
                lambda _self: SwapResponse(text=self.swap_requests_response_text([])),
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
                    'swap',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Swap stickers: 3, 5\nSwap requests: (none)\n')

    def test_prints_swap_requests(self):
        config = self.write_config()

        with (
            patch.object(Swap, 'get_swap_stack', lambda _self: SwapResponse(text=self.swap_response_text())),
            patch.object(
                Swap,
                'get_swap_requests',
                lambda _self: SwapResponse(text=self.swap_requests_response_text()),
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
                    'swap',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '\n'.join(
                [
                    'Swap stickers: 3, 5',
                    'Swap requests:',
                    (
                        '- id: 1784658490062; offer: stickers: 492, 672, 737, full stack; '
                        'demand: stickers: 107, 108, 109; only team'
                    ),
                    '',
                ]
            ),
        )

    def test_prints_swap_request_groups_and_hides_false_only_team(self):
        config = self.write_config()
        requests = [
            {
                'demand': {'allow_duplicates': True, 'groups': ['POR', 'ARG'], 'stickers': []},
                'id': '1784658490063',
                'offer': {'full_stack': False, 'groups': ['BRA'], 'stickers': [492]},
                'only_team': False,
            }
        ]

        with (
            patch.object(Swap, 'get_swap_stack', lambda _self: SwapResponse(text=self.swap_response_text())),
            patch.object(
                Swap,
                'get_swap_requests',
                lambda _self: SwapResponse(text=self.swap_requests_response_text(requests)),
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
                    'swap',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '\n'.join(
                [
                    'Swap stickers: 3, 5',
                    'Swap requests:',
                    '- id: 1784658490063; offer: stickers: 492, groups: BRA; demand: groups: POR, ARG',
                    '',
                ]
            ),
        )

    def test_prints_none_when_swap_stack_is_empty(self):
        config = self.write_config()

        with (
            patch.object(Swap, 'get_swap_stack', lambda _self: SwapResponse(text=self.swap_response_text([]))),
            patch.object(
                Swap,
                'get_swap_requests',
                lambda _self: SwapResponse(text=self.swap_requests_response_text([])),
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
                    'swap',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Swap stickers: (none)\nSwap requests: (none)\n')

    def test_raises_click_exception_when_init_action_is_missing(self):
        config = self.write_config()

        with (
            patch.object(Swap, 'get_swap_stack', lambda _self: SwapResponse(text='[]')),
            patch.object(
                Swap,
                'get_swap_requests',
                lambda _self: SwapResponse(text=self.swap_requests_response_text([])),
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
                    'swap',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response did not include init sticker stacks.\n')
