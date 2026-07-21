import json

import click


def init_stacks(response):
    try:
        actions = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise click.ClickException(f'Response was not valid JSON: {error}') from error

    if not isinstance(actions, list):
        raise click.ClickException('Response JSON must be an array of action objects.')

    init = action(actions, 'init')
    stacks = init.get('stacks') or {}
    if not init or not isinstance(stacks, dict):
        raise click.ClickException('Response did not include init sticker stacks.')

    return stacks


def sticker_numbers(stickers):
    return [sticker for sticker in (sticker_number(item) for item in stickers) if sticker is not None]


def sticker_number(item):
    if isinstance(item, (list, tuple)):
        if not item:
            return None
        return item[0]
    return item


def format_stickers(stickers):
    if not stickers:
        return '(none)'
    return ', '.join(str(sticker) for sticker in stickers)


def action(actions, name):
    for action_item in actions:
        if isinstance(action_item, dict) and action_item.get('action') == name:
            return action_item
    return {}
