import classyclick
import click
from tqdm import tqdm

from ..utils.codes import (
    CODE_ALREADY_USED_MARKER,
    CODE_BASE_PATTERN,
    CODE_PATTERN,
    DEFAULT_REQUEST_DELAY,
    DEFAULT_STATE_FILE,
    INVALID_CODE_MARKER,
    SUFFIX_ALPHABET,
    TOTAL_SUFFIXES,
    UNLOCK_PACK_PATH,
    CodeMethodsMixin,
    CodeResponse,
)
from ..utils.panini import (
    DEFAULT_REQUEST_TIMEOUT,
    validate_cookie_header,
)
from .panini import PANINI_API_ENDPOINT_META_KEY, PANINI_COOKIE_META_KEY, Panini

__all__ = [
    'CODE_ALREADY_USED_MARKER',
    'CODE_BASE_PATTERN',
    'CODE_PATTERN',
    'CodeMethodsMixin',
    'CodeResponse',
    'DEFAULT_REQUEST_DELAY',
    'DEFAULT_STATE_FILE',
    'INVALID_CODE_MARKER',
    'SUFFIX_ALPHABET',
    'TOTAL_SUFFIXES',
    'TryCode',
    'UNLOCK_PACK_PATH',
]


class TryCode(CodeMethodsMixin, Panini.Command):
    """Try one FIFA Panini promo code."""

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    code: str = classyclick.Argument()
    dry_run: bool = classyclick.Option(help='Print the request that would be attempted.')
    request_timeout: float = classyclick.Option(
        '--timeout',
        default=DEFAULT_REQUEST_TIMEOUT,
        show_default=True,
        help='HTTP request timeout in seconds.',
    )

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            tqdm.write(f'DRY RUN POST {self.unlock_pack_endpoint} code={self.code}')
            return

        response = self.send_code(self.code)
        self.print_response(response)

    def validate_settings(self):
        missing = [name for name in ('code', 'cookie') if not getattr(self, name)]
        if missing:
            raise click.ClickException(
                f'Missing required setting(s): {", ".join(missing)}. '
                f'Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)
        self.validate_code(self.code, 'code')
