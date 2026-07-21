import json
import re
from pathlib import Path

import classyclick
import click
from tqdm import tqdm

from .panini import (
    DEFAULT_REQUEST_TIMEOUT,
    PANINI_API_ENDPOINT_META_KEY,
    PANINI_COOKIE_META_KEY,
    Panini,
    PaniniClient,
    PaniniResponse,
    validate_cookie_header,
)

DEFAULT_STATE_FILE = '.fifa-panini-try-code-state.json'
DEFAULT_REQUEST_DELAY = 1.0
UNLOCK_PACK_PATH = 'unlock_pack.json'
INVALID_CODE_MARKER = '"code.invalid"'
CODE_ALREADY_USED_MARKER = '"code.already_used"'
CODE_PATTERN = re.compile(r'^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')
CODE_BASE_PATTERN = CODE_PATTERN
SUFFIX_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
TOTAL_SUFFIXES = len(SUFFIX_ALPHABET) ** 4


CodeResponse = PaniniResponse


class CodeMethodsMixin:
    @property
    def unlock_pack_endpoint(self):
        return self.panini_client.endpoint(UNLOCK_PACK_PATH)

    @property
    def panini_client(self):
        return PaniniClient(self.cookie, self.api_endpoint, self.request_timeout)

    def validate_code(self, code, option_name):
        if not CODE_PATTERN.fullmatch(code):
            raise click.ClickException(
                f'{option_name} must be in XXXX-XXXX-XXXX format using only uppercase A-Z and 0-9 characters.'
            )

    def print_response(self, response):
        try:
            actions = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Response was not valid JSON: {error}') from error

        if not isinstance(actions, list):
            raise click.ClickException('Response JSON must be an array of action objects.')

        error_message = self.error_message(actions)
        if error_message:
            raise click.ClickException(error_message)

        received_packs = self.action(actions, 'received_packs')
        if not received_packs:
            raise click.ClickException('Response did not include received pack information.')

        tqdm.write(f'Won {received_packs.get("amount", 0)} packs. Total packs: {received_packs.get("total_packs", 0)}')

    def send_code(self, code):
        return self.panini_client.post_json(UNLOCK_PACK_PATH, {'code': code}, request_name=code)

    @staticmethod
    def action(actions, name):
        for action in actions:
            if isinstance(action, dict) and action.get('action') == name:
                return action
        return {}

    @staticmethod
    def error_message(actions):
        for action in actions:
            if not isinstance(action, dict) or 'error' not in action:
                continue

            error = action['error']
            if isinstance(error, dict):
                return error.get('message') or str(error)
            return str(error)
        return None

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
