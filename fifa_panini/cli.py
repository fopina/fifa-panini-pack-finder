from pathlib import Path

import classyclick
import classyclick.helpers
import click

from . import __version__

CONFIG_EXAMPLE_PATH = Path(__file__).with_name('config.example.toml')


class CLI(classyclick.helpers.ConfigFileMixin, classyclick.Group):
    """Tools for testing FIFA Panini promo codes."""

    __config__ = classyclick.Group.Config(
        name='fifa-panini',
        decorators=[click.version_option(version=__version__)],
    )
    CONFIG_DEFAULT_NAME = 'fifa-panini'
    CONFIG_EXAMPLE_PATH = CONFIG_EXAMPLE_PATH

    def __call__(self):
        self.load_config()


classyclick.helpers.discover_commands(f'{__package__}.commands')
