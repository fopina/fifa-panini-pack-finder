import datetime as dt
import json

import classyclick
import click

from .panini import (
    DEFAULT_REQUEST_TIMEOUT,
    PANINI_API_ENDPOINT_META_KEY,
    PANINI_COOKIE_META_KEY,
    Panini,
    PaniniClient,
    validate_cookie_header,
)

CLAIM_PACKS_PATH = 'receive_daily_packs.json'


class Claim(Panini.Command):
    """Claim the current FIFA Panini daily packs."""

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(help='Print the request that would be attempted.')
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
    def claim_endpoint(self):
        return self.panini_client.endpoint(CLAIM_PACKS_PATH)

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.claim_endpoint} json={{}}')
            return

        response = self.claim_packs()
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def claim_packs(self):
        return self.panini_client.post_json(CLAIM_PACKS_PATH, request_name='claim packs')

    def print_response(self, response):
        try:
            actions = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Response was not valid JSON: {error}') from error

        if not isinstance(actions, list):
            raise click.ClickException('Response JSON must be an array of action objects.')

        next_packs_message = self.next_packs_message(actions)
        error_message = self.error_message(actions)
        if error_message:
            message = error_message
            if next_packs_message:
                message = f'{message}. {next_packs_message}'
            raise click.ClickException(message)

        received_packs = self.action(actions, 'received_packs')
        if not received_packs:
            raise click.ClickException('Response did not include received pack information.')

        click.echo(f'Claimed packs: {received_packs.get("amount", 0)}')
        click.echo(f'Total packs: {received_packs.get("total_packs", 0)}')
        if next_packs_message:
            click.echo(next_packs_message)

    def next_packs_message(self, actions):
        daily_packs_status = self.action(actions, 'daily_packs_status')
        new_packs_in_sec = daily_packs_status.get('new_packs_in_sec')
        if new_packs_in_sec is None:
            return None

        available_at = self.current_time() + dt.timedelta(seconds=new_packs_in_sec)
        return f'New packs available at: {available_at.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()}'

    @staticmethod
    def current_time():
        return dt.datetime.now().astimezone()

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
