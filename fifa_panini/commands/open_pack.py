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
    PaniniResponse,
    validate_cookie_header,
)

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

    @property
    def pack_endpoint(self):
        return self.panini_client.endpoint(OPEN_PACK_PATH)

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.pack_endpoint} json={{}}')
            return

        response = self.open_pack()
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def open_pack(self):
        return self.panini_client.post_json(OPEN_PACK_PATH, request_name='open pack')

    def print_response(self, response):
        try:
            actions = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Response was not valid JSON: {error}') from error

        if not isinstance(actions, list):
            raise click.ClickException('Response JSON must be an array of action objects.')

        error_message = self.error_message(actions)
        if error_message:
            raise click.ClickException(error_message)

        wait_message = self.wait_message(actions)
        if wait_message:
            raise click.ClickException(wait_message)

        open_pack = self.action(actions, 'open_pack')
        if not open_pack:
            raise click.ClickException('Response did not include opened pack information.')

        stickers = open_pack.get('stickers') or []
        click.echo(f'Opened stickers: {", ".join(str(sticker) for sticker in stickers)}')

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

    def wait_message(self, actions):
        for action in actions:
            if not isinstance(action, dict) or 'wait' not in action:
                continue

            wait = action['wait']
            if not isinstance(wait, dict):
                return str(wait)

            reason = wait.get('reason') or str(wait)
            countdown_seconds = wait.get('countdown_seconds')
            if countdown_seconds is None:
                return reason

            available_at = self.current_time() + dt.timedelta(seconds=countdown_seconds)
            return f'{reason} {available_at.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()}'
        return None

    @staticmethod
    def current_time():
        return dt.datetime.now().astimezone()
