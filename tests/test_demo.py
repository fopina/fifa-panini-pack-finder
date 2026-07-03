from click.testing import CliRunner

from fifa_panini.cli import CLI, TryCode


def test_try_code_builds_dry_run_url():
    command = TryCode(code='ABC 123', endpoint='https://example.test/redeem', code_parameter='promo')

    assert command.url == 'https://example.test/redeem?promo=ABC%20123'


def test_cli_exposes_try_code_command():
    result = CliRunner().invoke(
        CLI.click,
        ['try-code', '--endpoint', 'https://example.test/redeem', 'ABC123'],
    )

    assert result.exit_code == 0
    assert result.output == 'DRY RUN https://example.test/redeem?code=ABC123\n'
