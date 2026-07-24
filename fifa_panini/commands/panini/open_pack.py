import datetime as dt

import classyclick
import click

from ...utils.actions import action, action_with_status, error_message, parse_action_list
from ...utils.panini import (
    DEFAULT_REQUEST_TIMEOUT,
    PaniniClient,
    PaniniResponse,
    validate_cookie_header,
)
from . import PANINI_API_ENDPOINT_META_KEY, PANINI_COOKIE_META_KEY, Panini

OPEN_PACK_PATH = 'open_pack.json'


PackResponse = PaniniResponse


class OpenPack(Panini.Command):
    """Open a FIFA Panini pack."""

    __config__ = classyclick.Command.Config(name='open')

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
            click.echo(f'DRY RUN POST {self.panini_client.endpoint(OPEN_PACK_PATH)} json={{}}')
            return

        response = self.panini_client.post_json(OPEN_PACK_PATH, request_name='open pack')
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def print_response(self, response):
        actions = parse_action_list(response)

        open_pack = action_with_status(actions, 'open_pack')
        if not open_pack:
            raise click.ClickException('Response did not include opened pack information.')

        error_message = self.error_message(open_pack)
        if error_message:
            raise click.ClickException(error_message)

        wait_message = self.wait_message(open_pack)
        if wait_message:
            raise click.ClickException(wait_message)

        stickers = open_pack.get('stickers') or []
        click.echo(f'Opened stickers: {", ".join(str(sticker) for sticker in stickers)}')

    action = staticmethod(action)
    error_message = staticmethod(error_message)

    def wait_message(self, action_item):
        wait = action_item.get('wait')
        if wait is None:
            return None
        if not isinstance(wait, dict):
            return str(wait)

        reason = wait.get('reason') or str(wait)
        countdown_seconds = wait.get('countdown_seconds')
        if countdown_seconds is None:
            return reason

        available_at = dt.datetime.now().astimezone() + dt.timedelta(seconds=countdown_seconds)
        return f'{reason} {available_at.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()}'
