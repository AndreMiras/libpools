# Pools

[![Tests](https://github.com/AndreMiras/libpools/workflows/Tests/badge.svg?branch=develop)](https://github.com/AndreMiras/libpools/actions?query=workflow%3ATests)
[![PyPI version](https://badge.fury.io/py/pools.svg)](https://badge.fury.io/py/pools)

Python library for pools liquidity providers.

## Install
```sh
pip install pools
```

## Usage
The `pools` library relies on `web3` which requires the `WEB3_INFURA_PROJECT_ID` environment variable to be set.
```sh
export WEB3_INFURA_PROJECT_ID=00000000000000000000000000000000
```
Then use the library to fetch portfolio data.
```python
>>> from pools import uniswap
>>> address = "0x000000000000000000000000000000000000dEaD"
>>> portfolio_data = uniswap.portfolio(address)
>>> portfolio_data.keys()
dict_keys(['address', 'pairs', 'balance_usd'])
>>> portfolio_data["balance_usd"]
Decimal('1234.56')
```
A Command line interface is also available.
```text
pools --help
Consider installing rusty-rlp to improve pyrlp performance with a rust based backend
usage: pools [-h] address

Liquidity provider portfolio stats.

positional arguments:
  address     Address

optional arguments:
  -h, --help  show this help message and exit
```
