import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import classyclick
import click
from classyclick.helpers.config import ConfigBaseCommand, ConfigFileMixin
from classyclick.utils import _is_click_unset
from tqdm import tqdm

from . import __version__

DEFAULT_ENDPOINT = 'https://paninicollection.fifa.com/api/unlock_pack.json'
DEFAULT_STATE_FILE = '.fifa-panini-try-code-state.json'
DEFAULT_REQUEST_DELAY = 1.0
CONFIG_EXAMPLE_PATH = Path(__file__).with_name('config.example.toml')
INVALID_CODE_MARKER = '"code.invalid"'
CODE_BASE_PATTERN = re.compile(r'^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')
SUFFIX_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
TOTAL_SUFFIXES = len(SUFFIX_ALPHABET) ** 4


@dataclass(frozen=True)
class CodeResponse:
    text: str
    headers: dict[str, str]


class CLI(classyclick.Group):
    """Tools for testing FIFA Panini promo codes."""

    __config__ = classyclick.Group.Config(
        name='fifa-panini',
        decorators=[click.version_option(version=__version__)],
    )


class Config(ConfigFileMixin, ConfigBaseCommand, CLI.Command):
    """Show or edit the current CLI configuration."""

    CONFIG_DEFAULT_NAME = 'fifa-panini'
    CONFIG_EXAMPLE_PATH = CONFIG_EXAMPLE_PATH
    MASKED_FIELDS = (*ConfigBaseCommand.MASKED_FIELDS, 'cookie')

    env: str = classyclick.Option(help='Environment to use for the command.')

    def __call__(self):
        self.load_persistent_config()
        super().__call__()

    def load_persistent_config(self):
        if _is_click_unset(self.config):
            self.config = None
        if _is_click_unset(self.env):
            self.env = None
        if self.ctx is None:
            self.ctx = click.Context(type(self).click)
        self.load_config()


class TryCode(ConfigFileMixin, CLI.Command):
    """Try FIFA Panini promo codes by iterating the final block."""

    CONFIG_DEFAULT_NAME = 'fifa-panini'
    CONFIG_EXAMPLE_PATH = CONFIG_EXAMPLE_PATH

    env: str = classyclick.Option(help='Environment to use for the command.')
    code_base: str = classyclick.Option(
        help='Promo code base in XXXX-XXXX-XXXX format; the final block is iterated.',
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
    state_file: Path = classyclick.Option(
        '-s',
        default=Path(DEFAULT_STATE_FILE),
        show_default=True,
        help='Path used to save resume state.',
    )
    dry_run: bool = classyclick.Option(default=False, help='Print the request that would be attempted.')
    request_timeout: float = classyclick.Option(
        '--timeout',
        default=30.0,
        show_default=True,
        help='HTTP request timeout in seconds.',
    )
    request_delay: float = classyclick.Option(
        '--request-delay',
        default=DEFAULT_REQUEST_DELAY,
        show_default=True,
        help='Delay between requests in seconds.',
    )

    def __call__(self):
        self.load_persistent_config()
        self.validate_settings()

        if self.dry_run:
            code = self.next_code()
            tqdm.write(f'DRY RUN POST {self.endpoint} code={code}')
            return

        start = self.start_suffix()
        with tqdm(total=TOTAL_SUFFIXES, initial=start, unit='code') as progress:
            for code in self.iter_codes(start):
                progress.set_description(f'Testing {code}')
                self.save_state(code, self.suffix_from_code(code))
                response = self.send_code(code)

                if INVALID_CODE_MARKER not in response.text:
                    tqdm.write(f'Stopping at {code}: response did not contain {INVALID_CODE_MARKER}')
                    self.print_response(response)
                    return

                self.save_state(code, self.suffix_from_code(code) + 1)
                progress.update()
                if self.request_delay:
                    time.sleep(self.request_delay)

        raise click.ClickException(f'All {TOTAL_SUFFIXES} suffixes were tried without a non-invalid response.')

    def load_persistent_config(self):
        if _is_click_unset(self.config):
            self.config = None
        if _is_click_unset(self.env):
            self.env = None
        if self.ctx is None:
            self.ctx = click.Context(type(self).click)
        self.load_config()

    def validate_settings(self):
        missing = [name for name in ('code_base', 'cookie') if not getattr(self, name)]
        if missing:
            raise click.ClickException(
                f'Missing required setting(s): {", ".join(missing)}. '
                f'Pass them as options or save them in {self.config}.'
            )
        if not CODE_BASE_PATTERN.fullmatch(self.code_base):
            raise click.ClickException(
                '--code-base must be in XXXX-XXXX-XXXX format using only uppercase A-Z and 0-9 characters.'
            )
        if self.request_delay < 0:
            raise click.ClickException('--request-delay must be greater than or equal to 0.')

    def iter_codes(self, start=None):
        if start is None:
            start = self.start_suffix()
        for suffix in range(start, TOTAL_SUFFIXES):
            yield self.format_code(suffix)

    def next_code(self):
        start = self.start_suffix()
        if start >= TOTAL_SUFFIXES:
            raise click.ClickException(f'All {TOTAL_SUFFIXES} suffixes have already been tried for this code base.')

        return self.format_code(start)

    def start_suffix(self):
        state = self.load_state()
        if state is None:
            return 0

        if state.get('code_base') != self.code_base:
            return 0

        next_suffix = int(state.get('next_suffix', 0))
        return min(next_suffix, TOTAL_SUFFIXES)

    def load_state(self):
        state_file = self.state_path
        if not state_file.exists():
            return None

        try:
            with state_file.open() as state:
                return json.load(state)
        except (OSError, json.JSONDecodeError) as error:
            raise click.ClickException(f'Could not read state file {state_file}: {error}') from error

    def save_state(self, code, next_suffix):
        state = {
            'code_base': self.code_base,
            'current_code': code,
            'next_suffix': next_suffix,
        }
        state_file = self.state_path
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with state_file.open('w') as file:
                json.dump(state, file, indent=2)
                file.write('\n')
        except OSError as error:
            raise click.ClickException(f'Could not write state file {state_file}: {error}') from error

    def suffix_from_code(self, code):
        suffix = 0
        for character in code[-4:]:
            suffix = suffix * len(SUFFIX_ALPHABET) + SUFFIX_ALPHABET.index(character)
        return suffix

    def format_code(self, suffix):
        characters = []
        for _ in range(4):
            suffix, index = divmod(suffix, len(SUFFIX_ALPHABET))
            characters.append(SUFFIX_ALPHABET[index])
        return f'{self.code_base[:-4]}{"".join(reversed(characters))}'

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
        if state_file.is_absolute() or not getattr(self, 'config', None):
            return state_file

        return Path(self.config).parent / state_file
