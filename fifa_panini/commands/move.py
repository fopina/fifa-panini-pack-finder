import classyclick
import click

from ..utils.actions import action, format_error, parse_action_list
from ..utils.panini import (
    DEFAULT_REQUEST_TIMEOUT,
    PaniniClient,
    PaniniResponse,
    validate_cookie_header,
)
from ..utils.stickers import format_stickers, init_stacks, parse_sticker_list, sticker_numbers
from .info import INFO_PATH
from .panini import PANINI_API_ENDPOINT_META_KEY, PANINI_COOKIE_META_KEY, Panini

MOVE_STICKERS_PATH = 'move_stickers.json'
MOVABLE_STACKS = ('temp', 'swap', 'album')
MoveResponse = PaniniResponse


class Move(Panini.Command):
    """Move FIFA Panini stickers to a target stack."""

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    target: str = classyclick.Argument(type=click.Choice(['temp', 'album', 'swap']), metavar='TARGET')
    stickers: str = classyclick.Argument(metavar='STICKERS')
    dry_run: bool = classyclick.Option(help='Print move requests without performing them.')
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

        stickers_to_move = parse_sticker_list(self.stickers, 'STICKERS')
        info_response = self.panini_client.post_json(INFO_PATH, request_name='info')
        move_groups, already_in_target = self.group_moves(stickers_to_move, info_response)

        for source, source_stickers in move_groups.items():
            payload = {'from': source, 'to': {self.target: source_stickers}}
            if self.dry_run:
                json_payload = PaniniClient.form_data(payload)['json']
                click.echo(f'DRY RUN POST {self.panini_client.endpoint(MOVE_STICKERS_PATH)} json={json_payload}')
                continue

            response = self.panini_client.post_json(
                MOVE_STICKERS_PATH,
                payload=payload,
                request_name='move stickers',
            )
            self.validate_response(response)
            click.echo(f'Moved stickers from {source} to {self.target}: {format_stickers(source_stickers)}')

        if already_in_target:
            click.echo(f'Already in {self.target}: {format_stickers(already_in_target)}')

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    @classmethod
    def validate_response(cls, response):
        actions = parse_action_list(
            response,
            response_name='Move stickers response',
            array_message='Move stickers response JSON must be an array.',
        )

        move_action = action(actions, 'move_stickers')
        if not move_action:
            raise click.ClickException('Response did not include move_stickers confirmation.')

        if 'error' in move_action:
            raise click.ClickException(cls.error_message(move_action['error']))

    error_message = staticmethod(format_error)

    def group_moves(self, stickers, info_response):
        locations_by_sticker = self.sticker_locations(init_stacks(info_response))
        missing_stickers = []
        already_in_target = []
        move_groups = {}

        for sticker in stickers:
            source = self.source_location(locations_by_sticker.get(sticker, []), self.target)
            if source is None:
                missing_stickers.append(sticker)
                continue
            if source == self.target:
                already_in_target.append(sticker)
                continue
            move_groups.setdefault(source, []).append(sticker)

        if missing_stickers:
            raise click.ClickException(
                f'Sticker(s) not found in album, swap, or temp: {format_stickers(missing_stickers)}'
            )

        return move_groups, already_in_target

    @staticmethod
    def sticker_locations(stacks):
        locations_by_sticker = {}
        for stack_name in MOVABLE_STACKS:
            for sticker in sticker_numbers(stacks.get(stack_name) or []):
                locations_by_sticker.setdefault(sticker, []).append(stack_name)
        return locations_by_sticker

    @staticmethod
    def source_location(locations, target):
        for stack_name in MOVABLE_STACKS:
            if stack_name != target and stack_name in locations:
                return stack_name
        if target in locations:
            return target
        return None
