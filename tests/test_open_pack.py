import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.open_pack import OPEN_PACK_BODY, OpenPack
from fifa_panini.commands.panini import API_ENDPOINT


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class OpenPackTestCase(unittest.TestCase):
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
                'open',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'DRY RUN POST https://example.test/api/open_pack.json json={}\n')

    def test_sends_open_pack_request_with_shared_cookie(self):
        captured = {}
        command = OpenPack(dry_run=False, **panini_settings(cookie='session=value'))

        class FakeHeaders:
            @staticmethod
            def items():
                return [('Content-Type', 'application/json')]

        class FakeResponse:
            headers = FakeHeaders()

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc_value, _traceback):
                return False

            @staticmethod
            def read():
                return b'{"ok":true}'

        def fake_urlopen(request, timeout):
            captured['url'] = request.full_url
            captured['method'] = request.get_method()
            captured['data'] = request.data
            captured['cookie'] = request.headers['Cookie']
            captured['content_type'] = request.headers['Content-type']
            captured['timeout'] = timeout
            return FakeResponse()

        with patch('fifa_panini.commands.open_pack.urlopen', fake_urlopen):
            response = command.open_pack()

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/open_pack.json')
        self.assertEqual(captured['method'], 'POST')
        self.assertEqual(captured['data'], OPEN_PACK_BODY)
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_loads_cookie_from_config(self):
        config = self.write_config('\n'.join(['[panini]', 'cookie = "session=value"']))

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'open', '--dry-run'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'DRY RUN POST https://paninicollection.fifa.com/api/open_pack.json json={}\n',
        )
