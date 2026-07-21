import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import click
from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.bf_code import BfCode
from fifa_panini.utils.codes import DEFAULT_STATE_FILE, TOTAL_SUFFIXES, CodeResponse
from fifa_panini.utils.panini import API_ENDPOINT

GOOD_TRY_CODE_RESPONSE_TEXT = (
    '[{"code":"SDB9-LM7T-93YT","is_multi_code":false,"market":"cr","action":"unlock_pack"},'
    '{"amount":1,"from_entered_code":true,"was_premium_code":false,"total_packs":2,"action":"received_packs"},'
    '{"has_new_challenge":true,"has_just_completed_challenge":false,"num_available_challenges":1,'
    '"action":"challenge_summary"}]'
)


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class BfCodeTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.tmp_path = Path(self.tempdir.name)

    def write_config(self, content=''):
        config = self.tmp_path / 'config.toml'
        config.write_text(content)
        return config

    def test_formats_four_character_suffixes(self):
        command = BfCode(code_base='ABCD-EFGH-IJKL', **panini_settings())

        self.assertEqual(command.format_code(0), 'ABCD-EFGH-AAAA')
        self.assertEqual(command.format_code(35), 'ABCD-EFGH-AAA9')
        self.assertEqual(command.format_code(42), 'ABCD-EFGH-AABG')

    def test_rejects_invalid_code_base(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=value',
                'bf-code',
                '--dry-run',
                '--code-base',
                'ABCD-EFGH-ijkl',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('--code-base must be in XXXX-XXXX-XXXX format', result.output)

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
                'bf-code',
                '--dry-run',
                '--code-base',
                'ABCD-EFGH-IJKL',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/unlock_pack.json code=ABCD-EFGH-AAAA\n')

    def test_panini_group_owns_shared_options(self):
        group_help = CliRunner().invoke(CLI.click, ['panini', '--help'])
        try_help = CliRunner().invoke(CLI.click, ['panini', 'try-code', '--help'])
        bf_help = CliRunner().invoke(CLI.click, ['panini', 'bf-code', '--help'])

        self.assertEqual(group_help.exit_code, 0)
        self.assertIn('--cookie', group_help.output)
        self.assertIn('--api-endpoint', group_help.output)

        self.assertEqual(try_help.exit_code, 0)
        self.assertIn('CODE', try_help.output)
        self.assertNotIn('--code', try_help.output)
        self.assertNotIn('--cookie', try_help.output)
        self.assertNotIn('--api-endpoint', try_help.output)

        self.assertEqual(bf_help.exit_code, 0)
        self.assertNotIn('--cookie', bf_help.output)
        self.assertNotIn('--api-endpoint', bf_help.output)

    def test_resumes_from_state_file(self):
        state_file = self.tmp_path / 'state.json'
        state_file.write_text('{"code_base": "ABCD-EFGH-IJKL", "current_code": "ABCD-EFGH-AABF", "next_suffix": 42}\n')
        command = BfCode(code_base='ABCD-EFGH-IJKL', state_file=state_file, **panini_settings())

        self.assertEqual(command.next_code(), 'ABCD-EFGH-AABG')

    def test_progress_resumes_from_saved_suffix(self):
        state_file = self.tmp_path / 'state.json'
        state_file.write_text('{"code_base": "ABCD-EFGH-IJKL", "current_code": "ABCD-EFGH-AABF", "next_suffix": 42}\n')
        progress_kwargs = {}

        class FakeProgress:
            def __init__(self, **kwargs):
                progress_kwargs.update(kwargs)

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc_value, _traceback):
                return False

            def set_description(self, _description):
                pass

            def update(self):
                pass

            @staticmethod
            def write(*_args, **_kwargs):
                pass

        command = BfCode(
            code_base='ABCD-EFGH-IJKL',
            dry_run=False,
            state_file=state_file,
            **panini_settings(),
        )

        def fake_send_code(code):
            text = '{"error":"code.already_used"}' if code == command.code_base else '{"ok":true}'
            if code != command.code_base:
                text = GOOD_TRY_CODE_RESPONSE_TEXT
            return CodeResponse(text=text, headers={'Content-Type': 'application/json'})

        with (
            patch('fifa_panini.commands.bf_code.tqdm', FakeProgress),
            patch.object(command, 'send_code', fake_send_code),
        ):
            command()

        self.assertEqual(progress_kwargs['total'], TOTAL_SUFFIXES)
        self.assertEqual(progress_kwargs['initial'], 42)
        self.assertEqual(progress_kwargs['unit'], 'code')

    def test_stops_when_response_is_not_invalid(self):
        attempts = []
        command = BfCode(
            code_base='ABCD-EFGH-IJKL',
            dry_run=False,
            state_file=self.tmp_path / 'state.json',
            **panini_settings(),
        )

        def fake_send_code(code):
            attempts.append(code)
            if code == command.code_base:
                return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
            if len(attempts) == 2:
                return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
            return CodeResponse(text=GOOD_TRY_CODE_RESPONSE_TEXT, headers={'Content-Type': 'application/json'})

        with (
            patch.object(command, 'send_code', fake_send_code),
            patch('fifa_panini.commands.bf_code.time.sleep', lambda _seconds: None),
        ):
            command()

        self.assertEqual(attempts, ['ABCD-EFGH-IJKL', 'ABCD-EFGH-AAAA', 'ABCD-EFGH-AAAB'])

    def test_fails_when_code_base_is_not_already_used(self):
        attempts = []
        command = BfCode(
            code_base='ABCD-EFGH-IJKL',
            dry_run=False,
            state_file=self.tmp_path / 'state.json',
            **panini_settings(),
        )

        def fake_send_code(code):
            attempts.append(code)
            return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})

        with patch.object(command, 'send_code', fake_send_code):
            with self.assertRaises(click.ClickException) as error:
                command()

        self.assertEqual(attempts, ['ABCD-EFGH-IJKL'])
        self.assertIn('Code base check failed for ABCD-EFGH-IJKL', str(error.exception))
        self.assertIn('"code.already_used"', str(error.exception))

    def test_uses_configured_request_delay(self):
        attempts = []
        sleeps = []
        command = BfCode(
            code_base='ABCD-EFGH-IJKL',
            dry_run=False,
            request_delay=0.25,
            state_file=self.tmp_path / 'state.json',
            **panini_settings(),
        )

        def fake_send_code(code):
            attempts.append(code)
            if code == command.code_base:
                return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
            if len(attempts) == 2:
                return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
            return CodeResponse(text=GOOD_TRY_CODE_RESPONSE_TEXT, headers={'Content-Type': 'application/json'})

        with (
            patch.object(command, 'send_code', fake_send_code),
            patch('fifa_panini.commands.bf_code.time.sleep', sleeps.append),
        ):
            command()

        self.assertEqual(sleeps, [0.25])

    def test_skips_request_delay_when_zero(self):
        attempts = []
        sleeps = []
        command = BfCode(
            code_base='ABCD-EFGH-IJKL',
            dry_run=False,
            request_delay=0,
            state_file=self.tmp_path / 'state.json',
            **panini_settings(),
        )

        def fake_send_code(code):
            attempts.append(code)
            if code == command.code_base:
                return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
            if len(attempts) == 2:
                return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
            return CodeResponse(text=GOOD_TRY_CODE_RESPONSE_TEXT, headers={'Content-Type': 'application/json'})

        with (
            patch.object(command, 'send_code', fake_send_code),
            patch('fifa_panini.commands.bf_code.time.sleep', sleeps.append),
        ):
            command()

        self.assertEqual(sleeps, [])

    def test_rejects_negative_request_delay(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'panini',
                '--cookie',
                'session=value',
                'bf-code',
                '--dry-run',
                '--code-base',
                'ABCD-EFGH-IJKL',
                '--request-delay=-1',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('--request-delay must be greater than or equal to 0', result.output)

    def test_loads_settings_from_config(self):
        config = self.write_config(
            '\n'.join(
                [
                    '[panini]',
                    'cookie = "session=value"',
                    'api_endpoint = "https://example.test/api/"',
                    '[panini.bf-code]',
                    'code_base = "ABCD-EFGH-IJKL"',
                    f'state_file = "{self.tmp_path / "state.json"}"',
                    'request_delay = 0',
                ]
            )
        )

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'bf-code', '--dry-run'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/unlock_pack.json code=ABCD-EFGH-AAAA\n')

    def test_default_state_file_sits_next_to_config_file(self):
        config = self.tmp_path / 'settings' / 'config.toml'
        config.parent.mkdir()
        config.write_text('[panini]\ncookie = "session=value"\n[panini.bf-code]\ncode_base = "ABCD-EFGH-IJKL"\n')
        attempts = []

        def fake_send_code(self, code):
            attempts.append(code)
            if code == self.code_base:
                return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
            return CodeResponse(text=GOOD_TRY_CODE_RESPONSE_TEXT, headers={'Content-Type': 'application/json'})

        with patch.object(BfCode, 'send_code', fake_send_code):
            result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'bf-code'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(attempts, ['ABCD-EFGH-IJKL', 'ABCD-EFGH-AAAA'])
        self.assertIn('Won 1 packs. Total packs: 2\n', result.output)
        self.assertTrue((config.parent / DEFAULT_STATE_FILE).exists())
