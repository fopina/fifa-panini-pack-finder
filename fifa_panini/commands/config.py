from classyclick.helpers.config import ConfigBaseCommand

from ..cli import CLI


class Config(ConfigBaseCommand, CLI.Command):
    """Show or edit the current CLI configuration."""

    MASKED_FIELDS = ('cookie',)
