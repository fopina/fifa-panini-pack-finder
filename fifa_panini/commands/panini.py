import classyclick

from ..cli import CLI
from ..utils.panini import (
    API_ENDPOINT,
    PANINI_API_ENDPOINT_META_KEY,
    PANINI_COOKIE_META_KEY,
)

__all__ = [
    'API_ENDPOINT',
    'PANINI_API_ENDPOINT_META_KEY',
    'PANINI_COOKIE_META_KEY',
    'Panini',
]


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
