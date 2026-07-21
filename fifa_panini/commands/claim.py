import datetime as dt

import classyclick
import click

from ..utils.actions import action, action_with_status, error_message, parse_action_list
from ..utils.panini import (
    DEFAULT_REQUEST_TIMEOUT,
    PaniniClient,
    validate_cookie_header,
)
from .panini import PANINI_API_ENDPOINT_META_KEY, PANINI_COOKIE_META_KEY, Panini

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

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.panini_client.endpoint(CLAIM_PACKS_PATH)} json={{}}')
            return

        response = self.panini_client.post_json(CLAIM_PACKS_PATH, request_name='claim packs')
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def print_response(self, response):
        actions = parse_action_list(response)

        receive_daily_packs = action_with_status(actions, 'receive_daily_packs')
        if not receive_daily_packs:
            raise click.ClickException('Response did not include receive daily pack information.')

        next_packs_message = self.next_packs_message(actions)

        error_message = self.error_message(receive_daily_packs)
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

        available_at = dt.datetime.now().astimezone() + dt.timedelta(seconds=new_packs_in_sec)
        return f'New packs available at: {available_at.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()}'

    action = staticmethod(action)
    error_message = staticmethod(error_message)
