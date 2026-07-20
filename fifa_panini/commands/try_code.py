import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import classyclick
import click
from tqdm import tqdm

from ..cli import CLI

DEFAULT_ENDPOINT = 'https://paninicollection.fifa.com/api/unlock_pack.json'
DEFAULT_STATE_FILE = '.fifa-panini-try-code-state.json'
DEFAULT_REQUEST_DELAY = 1.0
INVALID_CODE_MARKER = '"code.invalid"'
CODE_ALREADY_USED_MARKER = '"code.already_used"'
CODE_PATTERN = re.compile(r'^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')
CODE_BASE_PATTERN = CODE_PATTERN
SUFFIX_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
TOTAL_SUFFIXES = len(SUFFIX_ALPHABET) ** 4


@dataclass(frozen=True)
class CodeResponse:
    text: str
    headers: dict[str, str]


class CodeMethodsMixin:
    def validate_code(self, code, option_name):
        if not CODE_PATTERN.fullmatch(code):
            raise click.ClickException(
                f'{option_name} must be in XXXX-XXXX-XXXX format using only uppercase A-Z and 0-9 characters.'
            )

    def print_response(self, response):
        tqdm.write('Response headers:')
        for name, value in response.headers.items():
            tqdm.write(f'{name}: {value}')
        tqdm.write('Response text:')
        tqdm.write(response.text, end='' if response.text.endswith('\n') else '\n')

    def send_code(self, code):
        payload = urlencode({'json': json.dumps({'code': code}, separators=(',', ':')), 'locale': 'en'}).encode()
        request = Request(
            self.endpoint,
            data=payload,
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
                return CodeResponse(
                    text=response.read().decode('utf-8', errors='replace'),
                    headers=dict(response.headers.items()),
                )
        except OSError as error:
            raise click.ClickException(f'Request failed for {code}: {error}') from error

    @property
    def state_path(self):
        state_file = Path(self.state_file)
        config_path = self.config_path
        if state_file.is_absolute() or config_path is None:
            return state_file

        return config_path.parent / state_file

    @property
    def config_path(self):
        ctx = click.get_current_context(silent=True)
        if ctx is None:
            return None

        config_path = ctx.meta.get('config_path')
        if config_path is None:
            return None

        return Path(config_path)


class TryCode(CodeMethodsMixin, CLI.Command):
    """Try one FIFA Panini promo code."""

    code: str = classyclick.Option(
        help='Promo code in XXXX-XXXX-XXXX format.',
    )
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
    dry_run: bool = classyclick.Option(default=False, help='Print the request that would be attempted.')
    request_timeout: float = classyclick.Option(
        '--timeout',
        default=30.0,
        show_default=True,
        help='HTTP request timeout in seconds.',
    )

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            tqdm.write(f'DRY RUN POST {self.endpoint} code={self.code}')
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
        self.validate_code(self.code, '--code')
