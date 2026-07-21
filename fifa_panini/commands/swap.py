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
from .sticker_stacks import format_stickers, init_stacks, parse_sticker_list, sticker_numbers

SwapResponse = PaniniResponse
SWAP_REQUESTS_PATH = 'swap_requests.json'
DELETE_SWAP_REQUEST_PATH = 'delete_swap_request.json'
UPDATE_SWAP_REQUEST_PATH = 'update_swap_request.json'


class Swap(Panini.Command):
    """Print stickers currently in the FIFA Panini swap stack."""

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(help='Print the request that would be attempted.')
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

    @property
    def swap_endpoint(self):
        return self.panini_client.endpoint(INFO_PATH)

    @property
    def swap_requests_endpoint(self):
        return self.panini_client.endpoint(SWAP_REQUESTS_PATH)

    @property
    def delete_swap_request_endpoint(self):
        return self.panini_client.endpoint(DELETE_SWAP_REQUEST_PATH)

    @property
    def update_swap_request_endpoint(self):
        return self.panini_client.endpoint(UPDATE_SWAP_REQUEST_PATH)

    def __call__(self):
        self.validate_settings()
        self.validate_operation()

        if self.delete:
            payload = self.delete_payload(self.delete)
            if self.dry_run:
                json_payload = PaniniClient.form_data(payload)['json']
                click.echo(f'DRY RUN POST {self.delete_swap_request_endpoint} json={json_payload}')
                return

            response = self.delete_swap_request(self.delete)
            self.validate_delete_response(response)
            click.echo(f'Deleted swap request: {self.delete}')
            return

        if self.create:
            demand_stickers = parse_sticker_list(self.create, '--create')
            payload = self.create_payload(demand_stickers, allow_duplicates=self.create_allow_duplicates)
            if self.dry_run:
                json_payload = PaniniClient.form_data(payload)['json']
                click.echo(f'DRY RUN POST {self.update_swap_request_endpoint} json={json_payload}')
                return

            response = self.create_swap_request(demand_stickers)
            self.validate_create_response(response)
            click.echo(f'Created swap request for stickers: {format_stickers(demand_stickers)}')
            return

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

    def validate_operation(self):
        if self.delete and self.create:
            raise click.ClickException('--delete and --create cannot be used together.')
        if self.create_allow_duplicates and not self.create:
            raise click.ClickException('--create-allow-duplicates can only be used with --create.')

    def get_swap_stack(self):
        return self.panini_client.post_json(INFO_PATH, request_name='swap')

    def get_swap_requests(self):
        return self.panini_client.post_json(SWAP_REQUESTS_PATH, request_name='swap requests')

    def delete_swap_request(self, request_id):
        return self.panini_client.post_json(
            DELETE_SWAP_REQUEST_PATH,
            payload=self.delete_payload(request_id),
            request_name='delete swap request',
        )

    @staticmethod
    def delete_payload(request_id):
        return {'id': request_id}

    def create_swap_request(self, demand_stickers):
        return self.panini_client.post_json(
            UPDATE_SWAP_REQUEST_PATH,
            payload=self.create_payload(demand_stickers, allow_duplicates=self.create_allow_duplicates),
            request_name='create swap request',
        )

    @staticmethod
    def create_payload(demand_stickers, allow_duplicates=False):
        return {
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
                'allow_duplicates': allow_duplicates,
            },
        }

    @classmethod
    def validate_delete_response(cls, response):
        try:
            actions = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Delete swap request response was not valid JSON: {error}') from error

        if not isinstance(actions, list):
            raise click.ClickException('Delete swap request response JSON must be an array.')

        delete_action = cls.action(actions, 'delete_swap_request')
        if not delete_action:
            raise click.ClickException('Response did not include delete_swap_request confirmation.')

        if 'error' in delete_action:
            raise click.ClickException(cls.error_message(delete_action['error']))

    @classmethod
    def validate_create_response(cls, response):
        try:
            actions = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Create swap request response was not valid JSON: {error}') from error

        if not isinstance(actions, list):
            raise click.ClickException('Create swap request response JSON must be an array.')

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

    @staticmethod
    def action(actions, name):
        for action in actions:
            if isinstance(action, dict) and action.get('action') == name:
                return action
        return {}

    @staticmethod
    def error_message(error):
        if isinstance(error, dict):
            return error.get('message') or str(error)
        return str(error)

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
