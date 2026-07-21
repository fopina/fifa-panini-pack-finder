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

StickersResponse = PaniniResponse


class Stickers(Panini.Command):
    """Print FIFA Panini sticker lists from the current collection state."""

    __config__ = classyclick.Command.Config(name='stickers')

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(default=False, help='Print the request that would be attempted.')
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

    def __call__(self):
        self.validate_settings()

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

    def print_response(self, response):
        other_album_stickers = self.parse_sticker_list(self.swap_out, '--swap-out')
        other_duplicate_stickers = self.parse_sticker_list(self.swap_in, '--swap-in')

        try:
            actions = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Response was not valid JSON: {error}') from error

        if not isinstance(actions, list):
            raise click.ClickException('Response JSON must be an array of action objects.')

        init = self.action(actions, 'init')
        stacks = init.get('stacks') or {}
        if not init or not isinstance(stacks, dict):
            raise click.ClickException('Response did not include init sticker stacks.')

        album_stickers = self.sticker_numbers(stacks.get('album') or [])
        new_stickers = self.sticker_numbers(stacks.get('temp') or [])
        swap_stickers = self.sticker_numbers(stacks.get('swap') or [])
        non_album_stickers = new_stickers + swap_stickers
        album_sticker_set = set(album_stickers)

        duplicate_stickers = [sticker for sticker in non_album_stickers if sticker in album_sticker_set]
        stickers_to_glue = [sticker for sticker in non_album_stickers if sticker not in album_sticker_set]
        own_sticker_set = album_sticker_set | set(non_album_stickers)

        other_album_sticker_set = set(other_album_stickers)
        offer_stickers = [sticker for sticker in duplicate_stickers if sticker not in other_album_sticker_set]
        ask_stickers = [sticker for sticker in other_duplicate_stickers if sticker not in own_sticker_set]

        click.echo(f'Owned stickers: {self.format_stickers(album_stickers)}')
        click.echo(f'New DUPLICATE stickers: {self.format_stickers(duplicate_stickers)}')
        click.echo(f'Swap stickers: {self.format_stickers(swap_stickers)}')
        click.echo(f'New Stickers to glue: {self.format_stickers(stickers_to_glue)}')
        if self.swap_out or self.swap_in:
            click.echo(f'Offer: {self.format_stickers(offer_stickers)}')
            click.echo(f'Ask: {self.format_stickers(ask_stickers)}')

    @classmethod
    def sticker_numbers(cls, stickers):
        return [sticker for sticker in (cls.sticker_number(item) for item in stickers) if sticker is not None]

    @staticmethod
    def sticker_number(item):
        if isinstance(item, (list, tuple)):
            if not item:
                return None
            return item[0]
        return item

    @staticmethod
    def format_stickers(stickers):
        if not stickers:
            return '(none)'
        return ', '.join(str(sticker) for sticker in stickers)

    @staticmethod
    def parse_sticker_list(value, option_name):
        if not value:
            return []

        stickers = []
        for raw_sticker in value.split(','):
            sticker = raw_sticker.strip()
            if not sticker:
                raise click.ClickException(f'{option_name} must be a comma-separated list of sticker numbers.')
            try:
                stickers.append(int(sticker))
            except ValueError as error:
                raise click.ClickException(f'{option_name} includes an invalid sticker number: {sticker}') from error
        return stickers

    @staticmethod
    def action(actions, name):
        for action in actions:
            if isinstance(action, dict) and action.get('action') == name:
                return action
        return {}
