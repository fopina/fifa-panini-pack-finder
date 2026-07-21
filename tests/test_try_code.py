import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.try_code import TryCode
from fifa_panini.utils.codes import CodeResponse
from fifa_panini.utils.panini import API_ENDPOINT

GOOD_TRY_CODE_RESPONSE_TEXT = (
    '[{"code":"SDB9-LM7T-93YT","is_multi_code":false,"market":"cr","action":"unlock_pack"},'
    '{"amount":1,"from_entered_code":true,"was_premium_code":false,"total_packs":2,"action":"received_packs"},'
    '{"has_new_challenge":true,"has_just_completed_challenge":false,"num_available_challenges":1,'
    '"action":"challenge_summary"}]'
)
BAD_TRY_CODE_RESPONSE_TEXT = (
    '[{"error":{"message":"code.already_used"},"action":"unlock_pack"},'
    '{"has_new_challenge":true,"has_just_completed_challenge":false,"num_available_challenges":1,'
    '"action":"challenge_summary"}]'
)


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class TryCodeTestCase(unittest.TestCase):
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
                'try-code',
                '--dry-run',
                'ABCD-EFGH-IJKL',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/unlock_pack.json code=ABCD-EFGH-IJKL\n')

    def test_sends_only_passed_code(self):
        attempts = []
        command = TryCode(
            code='ABCD-EFGH-IJKL',
            dry_run=False,
            **panini_settings(),
        )

        def fake_send_code(code):
            attempts.append(code)
            return CodeResponse(text=GOOD_TRY_CODE_RESPONSE_TEXT, headers={'Content-Type': 'application/json'})

        with patch.object(command, 'send_code', fake_send_code):
            command()

        self.assertEqual(attempts, ['ABCD-EFGH-IJKL'])

    def test_prints_pack_summary_for_success_response(self):
        config = self.write_config()

        with patch.object(
            TryCode,
            'send_code',
            lambda _self, _code: CodeResponse(
                text=GOOD_TRY_CODE_RESPONSE_TEXT,
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
                    'try-code',
                    'ABCD-EFGH-IJKL',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Won 1 packs. Total packs: 2\n')
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(GOOD_TRY_CODE_RESPONSE_TEXT, result.output)

    def test_ignores_error_from_unrelated_action(self):
        config = self.write_config()
        response_text = (
            '[{"code":"SDB9-LM7T-93YT","action":"unlock_pack"},'
            '{"amount":1,"total_packs":2,"action":"received_packs"},'
            '{"error":{"message":"challenge.failed"},"action":"challenge_summary"}]'
        )

        with patch.object(
            TryCode,
            'send_code',
            lambda _self, _code: CodeResponse(
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
                    'try-code',
                    'ABCD-EFGH-IJKL',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Won 1 packs. Total packs: 2\n')

    def test_raises_click_exception_for_error_response(self):
        config = self.write_config()

        with patch.object(
            TryCode,
            'send_code',
            lambda _self, _code: CodeResponse(
                text=BAD_TRY_CODE_RESPONSE_TEXT,
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
                    'try-code',
                    'ABCD-EFGH-IJKL',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response did not include received pack information.\n')
        self.assertNotIn('Response headers:', result.output)
        self.assertNotIn('Response text:', result.output)
        self.assertNotIn(BAD_TRY_CODE_RESPONSE_TEXT, result.output)

    def test_raises_click_exception_when_received_packs_are_missing(self):
        config = self.write_config()

        with patch.object(
            TryCode,
            'send_code',
            lambda _self, _code: CodeResponse(
                text='[{"code":"SDB9-LM7T-93YT","action":"unlock_pack"}]',
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
                    'try-code',
                    'ABCD-EFGH-IJKL',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'Error: Response did not include received pack information.\n')

    def test_raises_click_exception_when_response_is_not_json(self):
        config = self.write_config()

        with patch.object(
            TryCode,
            'send_code',
            lambda _self, _code: CodeResponse(text='not json', headers={'Content-Type': 'application/json'}),
        ):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'try-code',
                    'ABCD-EFGH-IJKL',
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Response was not valid JSON', result.output)

    def test_send_code_posts_unlock_pack_payload(self):
        captured = {}
        command = TryCode(
            code='ABCD-EFGH-IJKL',
            dry_run=False,
            **panini_settings(cookie='session=value'),
        )

        class FakeResponse:
            headers = {'Content-Type': 'application/json'}
            text = '{"ok":true}'

        def fake_post(_session, url, data, headers, timeout):
            captured['url'] = url
            captured['data'] = data
            captured['cookie'] = headers['Cookie']
            captured['content_type'] = headers['Content-Type']
            captured['timeout'] = timeout
            return FakeResponse()

        with patch('fifa_panini.utils.panini.requests.Session.post', fake_post):
            response = command.send_code('ABCD-EFGH-IJKL')

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/unlock_pack.json')
        self.assertEqual(captured['data'], {'json': '{"code":"ABCD-EFGH-IJKL"}', 'locale': 'en'})
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')
        self.assertEqual(response.headers, {'Content-Type': 'application/json'})

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
                'try-code',
                '--dry-run',
                'ABCD-EFGH-IJKL',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(r'Cookie contains \u2026', result.output)

    def test_loads_settings_from_config(self):
        config = self.write_config(
            '\n'.join(
                [
                    '[panini]',
                    'cookie = "session=value"',
                    'api_endpoint = "https://example.test/api/"',
                ]
            )
        )

        result = CliRunner().invoke(
            CLI.click, ['--config', str(config), 'panini', 'try-code', '--dry-run', 'ABCD-EFGH-IJKL']
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/unlock_pack.json code=ABCD-EFGH-IJKL\n')
