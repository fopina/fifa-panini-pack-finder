import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.info import Info, InfoResponse
from fifa_panini.commands.panini import API_ENDPOINT


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class InfoTestCase(unittest.TestCase):
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
                        'album': [1, 2],
                        'own_lineup': [],
                        'swap': [3],
                        'temp': [17, 44, 114],
                    },
                    'received_swaps': [],
                    'completed_groups': ['group-1'],
                    'album_completed': False,
                    'action': 'init',
                },
                {
                    'amount': 3,
                    'from_entered_code': False,
                    'was_premium_code': False,
                    'total_packs': 3,
                    'action': 'received_packs',
                },
                {
                    'user_info': {
                        'uid': '55432500',
                        'label': 'tester',
                        'country': 'PRT',
                        'album_completion_perc': 12,
                        'album_collected_stickers': 77,
                        'album_total_stickers': 645,
                        'golden_album_completion_perc': 4,
                        'golden_album_collected_stickers': 23,
                        'golden_album_total_stickers': 585,
                        'collector_points': 10,
                        'public_profile': {
                            'id': 'JQ99Mv',
                            'url': 'https://paninicollection.fifa.com/p/JQ99Mv',
                        },
                    },
                    'ref_token': 'JQ99Mv',
                    'action': 'own_user_info',
                },
                {
                    'current_collector_points': 10,
                    'discounts': [{'unlocked': False, 'type': 'mypanini_row'}],
                    'action': 'discount_summary',
                },
                {'url': 'https://my.panini.link/fifa-wc-26-stk-collectors', 'action': 'mypanini_state'},
                {'slots': [-1], 'valid': False, 'problem': 'Need players.', 'action': 'dream_team_own'},
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
                'info',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/init.json json={}\n')

    def test_sends_info_request_with_open_pack_body(self):
        captured = {}
        command = Info(dry_run=False, **panini_settings(cookie='session=value'))

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
            response = command.get_info()

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/init.json')
        self.assertEqual(captured['data'], {'json': '{}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_prints_info_summary_by_default(self):
        config = self.write_config()

        with patch.object(Info, 'get_info', lambda _self: InfoResponse(text=self.info_response_text())):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'info',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            '\n'.join(
                [
                    'Available packs: 3',
                    'User: tester (PRT)',
                    'Public profile: https://paninicollection.fifa.com/p/JQ99Mv',
                    'Collector points: 10',
                    'Album: 77/645 (12%)',
                    'Golden album: 23/585 (4%)',
                    'Album completed: no',
                    'album stickers: 2',
                    'own_lineup stickers: 0',
                    'swap stickers: 1',
                    'temp stickers: 3',
                    'Completed groups: 1',
                    'Received swaps: 0',
                    '',
                ]
            ),
        )
        self.assertNotIn('discount_summary', result.output)
        self.assertNotIn('dream_team_own', result.output)
        self.assertNotIn('mypanini_state', result.output)

    def test_raw_prints_complete_json_response(self):
        config = self.write_config()
        response_text = self.info_response_text()

        with patch.object(Info, 'get_info', lambda _self: InfoResponse(text=response_text)):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'info',
                    '--raw',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, f'{response_text}\n')
        self.assertIn('discount_summary', result.output)
        self.assertIn('dream_team_own', result.output)
        self.assertIn('mypanini_state', result.output)

    def test_loads_cookie_from_config(self):
        config = self.write_config('\n'.join(['[panini]', 'cookie = "session=value"']))

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'info', '--dry-run'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'DRY RUN POST https://paninicollection.fifa.com/api/init.json json={}\n',
        )
