from urllib.parse import urljoin

import classyclick
import click

from ..cli import CLI

API_ENDPOINT = 'https://paninicollection.fifa.com/api/'
PANINI_COOKIE_META_KEY = 'panini_cookie'
PANINI_API_ENDPOINT_META_KEY = 'panini_api_endpoint'


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
