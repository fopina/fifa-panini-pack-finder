import json

import click


def parse_action_list(response, response_name='Response', array_message=None):
    try:
        actions = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise click.ClickException(f'{response_name} was not valid JSON: {error}') from error

    if not isinstance(actions, list):
        message = array_message or f'{response_name} JSON must be an array of action objects.'
        raise click.ClickException(message)

    return actions


def action(actions, name):
    for action_item in actions:
        if isinstance(action_item, dict) and action_item.get('action') == name:
            return action_item
    return {}


def action_with_status(actions, name):
    first_action = {}
    for action_item in actions:
        if not isinstance(action_item, dict) or action_item.get('action') != name:
            continue
        if not first_action:
            first_action = action_item
        if 'error' in action_item or 'wait' in action_item:
            return action_item
    return first_action


def format_error(error):
    if isinstance(error, dict):
        return error.get('message') or str(error)
    return str(error)


def error_message(action_item):
    if not isinstance(action_item, dict) or 'error' not in action_item:
        return None

    return format_error(action_item['error'])
