import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

import classyclick
import click

from .open_pack import OPEN_PACK_BODY
from .panini import PANINI_API_ENDPOINT_META_KEY, PANINI_COOKIE_META_KEY, Panini, api_url, validate_cookie_header


@dataclass(frozen=True)
class InfoResponse:
    text: str


class Info(Panini.Command):
    """Print FIFA Panini collection info."""

    __config__ = classyclick.Command.Config(name='info')

    cookie: str = classyclick.ContextMeta(PANINI_COOKIE_META_KEY)
    api_endpoint: str = classyclick.ContextMeta(PANINI_API_ENDPOINT_META_KEY)
    dry_run: bool = classyclick.Option(default=False, help='Print the request that would be attempted.')
    raw: bool = classyclick.Option('--raw', default=False, help='Print the complete JSON response.')
    request_timeout: float = classyclick.Option(
        '--timeout',
        default=30.0,
        show_default=True,
        help='HTTP request timeout in seconds.',
    )

    @property
    def info_endpoint(self):
        return api_url(self.api_endpoint, 'init.json')

    def __call__(self):
        self.validate_settings()

        if self.dry_run:
            click.echo(f'DRY RUN POST {self.info_endpoint} json={{}}')
            return

        response = self.get_info()
        self.print_response(response)

    def validate_settings(self):
        if not self.cookie:
            raise click.ClickException(
                'Missing required setting(s): cookie. Pass them as options or save them in the config file.'
            )
        validate_cookie_header(self.cookie)

    def get_info(self):
        validate_cookie_header(self.cookie)
        request = Request(
            self.info_endpoint,
            data=OPEN_PACK_BODY,
            headers={
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:152.0) Gecko/20100101 Firefox/152.0',
                'Accept': '*/*',
                'Accept-Language': 'en-GB,en;q=0.9',
                'Referer': 'https://paninicollection.fifa.com/game/flash',
                'X-User-Agent': 'Unity/1.3.0 (MacOS 10.15) Unity/6000.0.65f1 webgl_hires',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://paninicollection.fifa.com',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Gpc': '1',
                'Priority': 'u=4',
            },
            method='POST',
        )

        try:
            with urlopen(request, timeout=self.request_timeout) as response:
                return InfoResponse(text=response.read().decode('utf-8', errors='replace'))
        except OSError as error:
            raise click.ClickException(f'Request failed for info: {error}') from error

    def print_response(self, response):
        if self.raw:
            click.echo(response.text, nl=not response.text.endswith('\n'))
            return

        try:
            actions = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise click.ClickException(f'Response was not valid JSON: {error}') from error

        if not isinstance(actions, list):
            raise click.ClickException('Response JSON must be an array of action objects.')

        self.print_summary(actions)

    def print_summary(self, actions):
        received_packs = self.action(actions, 'received_packs')
        user_info = self.action(actions, 'own_user_info').get('user_info', {})
        init = self.action(actions, 'init')

        if received_packs:
            click.echo(f'Available packs: {received_packs.get("total_packs", received_packs.get("amount", 0))}')

        if user_info:
            label = user_info.get('label') or user_info.get('uid') or 'unknown'
            country = user_info.get('country')
            click.echo(f'User: {label}' + (f' ({country})' if country else ''))
            public_profile = user_info.get('public_profile') or {}
            if public_profile.get('url'):
                click.echo(f'Public profile: {public_profile["url"]}')
            click.echo(f'Collector points: {user_info.get("collector_points", 0)}')
            click.echo(
                'Album: '
                f'{user_info.get("album_collected_stickers", 0)}/{user_info.get("album_total_stickers", 0)} '
                f'({user_info.get("album_completion_perc", 0)}%)'
            )
            click.echo(
                'Golden album: '
                f'{user_info.get("golden_album_collected_stickers", 0)}/'
                f'{user_info.get("golden_album_total_stickers", 0)} '
                f'({user_info.get("golden_album_completion_perc", 0)}%)'
            )

        if init:
            click.echo(f'Album completed: {self.yes_no(init.get("album_completed"))}')
            stacks = init.get('stacks') or {}
            for name in sorted(stacks):
                click.echo(f'{name} stickers: {len(stacks[name])}')
            click.echo(f'Completed groups: {len(init.get("completed_groups") or [])}')
            click.echo(f'Received swaps: {len(init.get("received_swaps") or [])}')

    @staticmethod
    def action(actions, name):
        for action in actions:
            if isinstance(action, dict) and action.get('action') == name:
                return action
        return {}

    @staticmethod
    def yes_no(value):
        return 'yes' if value else 'no'
