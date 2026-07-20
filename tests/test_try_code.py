import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.panini import API_ENDPOINT
from fifa_panini.commands.try_code import CodeResponse, TryCode


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
                'try',
                '--dry-run',
                '--code',
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
                'panini',
                '--cookie',
                'session=abc\u2026',
                'try',
                '--dry-run',
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
                    '[panini]',
                    'cookie = "session=value"',
                    'api_endpoint = "https://example.test/api/"',
                    '[panini.try]',
                    'code = "ABCD-EFGH-IJKL"',
                ]
            )
        )

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'try', '--dry-run'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/unlock_pack.json code=ABCD-EFGH-IJKL\n')
