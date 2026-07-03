# fifa-panini

CLI for trying FIFA Panini promo codes against an endpoint.

## Install

```
pip install fifa-panini
```

## Usage

```
$ fifa-panini try-code --dry-run --cookie 'session=value; other=value' --code-base VD13-V24K-
DRY RUN POST https://paninicollection.fifa.com/api/unlock_pack.json code=VD13-V24K-0000
```

Persist settings in the classyclick config file:

```
$ fifa-panini config -e
$ fifa-panini try-code --dry-run
```

```python
>>> from fifa_panini.cli import TryCode
>>> TryCode(code_base='VD13-V24K-', cookie='session=value').next_code()
'VD13-V24K-0000'
```

## Build

Check out [CONTRIBUTING.md](CONTRIBUTING.md)
