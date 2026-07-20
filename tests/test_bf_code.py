import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import click
from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.bf_code import BfCode
from fifa_panini.commands.try_code import DEFAULT_STATE_FILE, TOTAL_SUFFIXES, CodeResponse


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
        command = BfCode(code_base='ABCD-EFGH-IJKL', cookie='session=value')

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
                'bf-code',
                '--dry-run',
                '--cookie',
                'session=value',
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
                'bf-code',
                '--dry-run',
                '--cookie',
                'session=value',
                '--endpoint',
                'https://example.test/redeem',
                '--code-base',
                'ABCD-EFGH-IJKL',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-AAAA\n')

    def test_resumes_from_state_file(self):
        state_file = self.tmp_path / 'state.json'
        state_file.write_text('{"code_base": "ABCD-EFGH-IJKL", "current_code": "ABCD-EFGH-AABF", "next_suffix": 42}\n')
        command = BfCode(code_base='ABCD-EFGH-IJKL', cookie='session=value', state_file=state_file)

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
            cookie='session=value',
            dry_run=False,
            state_file=state_file,
        )

        def fake_send_code(code):
            text = '{"error":"code.already_used"}' if code == command.code_base else '{"ok":true}'
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
            cookie='session=value',
            dry_run=False,
            state_file=self.tmp_path / 'state.json',
        )

        def fake_send_code(code):
            attempts.append(code)
            if code == command.code_base:
                return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
            if len(attempts) == 2:
                return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
            return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json', 'X-Pack': 'found'})

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
            cookie='session=value',
            dry_run=False,
            state_file=self.tmp_path / 'state.json',
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
            cookie='session=value',
            dry_run=False,
            request_delay=0.25,
            state_file=self.tmp_path / 'state.json',
        )

        def fake_send_code(code):
            attempts.append(code)
            if code == command.code_base:
                return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
            if len(attempts) == 2:
                return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
            return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

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
            cookie='session=value',
            dry_run=False,
            request_delay=0,
            state_file=self.tmp_path / 'state.json',
        )

        def fake_send_code(code):
            attempts.append(code)
            if code == command.code_base:
                return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
            if len(attempts) == 2:
                return CodeResponse(text='{"error":"code.invalid"}', headers={'Content-Type': 'application/json'})
            return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

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
                'bf-code',
                '--dry-run',
                '--cookie',
                'session=value',
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
                    '[bf-code]',
                    'code_base = "ABCD-EFGH-IJKL"',
                    'cookie = "session=value"',
                    'endpoint = "https://example.test/redeem"',
                    f'state_file = "{self.tmp_path / "state.json"}"',
                    'request_delay = 0',
                ]
            )
        )

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'bf-code', '--dry-run'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-AAAA\n')

    def test_default_state_file_sits_next_to_config_file(self):
        config = self.tmp_path / 'settings' / 'config.toml'
        config.parent.mkdir()
        config.write_text('[bf-code]\ncode_base = "ABCD-EFGH-IJKL"\ncookie = "session=value"\n')
        attempts = []

        def fake_send_code(self, code):
            attempts.append(code)
            if code == self.code_base:
                return CodeResponse(text='{"error":"code.already_used"}', headers={'Content-Type': 'application/json'})
            return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

        with patch.object(BfCode, 'send_code', fake_send_code):
            result = CliRunner().invoke(CLI.click, ['--config', str(config), 'bf-code'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(attempts, ['ABCD-EFGH-IJKL', 'ABCD-EFGH-AAAA'])
        self.assertIn('Response headers:\nContent-Type: application/json\nResponse text:\n{"ok":true}\n', result.output)
        self.assertTrue((config.parent / DEFAULT_STATE_FILE).exists())
