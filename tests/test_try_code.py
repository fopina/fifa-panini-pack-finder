import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.try_code import CodeResponse, TryCode


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
                'try-code',
                '--dry-run',
                '--cookie',
                'session=value',
                '--endpoint',
                'https://example.test/redeem',
                '--code',
                'ABCD-EFGH-IJKL',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-IJKL\n')

    def test_sends_only_passed_code(self):
        attempts = []
        command = TryCode(
            code='ABCD-EFGH-IJKL',
            cookie='session=value',
            dry_run=False,
        )

        def fake_send_code(code):
            attempts.append(code)
            return CodeResponse(text='{"ok":true}', headers={'Content-Type': 'application/json'})

        with patch.object(command, 'send_code', fake_send_code):
            command()

        self.assertEqual(attempts, ['ABCD-EFGH-IJKL'])

    def test_rejects_cookie_with_unicode_ellipsis(self):
        config = self.write_config()

        result = CliRunner().invoke(
            CLI.click,
            [
                '--config',
                str(config),
                'try-code',
                '--dry-run',
                '--cookie',
                'session=abc\u2026',
                '--code',
                'ABCD-EFGH-IJKL',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(r'Cookie contains \u2026', result.output)

    def test_loads_settings_from_config(self):
        config = self.write_config(
            '\n'.join(
                [
                    '[try-code]',
                    'code = "ABCD-EFGH-IJKL"',
                    'cookie = "session=value"',
                    'endpoint = "https://example.test/redeem"',
                ]
            )
        )

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'try-code', '--dry-run'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/redeem code=ABCD-EFGH-IJKL\n')
