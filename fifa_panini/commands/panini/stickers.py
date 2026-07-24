import classyclick
import click

from ...utils.actions import action
from ...utils.panini import DEFAULT_REQUEST_TIMEOUT, PaniniClient, PaniniResponse, validate_cookie_header
from ...utils.stickers import format_stickers, init_stacks, parse_sticker_list, sticker_number, sticker_numbers
from . import PANINI_API_ENDPOINT_META_KEY, PANINI_COOKIE_META_KEY, Panini
from .info import INFO_PATH

StickersResponse = PaniniResponse


class Stickers(Panini.Command):
    """Print FIFA Panini sticker lists from the current collection state."""

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(help='Print the request that would be attempted.')
    swap_out: str = classyclick.Option(
        '--swap-out',
        help='Sticker numbers in the other player album, comma separated.',
    )
    swap_in: str = classyclick.Option(
        '--swap-in',
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

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.panini_client.endpoint(INFO_PATH)} json={{}}')
            return

        response = self.panini_client.post_json(INFO_PATH, request_name='stickers')
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def print_response(self, response):
        other_album_stickers = self.parse_sticker_list(self.swap_out, '--swap-out')
        other_duplicate_stickers = self.parse_sticker_list(self.swap_in, '--swap-in')

        stacks = init_stacks(response)
        album_stickers = sticker_numbers(stacks.get('album') or [])
        temp_stickers = sticker_numbers(stacks.get('temp') or [])
        swap_stickers = sticker_numbers(stacks.get('swap') or [])
        loose_stickers = temp_stickers + swap_stickers
        album_sticker_set = set(album_stickers)

        duplicate_stickers = [sticker for sticker in temp_stickers if sticker in album_sticker_set]
        swap_duplicate_stickers = [sticker for sticker in swap_stickers if sticker in album_sticker_set]
        new_stickers = [sticker for sticker in temp_stickers if sticker not in album_sticker_set]
        swap_non_duplicate_stickers = [sticker for sticker in swap_stickers if sticker not in album_sticker_set]
        own_sticker_set = album_sticker_set | set(loose_stickers)

        other_album_sticker_set = set(other_album_stickers)
        duplicate_offer_stickers = duplicate_stickers + swap_duplicate_stickers
        offer_stickers = [
            sticker
            for sticker in (duplicate_offer_stickers if not self.swap_new else loose_stickers)
            if sticker not in other_album_sticker_set
        ]
        ask_stickers = [sticker for sticker in other_duplicate_stickers if sticker not in own_sticker_set]

        click.echo(f'Owned stickers: {format_stickers(album_stickers)}')
        if duplicate_stickers:
            click.echo(f'New DUPLICATE stickers: {format_stickers(duplicate_stickers)}')
        click.echo(f'Swap stickers: {format_stickers(swap_stickers)}')
        click.echo(f'New stickers: {format_stickers(new_stickers)}')
        if swap_non_duplicate_stickers:
            click.echo(f'Non-duplicate stickers in swap: {format_stickers(swap_non_duplicate_stickers)}')
        if self.swap_out or self.swap_in:
            click.echo(f'Offer: {format_stickers(offer_stickers)}')
            click.echo(f'Ask: {format_stickers(ask_stickers)}')

    action = staticmethod(action)
    parse_sticker_list = staticmethod(parse_sticker_list)
    sticker_number = staticmethod(sticker_number)
    sticker_numbers = staticmethod(sticker_numbers)
    format_stickers = staticmethod(format_stickers)
