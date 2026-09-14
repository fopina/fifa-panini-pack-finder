import json

import classyclick
import click

from ...utils.actions import action, format_error, parse_action_list
from ...utils.panini import DEFAULT_REQUEST_TIMEOUT, PaniniClient, PaniniResponse, validate_cookie_header
from ...utils.stickers import format_stickers, init_stacks, parse_sticker_list, sticker_numbers
from . import PANINI_API_ENDPOINT_META_KEY, PANINI_COOKIE_META_KEY, Panini
from .info import INFO_PATH

SwapResponse = PaniniResponse
SWAP_REQUESTS_PATH = 'swap_requests.json'
DELETE_SWAP_REQUEST_PATH = 'delete_swap_request.json'
UPDATE_SWAP_REQUEST_PATH = 'update_swap_request.json'
EXECUTE_RECEIVED_SWAP_PATH = 'execute_received_swap.json'


class Swap(Panini.Command):
    """Print stickers currently in the FIFA Panini swap stack."""

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(help='Print the request that would be attempted.')
    collect: bool = classyclick.Option('--collect', help='Collect all received swaps.')
    delete: str = classyclick.Option(
        '--delete',
        help='Swap request ID to delete.',
    )
    create: str = classyclick.Option(
        '--create',
        help='Sticker numbers to request, comma separated.',
    )
    create_allow_duplicates: bool = classyclick.Option(
        '--create-allow-duplicates',
        help='Allow duplicate stickers in the created swap request demand.',
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
        self.validate_operation()

        if self.delete:
            payload = {'id': self.delete}
            if self.dry_run:
                json_payload = PaniniClient.form_data(payload)['json']
                click.echo(f'DRY RUN POST {self.panini_client.endpoint(DELETE_SWAP_REQUEST_PATH)} json={json_payload}')
                return

            response = self.panini_client.post_json(
                DELETE_SWAP_REQUEST_PATH,
                payload=payload,
                request_name='delete swap request',
            )
            self.validate_delete_response(response)
            click.echo(f'Deleted swap request: {self.delete}')
            return

        if self.create:
            demand_stickers = parse_sticker_list(self.create, '--create')
            payload = {
                'id': None,
                'only_team': True,
                'offer': {
                    'stickers': [],
                    'groups': [],
                    'full_stack': True,
                },
                'demand': {
                    'stickers': demand_stickers,
                    'groups': [],
                    'allow_duplicates': self.create_allow_duplicates,
                },
            }
            if self.dry_run:
                json_payload = PaniniClient.form_data(payload)['json']
                click.echo(f'DRY RUN POST {self.panini_client.endpoint(UPDATE_SWAP_REQUEST_PATH)} json={json_payload}')
                return

            response = self.panini_client.post_json(
                UPDATE_SWAP_REQUEST_PATH,
                payload=payload,
                request_name='create swap request',
            )
            self.validate_create_response(response)
            click.echo(f'Created swap request for stickers: {format_stickers(demand_stickers)}')
            return

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.panini_client.endpoint(INFO_PATH)} json={{}}')
            click.echo(f'DRY RUN POST {self.panini_client.endpoint(SWAP_REQUESTS_PATH)} json={{}}')
            if self.collect:
                click.echo(
                    f'DRY RUN POST {self.panini_client.endpoint(EXECUTE_RECEIVED_SWAP_PATH)} '
                    'json={"id":"<received swap ID>"} (for each received swap from init)'
                )
            return

        swap_stack_response = self.panini_client.post_json(INFO_PATH, request_name='swap')
        swap_requests_response = self.panini_client.post_json(SWAP_REQUESTS_PATH, request_name='swap requests')
        self.print_response(swap_stack_response, swap_requests_response)
        if self.collect:
            self.collect_swaps(swap_stack_response)

    def collect_swaps(self, response):
        swaps = self.received_swaps(response)
        if not swaps:
            click.echo('No swaps to collect.')
            return

        for swap in swaps:
            result = self.panini_client.post_json(
                EXECUTE_RECEIVED_SWAP_PATH,
                payload={'id': swap['id']},
                request_name=f'collect swap {swap["id"]}',
            )
            actions = parse_action_list(result, response_name='Collect swap response')
            for action_item in actions:
                if isinstance(action_item, dict) and 'error' in action_item:
                    raise click.ClickException(self.error_message(action_item['error']))
            click.echo(f'Collected swap: {swap["id"]}')

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def validate_operation(self):
        if self.collect and (self.delete or self.create):
            raise click.ClickException('--collect cannot be used with --delete or --create.')
        if self.delete and self.create:
            raise click.ClickException('--delete and --create cannot be used together.')
        if self.create_allow_duplicates and not self.create:
            raise click.ClickException('--create-allow-duplicates can only be used with --create.')

    @classmethod
    def validate_delete_response(cls, response):
        actions = parse_action_list(
            response,
            response_name='Delete swap request response',
            array_message='Delete swap request response JSON must be an array.',
        )

        delete_action = cls.action(actions, 'delete_swap_request')
        if not delete_action:
            raise click.ClickException('Response did not include delete_swap_request confirmation.')

        if 'error' in delete_action:
            raise click.ClickException(cls.error_message(delete_action['error']))

    @classmethod
    def validate_create_response(cls, response):
        actions = parse_action_list(
            response,
            response_name='Create swap request response',
            array_message='Create swap request response JSON must be an array.',
        )

        update_action = cls.action(actions, 'update_swap_request')
        if not update_action:
            raise click.ClickException('Response did not include update_swap_request confirmation.')

        if 'error' in update_action:
            raise click.ClickException(cls.error_message(update_action['error']))

    def print_response(self, swap_stack_response, swap_requests_response):
        stacks = init_stacks(swap_stack_response)
        swap_stickers = sticker_numbers(stacks.get('swap') or [])
        click.echo(f'Swap stickers: {format_stickers(swap_stickers)}')
        self.print_swap_requests(swap_requests_response)
        self.print_executed_swaps(swap_stack_response)

    @classmethod
    def received_swaps(cls, response):
        actions = parse_action_list(response)
        swaps = cls.action(actions, 'init').get('received_swaps') or []
        if not isinstance(swaps, list):
            raise click.ClickException('Init action must include a received_swaps array.')
        for swap in swaps:
            if not isinstance(swap, dict):
                raise click.ClickException('Executed swap must be an object.')
            if not swap.get('id'):
                raise click.ClickException('Executed swap must include an id.')
        return swaps

    @classmethod
    def print_executed_swaps(cls, response):
        swaps = cls.received_swaps(response)
        if not swaps:
            click.echo('Swaps executed: (none)')
            return

        click.echo('Swaps executed:')
        for swap in swaps:
            if not isinstance(swap, dict):
                raise click.ClickException('Executed swap must be an object.')
            received = format_stickers([f'+{sticker}' for sticker in sticker_numbers(swap['received'])])
            given = format_stickers([f'-{sticker}' for sticker in sticker_numbers(swap['given'])])
            click.echo(f'- id: {swap["id"]}; {received}; {given}')

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

        for action_item in data:
            if isinstance(action_item, dict) and action_item.get('action') == 'swap_requests':
                requests = action_item.get('swap_requests') or []
                if not isinstance(requests, list):
                    raise click.ClickException('Swap requests action must include a swap_requests array.')
                return requests

        return []

    action = staticmethod(action)
    error_message = staticmethod(format_error)

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
            parts.append(f'groups: {", ".join(str(group) for group in group["groups"])}')

        return ', '.join(parts) if parts else '(empty)'
