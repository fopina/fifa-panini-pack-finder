import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fifa_panini.cli import CLI
from fifa_panini.commands.claim import CLAIM_PACKS_BODY, Claim
from fifa_panini.commands.panini import API_ENDPOINT


def panini_settings(cookie='session=value', api_endpoint=API_ENDPOINT):
    return {'cookie': cookie, 'api_endpoint': api_endpoint}


class ClaimTestCase(unittest.TestCase):
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
        requests = []

        class FakeResponse:
            headers = {'Content-Type': 'application/json'}

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc_value, _traceback):
                return False

            def read(self):
                return b'{"ok":true}'

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with patch('fifa_panini.commands.claim.urlopen', fake_urlopen):
            result = CliRunner().invoke(
                CLI.click,
                [
                    '--config',
                    str(config),
                    'panini',
                    '--cookie',
                    'session=value',
                    'claim',
                ],
            )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'Response headers:\nContent-Type: application/json\nResponse text:\n{"ok":true}\n',
        )
        request, timeout = requests[0]
        self.assertEqual(request.full_url, 'https://paninicollection.fifa.com/api/receive_daily_packs.json')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.data, CLAIM_PACKS_BODY)
        self.assertEqual(request.get_header('Cookie'), 'session=value')
        self.assertEqual(request.get_header('Content-type'), 'application/x-www-form-urlencoded')
        self.assertEqual(timeout, 30.0)

    def test_dry_run_prints_request(self):
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
                'claim',
                '--dry-run',
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'DRY RUN POST https://example.test/api/receive_daily_packs.json json={}\n',
        )

    def test_loads_cookie_from_panini_config(self):
        config = self.write_config('[panini]\ncookie = "session=value"\n')
        requests = []

        class FakeResponse:
            headers = {'Content-Type': 'application/json'}

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc_value, _traceback):
                return False

            def read(self):
                return b'{"ok":true}'

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with patch('fifa_panini.commands.claim.urlopen', fake_urlopen):
            result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'claim'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(requests[0][0].get_header('Cookie'), 'session=value')

    def test_requires_cookie(self):
        config = self.write_config()

        result = CliRunner().invoke(CLI.click, ['--config', str(config), 'panini', 'claim'])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Missing required setting(s): cookie', result.output)

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
                'claim',
                '--dry-run',
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(r'Cookie contains \u2026', result.output)

    def test_sends_claim_request(self):
        command = Claim(**panini_settings(cookie='session=value'))
        requests = []

        class FakeResponse:
            headers = {'Content-Type': 'application/json'}

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc_value, _traceback):
                return False

            def read(self):
                return b'{"claimed":true}'

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with patch('fifa_panini.commands.claim.urlopen', fake_urlopen):
            response = command.claim_packs()

        self.assertEqual(response.text, '{"claimed":true}')
        self.assertEqual(response.headers, {'Content-Type': 'application/json'})
        self.assertEqual(requests[0][0].full_url, 'https://paninicollection.fifa.com/api/receive_daily_packs.json')
        self.assertEqual(requests[0][0].data, b'json=%7b%7d&locale=en')
