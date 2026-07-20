import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.info import Info, InfoResponse
from fifa_panini.commands.open_pack import OPEN_PACK_BODY
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

        with patch('fifa_panini.commands.info.urlopen', fake_urlopen):
            response = command.get_info()

        self.assertEqual(captured['url'], 'https://paninicollection.fifa.com/api/init.json')
        self.assertEqual(captured['method'], 'POST')
        self.assertEqual(captured['data'], OPEN_PACK_BODY)
        self.assertEqual(captured['cookie'], 'session=value')
        self.assertEqual(captured['content_type'], 'application/x-www-form-urlencoded')
        self.assertEqual(captured['timeout'], 30.0)
        self.assertEqual(response.text, '{"ok":true}')

    def test_prints_only_json_response(self):
        config = self.write_config()

        with patch.object(Info, 'get_info', lambda _self: InfoResponse(text='{"ok":true}')):
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
        self.assertEqual(result.output, '{"ok":true}\n')

    def test_loads_cookie_from_config(self):
        config = self.write_config('\n'.join(['[panini]', 'cookie = "session=value"']))

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'info', '--dry-run'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'DRY RUN POST https://paninicollection.fifa.com/api/init.json json={}\n',
        )
