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
from .sticker_stacks import format_stickers, init_stacks, sticker_numbers

SwapResponse = PaniniResponse
SWAP_REQUESTS_PATH = 'swap_requests.json'


class Swap(Panini.Command):
    """Print stickers currently in the FIFA Panini swap stack."""

    __config__ = classyclick.Command.Config(name='swap')

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(default=False, help='Print the request that would be attempted.')
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
    def swap_endpoint(self):
        return self.panini_client.endpoint(INFO_PATH)

    @property
    def swap_requests_endpoint(self):
        return self.panini_client.endpoint(SWAP_REQUESTS_PATH)

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.swap_endpoint} json={{}}')
            click.echo(f'DRY RUN POST {self.swap_requests_endpoint} json={{}}')
            return

        swap_stack_response = self.get_swap_stack()
        swap_requests_response = self.get_swap_requests()
        self.print_response(swap_stack_response, swap_requests_response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def get_swap_stack(self):
        return self.panini_client.post_json(INFO_PATH, request_name='swap')

    def get_swap_requests(self):
        return self.panini_client.post_json(SWAP_REQUESTS_PATH, request_name='swap requests')

    def print_response(self, swap_stack_response, swap_requests_response):
        stacks = init_stacks(swap_stack_response)
        swap_stickers = sticker_numbers(stacks.get('swap') or [])
        click.echo(f'Swap stickers: {format_stickers(swap_stickers)}')
        self.print_swap_requests(swap_requests_response)

    @classmethod
    def print_swap_requests(cls, response):
        requests = cls.swap_requests(response)
        if not requests:
            click.echo('Swap requests: (none)')
            return

        click.echo('Swap requests:')
        for request in requests:
            click.echo(f'- {cls.format_swap_request(request)}')

    @staticmethod
    def swap_requests(response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Swap requests response was not valid JSON: {error}') from error

        if not isinstance(data, list):
            raise click.ClickException('Swap requests response JSON must be an array.')

        for action in data:
            if isinstance(action, dict) and action.get('action') == 'swap_requests':
                requests = action.get('swap_requests') or []
                if not isinstance(requests, list):
                    raise click.ClickException('Swap requests action must include a swap_requests array.')
                return requests

        return []

    @classmethod
    def format_swap_request(cls, request):
        if not isinstance(request, dict):
            raise click.ClickException('Swap request must be an object.')

        parts = [
            f'id: {request["id"]}',
            f'offer: {cls.format_sticker_group(request["offer"])}',
            f'demand: {cls.format_sticker_group(request["demand"])}',
        ]
        if request['only_team']:
            parts.append('only team')

        return '; '.join(parts)

    @classmethod
    def format_sticker_group(cls, group):
        parts = []
        if group['stickers']:
            parts.append(f'stickers: {format_stickers(sticker_numbers(group["stickers"]))}')
        if group.get('full_stack'):
            parts.append('full stack')
        if group['groups']:
            parts.append(f'groups: {cls.format_groups(group["groups"])}')

        return ', '.join(parts) if parts else '(empty)'

    @staticmethod
    def format_groups(groups):
        return ', '.join(str(group) for group in groups)

    get_swap = get_swap_stack
