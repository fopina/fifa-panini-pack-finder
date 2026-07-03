# fifa-panini

CLI for trying FIFA Panini promo codes against an endpoint.

## Install

```
pip install fifa-panini
```

## Usage

```
$ fifa-panini try-code --endpoint https://example.test/redeem ABC123
DRY RUN https://example.test/redeem?code=ABC123
```

```python
>>> from fifa_panini.cli import TryCode
>>> TryCode(code='ABC123', endpoint='https://example.test/redeem').url
'https://example.test/redeem?code=ABC123'
```

## Build

Check out [CONTRIBUTING.md](CONTRIBUTING.md)
