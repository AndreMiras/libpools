#!/usr/bin/env python
import argparse
import json
import os
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, DivisionByZero, InvalidOperation
from pprint import pprint
from typing import Dict

from cachetools.func import ttl_cache
from gql import Client, gql
from gql.transport.exceptions import TransportQueryError, TransportServerError
from gql.transport.requests import RequestsHTTPTransport
from graphql import DocumentNode
from web3.auto.infura import w3 as web3

MODULE_DIRECTORY = os.path.dirname((os.path.abspath(__file__)))

# default cache settings
CACHE_MAXSIZE = 1000
CACHE_TTL = 5 * 60

# pool tokens that can be staked
# staking contract -> pool token
STAKING_POOLS = {
    # DAI-ETH
    "0xa1484C3aa22a66C62b77E0AE78E15258bd0cB711": "0xA478c2975Ab1Ea89e8196811F51A7B7Ade33eB11",  # noqa: E501
    # USDC-ETH
    "0x7FBa4B8Dc5E7616e59622806932DBea72537A56b": "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",  # noqa: E501
    # USDT-ETH
    "0x6C3e4cb2E96B01F4b866965A91ed4437839A121a": "0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852",  # noqa: E501
    # WBTC-ETH
    "0xCA35e32e7926b96A9988f61d510E038108d8068e": "0xBb2b8038a1640196FbE3e38816F3e67Cba72D940",  # noqa: E501
}

GQL_PAIR_PARAMETERS = """
id
token0 {
  id
  symbol
  name
  derivedETH
}
token1 {
  id
  symbol
  name
  derivedETH
}
reserve0
reserve1
totalSupply
reserveUSD
token0Price
token1Price
"""


class UniswapRoiException(Exception):
    """Base library exception."""


class InvalidAddressException(UniswapRoiException):
    """The Ethereum address is invalid."""


class TheGraphServiceDownException(UniswapRoiException):
    """When the graph is down, e.g. giving `502 Server Error: Bad Gateway`."""


@contextmanager
def gql_exceptions():
    try:
        yield
    except (TransportServerError, TransportQueryError) as e:
        raise TheGraphServiceDownException(e.args[0])


def get_gql_client():
    transport = RequestsHTTPTransport(
        url="https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
    )
    with gql_exceptions():
        return Client(transport=transport, fetch_schema_from_transport=True)


def gql_client_execute(document: DocumentNode, *args, **kwargs) -> Dict:
    client = get_gql_client()
    with gql_exceptions():
        return client.execute(document, *args, **kwargs)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
def get_eth_price():
    """Retrieves ETH price from TheGraph.com"""
    request_string = '{bundle(id: "1") {ethPrice}}'
    query = gql(request_string)
    result = gql_client_execute(query)
    eth_price = Decimal(result["bundle"]["ethPrice"])
    return eth_price


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
def get_pair_info(contract_address):
    request_string = "query ($id: ID!) {pair(id: $id) {" + GQL_PAIR_PARAMETERS + "}}"
    query = gql(request_string)
    # note The Graph doesn't seem to like it in checksum format
    contract_address = contract_address.lower()
    variable_values = {"id": contract_address}
    result = gql_client_execute(query, variable_values=variable_values)
    return result


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
def get_liquidity_positions(address):
    request_string = (
        """
        query ($id: ID!) {
          user(id: $id) {
            liquidityPositions (where: {liquidityTokenBalance_not: "0"}) {
              liquidityTokenBalance
              pair {
              """
        + GQL_PAIR_PARAMETERS
        + """
              }
            }
          }
        }
      """
    )
    query = gql(request_string)
    # note The Graph doesn't seem to like it in checksum format
    address = address.lower()
    variable_values = {"id": address}
    result = gql_client_execute(query, variable_values=variable_values)
    user = result["user"] or {}
    result = user.get("liquidityPositions", [])
    return result


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
def get_staking_positions(address):
    """Given an address, returns all the staking positions."""
    # abi is the same for all contracts
    abi_path = os.path.join(MODULE_DIRECTORY, "abi.json")
    with open(abi_path) as f:
        abi = json.loads(f.read())
    positions = []
    for staking_contract, lp_contract in STAKING_POOLS.items():
        contract = web3.eth.contract(staking_contract, abi=abi)
        balance = contract.functions.balanceOf(address).call()
        if balance > 0:
            pair_info = get_pair_info(lp_contract)
            # this is the only missing key compared with the
            # `get_liquidity_positions()` call
            balance = web3.fromWei(balance, "ether")
            pair_info["liquidityTokenBalance"] = balance
            pair_info["pair"]["staking_contract_address"] = staking_contract
            positions.append(pair_info)
    return positions


def get_lp_transactions(address, pairs):
    """Retrieves mints/burns transactions of a given liquidity provider."""
    gql_order_by = "orderBy: timestamp, orderDirection: desc"
    gql_transaction_parameters = "transaction { id timestamp blockNumber }"
    gql_pair_parameters = "pair { id }"
    gql_mints_burns_parameters = "to sender liquidity amount0 amount1 amountUSD"
    gql_parameters = (
        gql_transaction_parameters
        + " "
        + gql_pair_parameters
        + " "
        + gql_mints_burns_parameters
    )
    request_string = (
        """
        query ($address: Bytes! $pairs: [String!]) {
          mints(
            where: { to: $address pair_in: $pairs}, """
        + gql_order_by
        + """
          ) {
        """
        + gql_parameters
        + """
          }
          burns(
            where: { sender: $address pair_in: $pairs}, """
        + gql_order_by
        + """
          ) {
        """
        + gql_parameters
        + """
          }
        }
      """
    )
    query = gql(request_string)
    # note The Graph doesn't seem to like it in checksum format
    address = address.lower()
    variable_values = {"address": address, "pairs": pairs}
    result = gql_client_execute(query, variable_values=variable_values)
    return result


def extract_pair_info(pair, balance, eth_price):
    """Builds a dictionary with pair information."""
    contract_address = None
    pair_symbol = None
    total_supply = None
    share = None
    tokens = []
    if pair:
        contract_address = pair["id"]
        # this was populated via `get_staking_positions()`
        staking_contract_address = pair.get("staking_contract_address")
        total_supply = Decimal(pair["totalSupply"])
        share = 100 * (balance / total_supply)
        reserve_usd = Decimal(pair["reserveUSD"])
        pool_token_price = reserve_usd / total_supply
        for i in range(2):
            token = pair[f"token{i}"]
            token_symbol = token["symbol"]
            token_price = Decimal(token["derivedETH"]) * eth_price
            token_balance = Decimal(pair[f"reserve{i}"]) * share * Decimal("0.01")
            token_balance_usd = token_balance * token_price
            tokens.append(
                {
                    "symbol": token_symbol,
                    "price_usd": token_price,
                    "balance": token_balance,
                    "balance_usd": token_balance_usd,
                }
            )
        pair_symbol = "-".join([token["symbol"] for token in tokens])
        balance_usd = sum([token["balance_usd"] for token in tokens])
    pair_info = {
        "contract_address": contract_address,
        "staking_contract_address": staking_contract_address,
        "owner_balance": balance,
        "symbol": pair_symbol,
        "total_supply": total_supply,
        "price_usd": pool_token_price,
        "share": share,
        "balance_usd": balance_usd,
        "tokens": tokens,
    }
    return pair_info


def merge_lp_transactions(mints, burns):
    """Merges mints/burns transactions and order by timestamp."""
    mints = list(map(lambda m: dict(m, **{"type": "mint"}), mints))
    burns = list(map(lambda m: dict(m, **{"type": "burn"}), burns))
    transactions = mints + burns
    # TODO: reverse=True
    transactions = sorted(transactions, key=lambda tx: tx["transaction"]["timestamp"])
    return transactions


def group_lp_transactions(transactions):
    """Groups transactions by pair."""
    transaction_dict = {}
    for transaction in transactions:
        pair = transaction["pair"]["id"]
        transaction_dict[pair] = transaction_dict.get(pair, []) + [transaction]
    return transaction_dict


def fix_type_lp_transactions(transactions):
    """Makes sure the type of each fields is correct."""
    transactions = deepcopy(transactions)
    for transaction in transactions:
        transaction["amount0"] = Decimal(transaction["amount0"])
        transaction["amount1"] = Decimal(transaction["amount1"])
        transaction["amountUSD"] = Decimal(transaction["amountUSD"])
        transaction["liquidity"] = Decimal(transaction["liquidity"])
        transaction_transaction = transaction["transaction"]
        block_number = transaction_transaction.pop("blockNumber")
        transaction_transaction["block_number"] = int(block_number)
        timestamp = transaction_transaction["timestamp"]
        transaction_transaction["timestamp"] = datetime.utcfromtimestamp(int(timestamp))
    return transactions


def clean_transactions(mints_burns):
    """
    Fixes ordering, grouping, typing and dict key convention of the mints burns result.
    """
    mints = mints_burns["mints"]
    burns = mints_burns["burns"]
    transactions = merge_lp_transactions(mints, burns)
    transactions = fix_type_lp_transactions(transactions)
    transaction_dict = group_lp_transactions(transactions)
    return transaction_dict


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
def portfolio(address):
    try:
        address = web3.toChecksumAddress(address)
    except ValueError:
        raise InvalidAddressException(address)
    # TODO: check if the GraphQL queries can be merged into one
    eth_price = get_eth_price()
    positions = []
    positions += get_liquidity_positions(address)
    positions += get_staking_positions(address)
    pair_addresses = [pair["pair"]["id"] for pair in positions]
    mints_burns = get_lp_transactions(address, pair_addresses)
    transaction_dict = clean_transactions(mints_burns)
    balance_usd = 0
    pairs = []
    for position in positions:
        balance = Decimal(position["liquidityTokenBalance"])
        pair = position["pair"]
        pair_info = extract_pair_info(pair, balance, eth_price)
        contract_address = pair_info["contract_address"]
        # even though the pair exists, we may not find transactions history
        pair_info["transactions"] = transaction_dict.get(contract_address, [])
        balance_usd += pair_info["balance_usd"]
        pairs.append(pair_info)
    data = {
        "address": address,
        "pairs": pairs,
        "balance_usd": balance_usd,
    }
    return data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
def get_token_daily_raw(address):
    """
    Raw pull of token daily data from TheGraph.
    Note this getting the daily for the token, not the pair.
    """
    request_string = """
        query ($token: String!) {
          tokenDayDatas(
            orderBy: date,
            orderDirection: desc,
            first: 31,
            where: {token: $token}
          ) {
            date
            priceUSD
          }
        }
      """
    query = gql(request_string)
    # note The Graph doesn't seem to like it in checksum format
    address = address.lower()
    variable_values = {"token": address}
    result = gql_client_execute(query, variable_values=variable_values)
    result = result["tokenDayDatas"]
    return result


def fix_type_token_daily(data):
    """Makes sure the type of each fields is correct."""
    data = deepcopy(data)
    for data_day in data:
        price_usd = data_day.pop("priceUSD")
        data_day["price_usd"] = Decimal(price_usd)
        data_day["date"] = datetime.utcfromtimestamp(int(data_day["date"]))
    return data


def get_token_daily(address):
    data = get_token_daily_raw(address)
    data = fix_type_token_daily(data)
    return data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
def get_pair_daily_raw(address):
    """Raw pull of pair daily data from TheGraph."""
    request_string = (
        """
        query ($pairAddress: Bytes!, $id: ID!) {
          pair(id: $id) {"""
        + GQL_PAIR_PARAMETERS
        + """}
          pairDayDatas(
            orderBy: date,
            orderDirection: desc,
            first: 31,
            where: {pairAddress: $pairAddress}
          ) {
            date
            totalSupply
            reserveUSD
          }
        }
      """
    )
    query = gql(request_string)
    # note The Graph doesn't seem to like it in checksum format
    address = address.lower()
    variable_values = {"id": address, "pairAddress": address}
    result = gql_client_execute(query, variable_values=variable_values)
    pair = result["pair"]
    date_price = result["pairDayDatas"]
    result = {"pair": pair, "date_price": date_price}
    return result


def fix_type_pair_daily(data):
    """Makes sure the type of each fields is correct."""
    data = deepcopy(data)
    for data_day in data:
        reserve_usd = Decimal(data_day.pop("reserveUSD"))
        total_supply = Decimal(data_day.pop("totalSupply"))
        try:
            data_day["price_usd"] = reserve_usd / total_supply
        except (InvalidOperation, DivisionByZero):
            data_day["price_usd"] = Decimal(0)
        data_day["date"] = datetime.utcfromtimestamp(int(data_day["date"]))
    return data


def fix_pair(pair):
    pair = deepcopy(pair)
    total_supply = Decimal(pair.pop("totalSupply"))
    pair["total_supply"] = total_supply
    reserve_usd = Decimal(pair.pop("reserveUSD"))
    pair["reserve_usd"] = reserve_usd
    pair_price_usd = reserve_usd / total_supply
    pair["price_usd"] = pair_price_usd
    pair_symbol = pair["token0"]["symbol"] + "-" + pair["token1"]["symbol"]
    pair["symbol"] = pair_symbol
    return pair


def get_pair_daily(address):
    data = get_pair_daily_raw(address)
    # makes sure we don't mutate the cached reference
    # or next cache hit we would retrieve that already mutated reference
    data = deepcopy(data)
    pair = data["pair"]
    data["pair"] = fix_pair(pair)
    date_price = data["date_price"]
    data["date_price"] = fix_type_pair_daily(date_price)
    return data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
def get_pairs_raw():
    """Raw pull of pairs data from TheGraph."""
    request_string = (
        """
    {
     pairs(first: 10, orderBy: reserveUSD, orderDirection: desc) {"""
        + GQL_PAIR_PARAMETERS
        + """
     }
    }
    """
    )
    query = gql(request_string)
    result = gql_client_execute(query)
    result = result["pairs"]
    return result


def get_pairs():
    pairs = get_pairs_raw()
    pairs = deepcopy(pairs)
    for i, pair in enumerate(pairs):
        pairs[i] = fix_pair(pair)
    return pairs


def main():
    parser = argparse.ArgumentParser(description="Liquidity provider portfolio stats.")
    parser.add_argument("address", help="Address")
    args = parser.parse_args()
    address = args.address
    data = portfolio(address)
    pprint(data)


if __name__ == "__main__":
    main()
