# fifa-panini

CLI for trying FIFA Panini promo codes against the API.

## Install

```
pip install fifa-panini
```

## Usage

```
$ fifa-panini panini --cookie 'session=value; other=value' try --dry-run --code VD13-V24K-ABCD
DRY RUN POST https://paninicollection.fifa.com/api/unlock_pack.json code=VD13-V24K-ABCD
```

Brute-force the final block from a known-used code base:

```
$ fifa-panini panini --cookie 'session=value; other=value' bf --dry-run --code-base VD13-V24K-0000
DRY RUN POST https://paninicollection.fifa.com/api/unlock_pack.json code=VD13-V24K-AAAA
```

Claim the current daily Panini packs:

```
$ fifa-panini panini --cookie 'session=value; other=value' claim
```

Fetch the daily promo code from FIFA Play:

```
$ fifa-panini daily-play --cookie 'session=value; other=value'
```

Persist settings in the classyclick config file:

```
$ fifa-panini config -e
$ fifa-panini panini bf --dry-run
```

```python
>>> from fifa_panini.commands.bf_code import BfCode
>>> BfCode(code_base='VD13-V24K-0000').next_code()
'VD13-V24K-AAAA'
```

## Build

Check out [CONTRIBUTING.md](CONTRIBUTING.md)
