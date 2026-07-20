# fifa-panini

CLI for trying FIFA Panini promo codes against an endpoint.

## Install

```
pip install fifa-panini
```

## Usage

```
$ fifa-panini try-code --dry-run --cookie 'session=value; other=value' --code VD13-V24K-ABCD
DRY RUN POST https://paninicollection.fifa.com/api/unlock_pack.json code=VD13-V24K-ABCD
```

Brute-force the final block from a known-used code base:

```
$ fifa-panini bf-code --dry-run --cookie 'session=value; other=value' --code-base VD13-V24K-0000
DRY RUN POST https://paninicollection.fifa.com/api/unlock_pack.json code=VD13-V24K-AAAA
```

Fetch the daily promo code:

```
$ fifa-panini daily-code --cookie 'session=value; other=value'
```

Persist settings in the classyclick config file:

```
$ fifa-panini config -e
$ fifa-panini bf-code --dry-run
```

```python
>>> from fifa_panini.commands.bf_code import BfCode
>>> BfCode(code_base='VD13-V24K-0000', cookie='session=value').next_code()
'VD13-V24K-AAAA'
```

## Build

Check out [CONTRIBUTING.md](CONTRIBUTING.md)
