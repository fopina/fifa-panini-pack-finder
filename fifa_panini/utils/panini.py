import json
from dataclasses import dataclass, field
from urllib.parse import urljoin

import click
import requests

API_ENDPOINT = 'https://paninicollection.fifa.com/api/'
DEFAULT_REQUEST_TIMEOUT = 30.0
PANINI_COOKIE_META_KEY = 'panini_cookie'
PANINI_API_ENDPOINT_META_KEY = 'panini_api_endpoint'
PANINI_REQUEST_HEADERS = {
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
}


@dataclass(frozen=True)
class PaniniResponse:
    text: str
    headers: dict[str, str] = field(default_factory=dict)


def validate_cookie_header(cookie):
    try:
        cookie.encode('latin-1')
    except UnicodeEncodeError as error:
        character = error.object[error.start : error.end].encode('unicode_escape').decode('ascii')
        raise click.ClickException(
            f'Cookie contains {character}, which cannot be sent in an HTTP header. '
            'Re-copy the complete Cookie header from browser developer tools; copied previews are often truncated.'
        ) from error


def api_url(api_endpoint, path):
    return urljoin(f'{api_endpoint.rstrip("/")}/', path)


class PaniniClient:
    def __init__(self, cookie, api_endpoint=API_ENDPOINT, request_timeout=DEFAULT_REQUEST_TIMEOUT):
        self.cookie = cookie
        self.api_endpoint = api_endpoint
        self.request_timeout = request_timeout
        self.session = requests.Session()

    def endpoint(self, path):
        return api_url(self.api_endpoint, path)

    def post_json(self, path, payload=None, request_name=None):
        validate_cookie_header(self.cookie)
        try:
            response = self.session.post(
                self.endpoint(path),
                data=self.form_data(payload or {}),
                headers=self.headers(),
                timeout=self.request_timeout,
            )
        except requests.RequestException as error:
            name = request_name or path
            raise click.ClickException(f'Request failed for {name}: {error}') from error

        return PaniniResponse(
            text=response.text,
            headers=dict(response.headers.items()),
        )

    def headers(self):
        return {
            **PANINI_REQUEST_HEADERS,
            'Cookie': self.cookie,
        }

    @staticmethod
    def form_data(payload):
        return {'json': json.dumps(payload, separators=(',', ':')), 'locale': 'en'}
