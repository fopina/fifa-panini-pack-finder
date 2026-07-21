import json
from urllib.request import Request, urlopen

import classyclick
import click

from ..cli import CLI
from ..utils.codes import CodeResponse
from ..utils.panini import validate_cookie_header

DEFAULT_DAILY_PLAY_ENDPOINT = 'https://play.fifa.com/api/en/gamezone/panini/code'
DEFAULT_REQUEST_TIMEOUT = 30.0


class DailyPlay(CLI.Command):
    """Fetch the current FIFA Play daily promo code."""

    cookie: str = classyclick.Option(
        '-c',
        '--cookie',
        help='Complete Cookie header value copied from the daily Play code browser request.',
    )

    def __call__(self):
        self.validate_settings()

        response = self.send_code()
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def print_response(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Response was not valid JSON: {error}') from error

        if not isinstance(payload, dict):
            raise click.ClickException('Response JSON must be an object.')

        errors = payload.get('errors')
        if errors:
            raise click.ClickException(f'Response errors: {self.format_errors(errors)}')

        code = self.daily_code(payload)
        if not code:
            raise click.ClickException('Response did not include a daily promo code.')

        click.echo(code)

    @staticmethod
    def daily_code(payload):
        success = payload.get('success')
        if not isinstance(success, dict):
            return None

        panini_code = success.get('paniniCode')
        if not isinstance(panini_code, dict):
            return None

        code = panini_code.get('code')
        if not isinstance(code, str):
            return None

        code = code.strip()
        return code or None

    @staticmethod
    def format_errors(errors):
        if isinstance(errors, list):
            return ', '.join(DailyPlay.format_error(error) for error in errors)
        return DailyPlay.format_error(errors)

    @staticmethod
    def format_error(error):
        if isinstance(error, str):
            return error
        return json.dumps(error, separators=(',', ':'))

    def send_code(self):
        request = Request(
            DEFAULT_DAILY_PLAY_ENDPOINT,
            headers={
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:152.0) Gecko/20100101 Firefox/152.0',
                'Accept': '*/*',
                'Accept-Language': 'en-GB,en;q=0.9',
            },
            method='GET',
        )

        try:
            with urlopen(request, timeout=DEFAULT_REQUEST_TIMEOUT) as response:
                return CodeResponse(
                    text=response.read().decode('utf-8', errors='replace'),
                    headers=dict(response.headers.items()),
                )
        except OSError as error:
            raise click.ClickException(f'Request failed for {DEFAULT_DAILY_PLAY_ENDPOINT}: {error}') from error
