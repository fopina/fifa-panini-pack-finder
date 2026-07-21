import json

import classyclick
import click

from .info import INFO_PATH
from .panini import (
    DEFAULT_REQUEST_TIMEOUT,
    PANINI_API_ENDPOINT_META_KEY,
    PANINI_COOKIE_META_KEY,
    Panini,
    PaniniClient,
    PaniniResponse,
    validate_cookie_header,
)
from .sticker_stacks import action, format_stickers, init_stacks, parse_sticker_list, sticker_number, sticker_numbers

StickersResponse = PaniniResponse
MOVE_STICKERS_PATH = 'move_stickers.json'


class Stickers(Panini.Command):
    """Print FIFA Panini sticker lists from the current collection state."""

    __config__ = classyclick.Command.Config(name='stickers')

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(default=False, help='Print the request that would be attempted.')
    move: str = classyclick.Option(
        '--move',
        default='',
        help='Sticker numbers to move from temp to swap, comma separated.',
    )
    swap_out: str = classyclick.Option(
        '--swap-out',
        default='',
        help='Sticker numbers in the other player album, comma separated.',
    )
    swap_in: str = classyclick.Option(
        '--swap-in',
        default='',
        help='Sticker numbers in the other player duplicates, comma separated.',
    )
    swap_new: bool = classyclick.Option(
        help='If used, NEW stickers will also be considered for offers, instead of restricting those to DUPLICATES'
    )
    request_timeout: float = classyclick.Option(
        '--timeout',
        default=DEFAULT_REQUEST_TIMEOUT,
        show_default=True,
        help='HTTP request timeout in seconds.',
    )

    @property
    def panini_client(self):
        return PaniniClient(self.cookie, self.api_endpoint, self.request_timeout)

    @property
    def stickers_endpoint(self):
        return self.panini_client.endpoint(INFO_PATH)

    @property
    def move_endpoint(self):
        return self.panini_client.endpoint(MOVE_STICKERS_PATH)

    def __call__(self):
        self.validate_settings()

        if self.move:
            stickers_to_move = self.parse_sticker_list(self.move, '--move')
            payload = self.move_payload(stickers_to_move)
            if self.dry_run:
                json_payload = PaniniClient.form_data(payload)['json']
                click.echo(f'DRY RUN POST {self.move_endpoint} json={json_payload}')
                return

            response = self.move_stickers(stickers_to_move)
            self.validate_move_response(response)
            click.echo(f'Moved stickers to swap: {format_stickers(stickers_to_move)}')
            return

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.stickers_endpoint} json={{}}')
            return

        response = self.get_stickers()
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def get_stickers(self):
        return self.panini_client.post_json(INFO_PATH, request_name='stickers')

    def move_stickers(self, stickers):
        return self.panini_client.post_json(
            MOVE_STICKERS_PATH,
            payload=self.move_payload(stickers),
            request_name='move stickers',
        )

    @staticmethod
    def move_payload(stickers):
        return {'from': 'temp', 'to': {'swap': stickers}}

    @classmethod
    def validate_move_response(cls, response):
        try:
            actions = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Move stickers response was not valid JSON: {error}') from error

        if not isinstance(actions, list):
            raise click.ClickException('Move stickers response JSON must be an array.')

        move_action = action(actions, 'move_stickers')
        if not move_action:
            raise click.ClickException('Response did not include move_stickers confirmation.')

        if 'error' in move_action:
            raise click.ClickException(cls.error_message(move_action['error']))

    @staticmethod
    def error_message(error):
        if isinstance(error, dict):
            return error.get('message') or str(error)
        return str(error)

    def print_response(self, response):
        other_album_stickers = self.parse_sticker_list(self.swap_out, '--swap-out')
        other_duplicate_stickers = self.parse_sticker_list(self.swap_in, '--swap-in')

        stacks = init_stacks(response)
        album_stickers = sticker_numbers(stacks.get('album') or [])
        new_stickers = sticker_numbers(stacks.get('temp') or [])
        swap_stickers = sticker_numbers(stacks.get('swap') or [])
        non_album_stickers = new_stickers + swap_stickers
        album_sticker_set = set(album_stickers)

        duplicate_stickers = [sticker for sticker in non_album_stickers if sticker in album_sticker_set]
        stickers_to_glue = [sticker for sticker in non_album_stickers if sticker not in album_sticker_set]
        own_sticker_set = album_sticker_set | set(non_album_stickers)

        other_album_sticker_set = set(other_album_stickers)
        offer_stickers = [
            sticker
            for sticker in (duplicate_stickers if not self.swap_new else non_album_stickers)
            if sticker not in other_album_sticker_set
        ]
        ask_stickers = [sticker for sticker in other_duplicate_stickers if sticker not in own_sticker_set]

        click.echo(f'Owned stickers: {format_stickers(album_stickers)}')
        click.echo(f'New DUPLICATE stickers: {format_stickers(duplicate_stickers)}')
        click.echo(f'Swap stickers: {format_stickers(swap_stickers)}')
        click.echo(f'New Stickers to glue: {format_stickers(stickers_to_glue)}')
        if self.swap_out or self.swap_in:
            click.echo(f'Offer: {format_stickers(offer_stickers)}')
            click.echo(f'Ask: {format_stickers(ask_stickers)}')

    action = staticmethod(action)
    parse_sticker_list = staticmethod(parse_sticker_list)
    sticker_number = staticmethod(sticker_number)
    sticker_numbers = staticmethod(sticker_numbers)
    format_stickers = staticmethod(format_stickers)
