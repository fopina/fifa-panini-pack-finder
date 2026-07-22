import re
from pathlib import Path

import click
from tqdm import tqdm

from .actions import action, error_message, parse_action_list
from .panini import PaniniClient, PaniniResponse

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
    'UNLOCK_PACK_PATH',
]


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
        print(response.text)
        actions = parse_action_list(response)

        unlock_pack = self.action(actions, 'unlock_pack')
        if not unlock_pack:
            raise click.ClickException('Response did not include unlock pack information.')
        message = self.error_message(unlock_pack)
        if message:
            raise click.ClickException(message)

        received_packs = self.action(actions, 'received_packs')
        if not received_packs:
            raise click.ClickException('Response did not include received pack information.')

        tqdm.write(f'Won {received_packs.get("amount", 0)} packs. Total packs: {received_packs.get("total_packs", 0)}')

    def send_code(self, code):
        return self.panini_client.post_json(UNLOCK_PACK_PATH, {'code': code}, request_name=code)

    action = staticmethod(action)
    error_message = staticmethod(error_message)

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
