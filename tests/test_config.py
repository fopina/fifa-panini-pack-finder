import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from fifa_panini.cli import CLI


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.tmp_path = Path(self.tempdir.name)

    def test_config_command_masks_cookie(self):
        config = self.tmp_path / 'config.toml'
        config.write_text('[panini]\ncookie = "session=value"\n[panini.bf]\ncode_base = "ABCD-EFGH-IJKL"\n')

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'config'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('"cookie": "<masked>"', result.output)
