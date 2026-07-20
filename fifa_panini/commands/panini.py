from dataclasses import dataclass
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import classyclick
import click

from ..cli import CLI

API_ENDPOINT = 'https://paninicollection.fifa.com/api/'
OPEN_PACK_BODY = b'json=%7b%7d&locale=en'
PANINI_COOKIE_META_KEY = 'panini_cookie'
PANINI_API_ENDPOINT_META_KEY = 'panini_api_endpoint'


@dataclass(frozen=True)
class PackResponse:
    text: str
    headers: dict[str, str]


def validate_cookie_header(cookie):
    try:
        cookie.encode('latin-1')
    except UnicodeEncodeError as error:
        character = error.object[error.start : error.end].encode('unicode_escape').decode('ascii')
        raise click.ClickException(
            f'Cookie contains {character}, which cannot be sent in an HTTP header. '
            'Re-copy the complete Cookie header from browser developer tools; copied previews are often truncated.'
        ) from error


def api_url(api_endpoint, path):
    return urljoin(f'{api_endpoint.rstrip("/")}/', path)


class Panini(CLI.SubGroup):
    """Try and brute-force FIFA Panini promo codes."""

    cookie: str = classyclick.Option(
        '-c',
        '--cookie',
        help='Complete Cookie header value copied from the browser request.',
    )
    api_endpoint: str = classyclick.Option(
        '--api-endpoint',
        default=API_ENDPOINT,
        show_default=True,
        help='Panini API base URL.',
    )
    ctx: classyclick.Context = classyclick.Context()

    def __call__(self):
        self.ctx.meta[PANINI_COOKIE_META_KEY] = self.cookie
        self.ctx.meta[PANINI_API_ENDPOINT_META_KEY] = self.api_endpoint


class OpenPack(Panini.Command):
    """Open a FIFA Panini pack."""

    __config__ = classyclick.Command.Config(name='open')

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(default=False, help='Print the request that would be attempted.')
    request_timeout: float = classyclick.Option(
        '--timeout',
        default=30.0,
        show_default=True,
        help='HTTP request timeout in seconds.',
    )

    @property
    def pack_endpoint(self):
        return api_url(self.api_endpoint, 'open_pack.json')

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.pack_endpoint} json={{}}')
            return

        response = self.open_pack()
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def open_pack(self):
        validate_cookie_header(self.cookie)
        request = Request(
            self.pack_endpoint,
            data=OPEN_PACK_BODY,
            headers={
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:152.0) Gecko/20100101 Firefox/152.0',
                'Accept': '*/*',
                'Accept-Language': 'en-GB,en;q=0.9',
                'Referer': 'https://paninicollection.fifa.com/game/flash',
                'X-User-Agent': 'Unity/1.3.0 (MacOS 10.15) Unity/6000.0.65f1 webgl_hires',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://paninicollection.fifa.com',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Gpc': '1',
                'Priority': 'u=4',
            },
            method='POST',
        )

        try:
            with urlopen(request, timeout=self.request_timeout) as response:
                return PackResponse(
                    text=response.read().decode('utf-8', errors='replace'),
                    headers=dict(response.headers.items()),
                )
        except OSError as error:
            raise click.ClickException(f'Request failed for open pack: {error}') from error

    def print_response(self, response):
        click.echo('Response headers:')
        for name, value in response.headers.items():
            click.echo(f'{name}: {value}')
        click.echo('Response text:')
        click.echo(response.text, nl=not response.text.endswith('\n'))
