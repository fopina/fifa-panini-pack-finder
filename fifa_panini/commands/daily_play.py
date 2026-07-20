from urllib.request import Request, urlopen

import classyclick
import click

from ..cli import CLI
from .panini import validate_cookie_header
from .try_code import CodeResponse

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
        click.echo('Response headers:')
        for name, value in response.headers.items():
            click.echo(f'{name}: {value}')
        click.echo('Response text:')
        click.echo(response.text, nl=not response.text.endswith('\n'))

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
