import classyclick

from ..cli import CLI

DEFAULT_ENDPOINT = 'https://paninicollection.fifa.com/api/unlock_pack.json'
PANINI_COOKIE_META_KEY = 'panini_cookie'
PANINI_ENDPOINT_META_KEY = 'panini_endpoint'


class Panini(CLI.SubGroup):
    """Try and brute-force FIFA Panini promo codes."""

    cookie: str = classyclick.Option(
        '-c',
        '--cookie',
        help='Complete Cookie header value copied from the browser request.',
    )
    endpoint: str = classyclick.Option(
        default=DEFAULT_ENDPOINT,
        show_default=True,
        help='Endpoint URL to test against.',
    )
    ctx: classyclick.Context = classyclick.Context()

    def __call__(self):
        self.ctx.meta[PANINI_COOKIE_META_KEY] = self.cookie
        self.ctx.meta[PANINI_ENDPOINT_META_KEY] = self.endpoint
