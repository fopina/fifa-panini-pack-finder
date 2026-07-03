from urllib.parse import quote

import classyclick
import click

from . import __version__


class CLI(classyclick.Group):
    """Tools for testing FIFA Panini promo codes."""

    __config__ = classyclick.Group.Config(
        name='fifa-panini',
        decorators=[click.version_option(version=__version__)],
    )


class TryCode(CLI.Command):
    """Prepare a promo-code attempt against an endpoint."""

    code: str = classyclick.Argument(metavar='CODE')
    endpoint: str = classyclick.Option('-e', required=True, help='Endpoint URL to test against.')
    code_parameter: str = classyclick.Option(
        '--code-param',
        default='code',
        show_default=True,
        help='Query parameter name used for the promo code.',
    )
    dry_run: bool = classyclick.Option(default=True, help='Print the request that would be attempted.')

    def __call__(self):
        url = self.url
        if self.dry_run:
            click.echo(f'DRY RUN {url}')
            return

        raise click.ClickException('Real endpoint attempts are not implemented yet.')

    @property
    def url(self):
        separator = '&' if '?' in self.endpoint else '?'
        return f'{self.endpoint}{separator}{quote(self.code_parameter)}={quote(self.code)}'
