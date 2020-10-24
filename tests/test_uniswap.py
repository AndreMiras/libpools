from datetime import datetime
from decimal import Decimal
from io import BytesIO
from unittest import mock

import pytest
from gql import gql
from gql.transport.exceptions import TransportServerError
from requests.models import Response

from pools.test_utils import (
    GQL_ETH_PRICE_RESPONSE,
    GQL_LIQUIDITY_POSITIONS_RESPONSE,
    GQL_PAIR_INFO_RESPONSE,
    GQL_TOKEN_DAY_DATA_RESPONSE,
    patch_client_execute,
    patch_session_fetch_schema,
    patch_web3_contract,
)


def patch_session_request(content, status_code=200):
    response = Response()
    response.status_code = status_code
    response.raw = BytesIO(content.encode())
    m_request = mock.Mock(return_value=response)
    return mock.patch("requests.Session.request", m_request)


def patch_gql_transport_execute(m_execute):
    # return mock.patch("gql.client.Client.transport.execute", m_execute)
    # return mock.patch("gql.client.Transport.execute", m_execute)
    # return mock.patch("gql.transport.Transport.execute", m_execute)
    return mock.patch("pools.uniswap.RequestsHTTPTransport.execute", m_execute)


class TestLibUniswapRoi:
    address = "0x000000000000000000000000000000000000dEaD"
    contract_address = "0xA478c2975Ab1Ea89e8196811F51A7B7Ade33eB11"

    def setup_method(self):
        with mock.patch.dict("os.environ", {"WEB3_INFURA_PROJECT_ID": "1"}):
            from pools import uniswap
        self.uniswap = uniswap

    def teardown_method(self):
        self.clear_cache()

    def clear_cache(self):
        functions = (
            self.uniswap.get_eth_price,
            self.uniswap.get_liquidity_positions,
            self.uniswap.get_pair_info,
            self.uniswap.get_staking_positions,
        )
        for function in functions:
            function.cache_clear()

    def test_get_gql_client(self):
        with patch_session_fetch_schema() as m_fetch_schema:
            client = self.uniswap.get_gql_client()
        assert m_fetch_schema.call_args_list == [mock.call()]
        assert client is not None

    def test_get_gql_client_exception(self):
        """
        On `TransportServerError` exception a custom
        `TheGraphServiceDownException` should be re-raised.
        """
        content = ""
        status_code = 502
        with pytest.raises(
            self.uniswap.TheGraphServiceDownException, match="502 Server Error"
        ), patch_session_request(content, status_code) as m_request:
            self.uniswap.get_gql_client()
        assert m_request.call_args_list == [
            mock.call(
                "POST",
                "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
                headers=None,
                auth=None,
                cookies=None,
                timeout=None,
                verify=True,
                json=mock.ANY,
            )
        ]

    def test_gql_client_execute_exception(self):
        """
        On `TransportQueryError` exception a custom
        `TheGraphServiceDownException` should be re-raised.
        """
        request_string = '{bundle(id: "1") {ethPrice}}'
        query = gql(request_string)
        m_execute = mock.Mock(return_value=mock.Mock(errors=["Error1", "Error2"]))
        with pytest.raises(
            self.uniswap.TheGraphServiceDownException, match="Error1"
        ), patch_session_fetch_schema(), patch_gql_transport_execute(m_execute):
            self.uniswap.gql_client_execute(query)
        assert m_execute.call_args_list == [mock.call(mock.ANY)]

    def test_get_eth_price(self):
        m_execute = mock.Mock(return_value=GQL_ETH_PRICE_RESPONSE)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            eth_price = self.uniswap.get_eth_price()
        assert m_execute.call_count == 1
        assert eth_price == Decimal("321.123")
        assert str(eth_price) == GQL_ETH_PRICE_RESPONSE["bundle"]["ethPrice"]

    def test_get_eth_price_exception(self):
        """TheGraph exceptions should be caught and reraised."""
        m_execute = mock.Mock(
            side_effect=TransportServerError(
                {
                    "message": (
                        "service is overloaded and can not run the query right now."
                        "Please try again in a few minutes"
                    )
                }
            )
        )
        with pytest.raises(
            self.uniswap.TheGraphServiceDownException,
            match="service is overloaded",
        ), patch_client_execute(m_execute), patch_session_fetch_schema():
            self.uniswap.get_eth_price()
        assert m_execute.call_count == 1

    def test_get_pair_info(self):
        m_execute = mock.Mock(return_value=GQL_PAIR_INFO_RESPONSE)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            pair_info = self.uniswap.get_pair_info(self.contract_address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={"id": self.contract_address.lower()},
            )
        ]
        assert pair_info["pair"].keys() == {
            "id",
            "reserve0",
            "reserve1",
            "reserveUSD",
            "token0",
            "token0Price",
            "token1",
            "token1Price",
            "totalSupply",
        }

    def test_get_liquidity_positions(self):
        m_execute = mock.Mock(return_value=GQL_LIQUIDITY_POSITIONS_RESPONSE)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            positions = self.uniswap.get_liquidity_positions(self.address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={"id": self.address.lower()},
            )
        ]
        assert len(positions) == 2
        assert positions[0].keys() == {"liquidityTokenBalance", "pair"}

    def test_get_liquidity_positions_no_liquidity(self):
        """Makes sure the function doesn't crash on no liquidity positions."""
        m_execute = mock.Mock(return_value={"user": None})
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            positions = self.uniswap.get_liquidity_positions(self.address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={"id": self.address.lower()},
            )
        ]
        assert positions == []

    def test_get_staking_positions(self):
        m_contract = mock.Mock()
        m_contract().functions.balanceOf().call.return_value = 0
        with patch_web3_contract(m_contract):
            positions = self.uniswap.get_staking_positions(self.address)
        assert m_contract().functions.balanceOf().call.call_count == 4
        assert len(positions) == 0

    def test_get_token_daily(self):
        m_execute = mock.Mock(return_value=GQL_TOKEN_DAY_DATA_RESPONSE)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            data = self.uniswap.get_token_daily(self.contract_address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={"token": self.contract_address.lower()},
            )
        ]
        assert data == [
            {"date": datetime(2020, 10, 11, 0, 0), "price_usd": Decimal("0")},
            {"date": datetime(2020, 10, 12, 0, 0), "price_usd": Decimal("0")},
            {
                "date": datetime(2020, 10, 17, 0, 0),
                "price_usd": Decimal("32.32860336361385733755970401320658"),
            },
            {"date": datetime(2020, 10, 18, 0, 0), "price_usd": Decimal("0")},
            {"date": datetime(2020, 10, 21, 0, 0), "price_usd": Decimal("0")},
        ]
