import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.panini.swap import (
    DELETE_SWAP_REQUEST_PATH,
    INFO_PATH,
    SWAP_REQUESTS_PATH,
    UPDATE_SWAP_REQUEST_PATH,
    Swap,
    SwapResponse,
)
from fifa_panini.utils.panini import API_ENDPOINT


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


def post_json_responses(*responses):
    responses = list(responses)

    def fake_post_json(_self, *_args, **_kwargs):
        return responses.pop(0)

    return fake_post_json


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

    def test_collect_posts_each_received_swap_and_stops_on_error(self):
        config = self.write_config()
        stack_actions = json.loads(self.swap_response_text())
        stack_actions[1]['received_swaps'] = [
            {'id': swap_id, 'received': [121, 127], 'given': [81, 86]}
            for swap_id in ['4399585804394855846', '2562693308756677408', 'third']
        ]
        with patch('fifa_panini.utils.panini.PaniniClient.post_json') as post:
            post.side_effect = [
                SwapResponse(text=json.dumps(stack_actions)),
                SwapResponse(text=self.swap_requests_response_text([])),
                SwapResponse(text='[{"action":"execute_received_swap"}]'),
                SwapResponse(text='[{"action":"execute_received_swap","error":{"message":"failed"}}]'),
            ]
            result = CliRunner().invoke(
                CLI.click,
                ['--config', str(config), 'panini', '--cookie', 'session=value', 'swap', '--collect'],
            )
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(post.call_count, 4)
        for call, swap_id in zip(post.call_args_list[2:], ['4399585804394855846', '2562693308756677408']):
            self.assertEqual(call.args, ('execute_received_swap.json',))
            self.assertEqual(call.kwargs['payload'], {'id': swap_id})
        self.assertIn('Collected swap: 4399585804394855846\n', result.output)
        self.assertNotIn('Collected swap: 2562693308756677408', result.output)
        self.assertTrue(result.output.endswith('Error: failed\n'))

    def test_collect_dry_run_does_not_send_requests(self):
        config = self.write_config()
        with patch('fifa_panini.utils.panini.PaniniClient.post_json') as post:
            result = CliRunner().invoke(
                CLI.click,
                ['--config', str(config), 'panini', '--cookie', 'session=value', 'swap', '--collect', '--dry-run'],
            )
        self.assertEqual(result.exit_code, 0)
        post.assert_not_called()
        self.assertIn('execute_received_swap.json', result.output)

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

    def test_cli_delete_dry_run_posts_delete_payload(self):
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
                '--delete',
                '1784671714343',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'DRY RUN POST https://example.test/api/delete_swap_request.json json={"id":"1784671714343"}\n',
        )

    def test_cli_create_dry_run_posts_create_payload(self):
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
                '--create',
                '36',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            (
                'DRY RUN POST https://example.test/api/update_swap_request.json '
                'json={"id":null,"only_team":true,"offer":{"stickers":[],"groups":[],"full_stack":true},'
                '"demand":{"stickers":[36],"groups":[],"allow_duplicates":false}}\n'
            ),
        )

    def test_cli_create_dry_run_can_allow_duplicates(self):
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
                '--create',
                '36, 42',
                '--create-allow-duplicates',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            (
                'DRY RUN POST https://example.test/api/update_swap_request.json '
                'json={"id":null,"only_team":true,"offer":{"stickers":[],"groups":[],"full_stack":true},'
                '"demand":{"stickers":[36,42],"groups":[],"allow_duplicates":true}}\n'
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

        with patch('fifa_panini.utils.panini.requests.Session.post', fake_post):
            response = command.panini_client.post_json(INFO_PATH, request_name='swap')

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

        with patch('fifa_panini.utils.panini.requests.Session.post', fake_post):
            response = command.panini_client.post_json(SWAP_REQUESTS_PATH, request_name='swap requests')

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/swap_requests.json')
        self.assertEqual(captured['data'], {'json': '{}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_sends_delete_swap_request_with_id_body(self):
        captured = {}
        command = Swap(dry_run=False, **panini_settings(cookie='session=value'))

        class FakeResponse:
            headers = {}
            text = '[{"action":"delete_swap_request"}]'

        def fake_post(_session, url, data, headers, timeout):
            captured['url'] = url
            captured['data'] = data
            captured['cookie'] = headers['Cookie']
            captured['content_type'] = headers['Content-Type']
            captured['timeout'] = timeout
            return FakeResponse()

        with patch('fifa_panini.utils.panini.requests.Session.post', fake_post):
            response = command.panini_client.post_json(
                DELETE_SWAP_REQUEST_PATH,
                payload={'id': '1784671714343'},
                request_name='delete swap request',
            )

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/delete_swap_request.json')
        self.assertEqual(captured['data'], {'json': '{"id":"1784671714343"}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '[{"action":"delete_swap_request"}]')

    def test_sends_create_swap_request_with_demand_body(self):
        captured = {}
        command = Swap(dry_run=False, create_allow_duplicates=True, **panini_settings(cookie='session=value'))

        class FakeResponse:
            headers = {}
            text = '[{"action":"update_swap_request"}]'

        def fake_post(_session, url, data, headers, timeout):
            captured['url'] = url
            captured['data'] = data
            captured['cookie'] = headers['Cookie']
            captured['content_type'] = headers['Content-Type']
            captured['timeout'] = timeout
            return FakeResponse()

        with patch('fifa_panini.utils.panini.requests.Session.post', fake_post):
            response = command.panini_client.post_json(
                UPDATE_SWAP_REQUEST_PATH,
                payload={
                    'id': None,
                    'only_team': True,
                    'offer': {
                        'stickers': [],
                        'groups': [],
                        'full_stack': True,
                    },
                    'demand': {
                        'stickers': [36, 42],
                        'groups': [],
                        'allow_duplicates': command.create_allow_duplicates,
                    },
                },
                request_name='create swap request',
            )

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/update_swap_request.json')
        self.assertEqual(
            captured['data'],
            {
                'json': (
                    '{"id":null,"only_team":true,"offer":{"stickers":[],"groups":[],"full_stack":true},'
                    '"demand":{"stickers":[36,42],"groups":[],"allow_duplicates":true}}'
                ),
                'locale': 'en',
            },
        )
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '[{"action":"update_swap_request"}]')

    def test_prints_swap_stack_stickers(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            post_json_responses(
                SwapResponse(text=self.swap_response_text()),
                SwapResponse(text=self.swap_requests_response_text([])),
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
        self.assertEqual(result.output, 'Swap stickers: 3, 5\nSwap requests: (none)\nSwaps executed: (none)\n')

    def test_prints_swap_requests(self):
        config = self.write_config()
        stack_actions = json.loads(self.swap_response_text())
        stack_actions[1]['received_swaps'] = [
            {'id': '2562693308756677408', 'received': [121, 127], 'given': [81, 86]},
        ]

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            post_json_responses(
                SwapResponse(text=json.dumps(stack_actions)),
                SwapResponse(text=self.swap_requests_response_text()),
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
                    'Swaps executed:',
                    '- id: 2562693308756677408; +121, +127; -81, -86',
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

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            post_json_responses(
                SwapResponse(text=self.swap_response_text()),
                SwapResponse(text=self.swap_requests_response_text(requests)),
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
                    'Swaps executed: (none)',
                    '',
                ]
            ),
        )

    def test_prints_none_when_swap_stack_is_empty(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            post_json_responses(
                SwapResponse(text=self.swap_response_text([])),
                SwapResponse(text=self.swap_requests_response_text([])),
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
        self.assertEqual(result.output, 'Swap stickers: (none)\nSwap requests: (none)\nSwaps executed: (none)\n')

    def test_raises_click_exception_when_init_action_is_missing(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            post_json_responses(
                SwapResponse(text='[]'),
                SwapResponse(text=self.swap_requests_response_text([])),
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

    def test_delete_prints_success_for_confirmation_response(self):
        config = self.write_config()
        response = SwapResponse(
            text=(
                '[{"action":"delete_swap_request"},'
                '{"has_new_challenge":true,"has_just_completed_challenge":false,'
                '"num_available_challenges":1,"action":"challenge_summary"}]'
            )
        )

        with patch('fifa_panini.utils.panini.PaniniClient.post_json', lambda _self, *_args, **_kwargs: response):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'swap',
                    '--delete',
                    '1784671714343',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Deleted swap request: 1784671714343\n')

    def test_delete_rejects_error_in_delete_action(self):
        config = self.write_config()
        response = SwapResponse(text='[{"error":{"message":"swap_request.not_found"},"action":"delete_swap_request"}]')

        with patch('fifa_panini.utils.panini.PaniniClient.post_json', lambda _self, *_args, **_kwargs: response):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'swap',
                    '--delete',
                    '1784671714343',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: swap_request.not_found\n')

    def test_delete_rejects_missing_confirmation_response(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            lambda _self, *_args, **_kwargs: SwapResponse(text='[]'),
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
                    '--delete',
                    '1784671714343',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response did not include delete_swap_request confirmation.\n')

    def test_create_prints_success_for_confirmation_response(self):
        config = self.write_config()
        response = SwapResponse(
            text=(
                '[{"action":"update_swap_request"},'
                '{"has_new_challenge":true,"has_just_completed_challenge":false,'
                '"num_available_challenges":1,"action":"challenge_summary"}]'
            )
        )

        with patch('fifa_panini.utils.panini.PaniniClient.post_json', lambda _self, *_args, **_kwargs: response):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'swap',
                    '--create',
                    '36, 42',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Created swap request for stickers: 36, 42\n')

    def test_create_rejects_error_in_update_action(self):
        config = self.write_config()
        response = SwapResponse(text='[{"error":{"message":"swap_request.invalid"},"action":"update_swap_request"}]')

        with patch('fifa_panini.utils.panini.PaniniClient.post_json', lambda _self, *_args, **_kwargs: response):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'swap',
                    '--create',
                    '36',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: swap_request.invalid\n')

    def test_create_rejects_missing_confirmation_response(self):
        config = self.write_config()

        with patch(
            'fifa_panini.utils.panini.PaniniClient.post_json',
            lambda _self, *_args, **_kwargs: SwapResponse(text='[]'),
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
                    '--create',
                    '36',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response did not include update_swap_request confirmation.\n')

    def test_create_rejects_invalid_sticker_number(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=value',
                'swap',
                '--create',
                '36, nope',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: --create includes an invalid sticker number: nope\n')

    def test_rejects_create_and_delete_together(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=value',
                'swap',
                '--create',
                '36',
                '--delete',
                '1784671714343',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: --delete and --create cannot be used together.\n')

    def test_rejects_create_allow_duplicates_without_create(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=value',
                'swap',
                '--create-allow-duplicates',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: --create-allow-duplicates can only be used with --create.\n')
