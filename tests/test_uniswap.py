from copy import deepcopy
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
    GQL_MINTS_BURNS_TX_RESPONSE,
    GQL_PAIR_DAY_DATA_RESPONSE,
    GQL_PAIR_INFO_RESPONSE,
    GQL_PAIRS_RESPONSE,
    GQL_TOKEN_DAY_DATA_RESPONSE,
    patch_client_execute,
    patch_get_eth_price,
    patch_get_liquidity_positions,
    patch_get_lp_transactions,
    patch_get_staking_positions,
    patch_portfolio,
    patch_session_fetch_schema,
    patch_sys_argv,
    patch_web3_contract,
)


def patch_session_request(content, status_code=200):
    response = Response()
    response.status_code = status_code
    response.raw = BytesIO(content.encode())
    m_request = mock.Mock(return_value=response)
    return mock.patch("requests.Session.request", m_request)


def patch_gql_transport_execute(m_execute):
    return mock.patch("pools.uniswap.RequestsHTTPTransport.execute", m_execute)


class TestLibUniswapRoi:
    address = "0x000000000000000000000000000000000000dEaD"
    # DAI
    token_address = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
    # DAI-ETH
    pair_address = "0xA478c2975Ab1Ea89e8196811F51A7B7Ade33eB11"

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
            self.uniswap.get_token_daily_raw,
            self.uniswap.get_pair_daily_raw,
            self.uniswap.portfolio,
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
            pair_info = self.uniswap.get_pair_info(self.pair_address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={"id": self.pair_address.lower()},
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

    def test_get_staking_positions_balance(self):
        m_contract = mock.Mock()
        m_contract().functions.balanceOf().call.side_effect = [1, 0, 0, 0]
        m_execute = mock.Mock(return_value=GQL_PAIR_INFO_RESPONSE)
        with patch_web3_contract(m_contract), patch_client_execute(
            m_execute
        ), patch_session_fetch_schema():
            positions = self.uniswap.get_staking_positions(self.address)
        assert m_execute.call_count == 1
        assert m_contract().functions.balanceOf().call.call_count == 4
        assert len(positions) == 1
        assert positions == [
            {
                "pair": {
                    "id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
                    "reserve0": "202079477.297395245222385992",
                    "reserve1": "554825.663433614212350256",
                    "reserveUSD": "438900192.169828320338927756595308",
                    "token0": {
                        "derivedETH": "0.002745581445745187399781487618568183",
                        "id": "0x6b175474e89094c44da98b954eedeac495271d0f",
                        "name": "Dai Stablecoin",
                        "symbol": "DAI",
                    },
                    "token0Price": "364.2215755608687365540815738979592",
                    "token1": {
                        "derivedETH": "1",
                        "id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                        "name": "Wrapped Ether",
                        "symbol": "WETH",
                    },
                    "token1Price": "0.002745581445745187399781487618568183",
                    "totalSupply": "8967094.518364383041536096",
                    "staking_contract_address": (
                        "0xa1484C3aa22a66C62b77E0AE78E15258bd0cB711"
                    ),
                },
                "liquidityTokenBalance": Decimal("1E-18"),
            }
        ]

    def test_get_token_daily(self):
        m_execute = mock.Mock(return_value=GQL_TOKEN_DAY_DATA_RESPONSE)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            data = self.uniswap.get_token_daily(self.token_address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={"token": self.token_address.lower()},
            )
        ]
        assert data == [
            {
                "date": datetime(2020, 10, 25, 0, 0),
                "price_usd": Decimal("1.0037"),
            },
            {
                "date": datetime(2020, 10, 24, 0, 0),
                "price_usd": Decimal("1.0053"),
            },
            {
                "date": datetime(2020, 10, 23, 0, 0),
                "price_usd": Decimal("1.0063"),
            },
            {
                "date": datetime(2020, 10, 22, 0, 0),
                "price_usd": Decimal("1.0047"),
            },
            {
                "date": datetime(2020, 10, 21, 0, 0),
                "price_usd": Decimal("1.0059"),
            },
            {
                "date": datetime(2020, 10, 20, 0, 0),
                "price_usd": Decimal("1.0049"),
            },
        ]

    def test_get_pair_daily(self):
        m_execute = mock.Mock(return_value=GQL_PAIR_DAY_DATA_RESPONSE)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            data = self.uniswap.get_pair_daily(self.pair_address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={
                    "id": self.pair_address.lower(),
                    "pairAddress": self.pair_address.lower(),
                },
            )
        ]
        assert data == {
            "pair": {
                "id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
                "price_usd": Decimal("47.63563936389575939010629216"),
                "reserve_usd": Decimal("415905325.9588990528391949333277547"),
                "symbol": "DAI-WETH",
                "token0": {
                    "derivedETH": "0.002482164437276671900656302172320963",
                    "id": "0x6b175474e89094c44da98b954eedeac495271d0f",
                    "name": "Dai Stablecoin",
                    "symbol": "DAI",
                },
                "token0Price": "402.87419519117702623465593526239",
                "token1": {
                    "derivedETH": "1",
                    "id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                    "name": "Wrapped Ether",
                    "symbol": "WETH",
                },
                "token1Price": "0.002482164437276671900656302172320963",
                "total_supply": Decimal("8730969.742669688720211513"),
            },
            "date_price": [
                {
                    "date": datetime(2020, 10, 25, 0, 0),
                    "price_usd": Decimal("47.75974727766944294903865913"),
                },
                {
                    "date": datetime(2020, 10, 24, 0, 0),
                    "price_usd": Decimal("48.01749402379172222921539513"),
                },
                {
                    "date": datetime(2020, 10, 23, 0, 0),
                    "price_usd": Decimal("47.88345730523966278509766686"),
                },
                {
                    "date": datetime(2020, 10, 22, 0, 0),
                    "price_usd": Decimal("48.16869701768362998144941414"),
                },
                {
                    "date": datetime(2020, 10, 21, 0, 0),
                    "price_usd": Decimal("46.88813260917142369483660351"),
                },
                {
                    "date": datetime(2020, 10, 20, 0, 0),
                    "price_usd": Decimal("45.41583043969722591000008424"),
                },
            ],
        }
        # make a second call to make sure the cached data wasn't mutated
        # from previous calls
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            data = self.uniswap.get_pair_daily(self.pair_address)
        assert data.keys() == {"pair", "date_price"}

    def test_get_pair_daily_total_supply_0(self):
        """
        Makes sure a total `totalSupply` of `0` in The Graph response
        doesn't crash the library.
        Note that when both numerator and denominator are zero the exception
        is also different.
        """
        gql_pair_day_data_response = deepcopy(GQL_PAIR_DAY_DATA_RESPONSE)
        gql_pair_day_data_response["pairDayDatas"] = [
            {
                "date": 1603584000,
                "reserveUSD": "433176263.4363820888744425087438633",
                "totalSupply": "0",
            },
            {
                "date": 1603497600,
                "reserveUSD": "435317156.2189432956087607791883648",
                "totalSupply": "9065803.30917003335268362",
            },
            {
                "date": 1603411200,
                "reserveUSD": "0",
                "totalSupply": "0",
            },
        ]
        m_execute = mock.Mock(return_value=gql_pair_day_data_response)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            data = self.uniswap.get_pair_daily(self.pair_address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={
                    "id": self.pair_address.lower(),
                    "pairAddress": self.pair_address.lower(),
                },
            )
        ]
        assert data == {
            "pair": mock.ANY,
            "date_price": [
                {"date": datetime(2020, 10, 25, 0, 0), "price_usd": Decimal("0")},
                {
                    "date": datetime(2020, 10, 24, 0, 0),
                    "price_usd": Decimal("48.01749402379172222921539513"),
                },
                {"date": datetime(2020, 10, 23, 0, 0), "price_usd": Decimal("0")},
            ],
        }

    def test_get_pairs(self):
        m_execute = mock.Mock(return_value=GQL_PAIRS_RESPONSE)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            data = self.uniswap.get_pairs()
        assert m_execute.call_args_list == [mock.call(mock.ANY)]
        assert data == [
            {
                "id": "0xc5ddc3e9d103b9dfdf32ae7096f1392cf88696f9",
                "price_usd": Decimal("170814795.2673407741498589706"),
                "reserve0": "2063243.37701238",
                "reserve1": "78990431.276124196481995237",
                "reserve_usd": Decimal("1155422539.501794978568848429540974"),
                "symbol": "FCBTC-TWOB",
                "token0": {
                    "derivedETH": "1.384712347348822582084534991907731",
                    "id": "0x4c6e796bbfe5eb37f9e3e0f66c009c8bf2a5f428",
                    "name": "FC Bitcoin",
                    "symbol": "FCBTC",
                },
                "token0Price": "0.02612016852775457641571125345392988",
                "token1": {
                    "derivedETH": "0",
                    "id": "0x975ce667d59318e13da8acd3d2f534be5a64087b",
                    "name": "The Whale of Blockchain",
                    "symbol": "TWOB",
                },
                "token1Price": "38.284592189266595295457534649458",
                "total_supply": Decimal("6.764183030477266625"),
            },
            {
                "id": "0xbb2b8038a1640196fbe3e38816f3e67cba72d940",
                "price_usd": Decimal("500825813.2783620728235026365"),
                "reserve0": "26186.56317714",
                "reserve1": "854243.645375842632389955",
                "reserve_usd": Decimal("688815654.2814067218630940203749505"),
                "symbol": "WBTC-WETH",
                "token0": mock.ANY,
                "token0Price": "0.03065467717423717613465000666387854",
                "token1": mock.ANY,
                "token1Price": "32.62144938979884788549711871554279",
                "total_supply": Decimal("1.375359727911146499"),
            },
            {
                "id": "0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc",
                "price_usd": Decimal("50242455.85402316180433129715"),
                "reserve0": "317611971.451732",
                "reserve1": "786437.873958944776984124",
                "reserve_usd": Decimal("634135172.5331979997924002078257594"),
                "symbol": "USDC-WETH",
                "token0": mock.ANY,
                "token0Price": "403.861489850261997342877776919223",
                "token1": mock.ANY,
                "token1Price": "0.002476096446756450426416512921592668",
                "total_supply": Decimal("12.621500317891400641"),
            },
        ]

    def test_get_lp_transactions(self):
        m_execute = mock.Mock(return_value=GQL_MINTS_BURNS_TX_RESPONSE)
        with patch_client_execute(m_execute), patch_session_fetch_schema():
            data = self.uniswap.get_lp_transactions(self.address, self.pair_address)
        assert m_execute.call_args_list == [
            mock.call(
                mock.ANY,
                variable_values={
                    "address": self.address.lower(),
                    "pairs": self.pair_address,
                },
            )
        ]
        assert data == {
            "burns": [],
            "mints": [
                {
                    "amount0": "15860000",
                    "amount1": "600",
                    "amountUSD": "229661.2283368789267441858327732994",
                    "liquidity": "97549.987186057589967631",
                    "pair": {"id": "0xf227e97616063a0ea4143744738f9def2aa06743"},
                    "sender": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
                    "to": "0x000000000000000000000000000000000000dead",
                    "transaction": {
                        "blockNumber": "11046485",
                        "id": (
                            "0x7f9080f8c72c0ec21ec7e1690b9"
                            "4c52ebc4787bca66f2d154f6274..."
                        ),
                        "timestamp": "1602581467",
                    },
                },
                {
                    "amount0": "23188460.096098020166920577",
                    "amount1": "1649.824913049740795957",
                    "amountUSD": "531596.1714480471128118203674972062",
                    "liquidity": "195593.709412655447555532",
                    "pair": {"id": "0xc822d85d2dcedfaf2cefcf69dbd5588e7ffc9f10"},
                    "sender": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
                    "to": "0x000000000000000000000000000000000000dead",
                    "transaction": {
                        "blockNumber": "10543065",
                        "id": (
                            "0x08d4f7eb1896d9ec25d2d36f722"
                            "52cdb45f735b922fd1e515e1ce6..."
                        ),
                        "timestamp": "1595873620",
                    },
                },
            ],
        }

    def test_extract_pair_info(self):
        pair = {
            "id": "0x0357347524debff4c783d0091b8c0101d16483b4",
            "reserve0": "65433589.260222401644767305",
            "reserve1": "0.026423215213923281",
            "reserveUSD": "15.13802717784757628627128541760104",
            "token0": {
                "derivedETH": "0",
                "id": "0xa507570aea52368f88d4ec11c1f97851270cd117",
                "name": "SojuToken",
                "symbol": "Soju",
            },
            "token0Price": "2476367418.971149363049022948777915",
            "token1": {
                "derivedETH": "1",
                "id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                "name": "Wrapped Ether",
                "symbol": "WETH",
            },
            "token1Price": "0.0000000004038172980063950624361315799192937",
            "totalSupply": "1266.682478365215644063",
        }
        balance = Decimal("12.34")
        eth_price = Decimal("321.123")
        pair_info = self.uniswap.extract_pair_info(pair, balance, eth_price)
        assert pair_info == {
            "balance_usd": Decimal("0.08266172634844539683211792027"),
            "contract_address": "0x0357347524debff4c783d0091b8c0101d16483b4",
            "owner_balance": Decimal("12.34"),
            "price_usd": Decimal("0.01195092490533599340577635533"),
            "share": Decimal("0.9741983654756196260478308400"),
            "staking_contract_address": None,
            "symbol": "Soju-WETH",
            "tokens": [
                {
                    "balance": Decimal("637452.9570451172247361995822"),
                    "balance_usd": Decimal("0E-25"),
                    "price_usd": Decimal("0.000"),
                    "symbol": "Soju",
                },
                {
                    "balance": Decimal("0.0002574145307201458532466311048"),
                    "balance_usd": Decimal("0.08266172634844539683211792027"),
                    "price_usd": Decimal("321.123"),
                    "symbol": "WETH",
                },
            ],
            "total_supply": Decimal("1266.682478365215644063"),
        }

    def test_clean_transactions(self):
        mints_burns = {
            "burns": [
                {
                    "amount0": "1378.90",
                    "amount1": "3.94",
                    "amountUSD": "2762.05",
                    "liquidity": "53.44",
                    "pair": {"id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"},
                    "sender": "0x000000000000000000000000000000000000dEaD",
                    "to": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
                    "transaction": {
                        "blockNumber": "11282090",
                        "timestamp": "1605704575",
                    },
                },
                {
                    "amount0": "531.21",
                    "amount1": "2.17",
                    "amountUSD": "1066.42",
                    "liquidity": "33.56",
                    "pair": {"id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"},
                    "sender": "0x000000000000000000000000000000000000dEaD",
                    "to": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
                    "transaction": {
                        "blockNumber": "10325381",
                        "timestamp": "1592960274",
                    },
                },
            ],
            "mints": [
                {
                    "amount0": "130.28",
                    "amount1": "8.57",
                    "amountUSD": "6039.62",
                    "liquidity": "24.11",
                    "pair": {"id": "0x3b3d4eefdc603b232907a7f3d0ed1eea5c62b5f7"},
                    "sender": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
                    "to": "0x000000000000000000000000000000000000dEaD",
                    "transaction": {
                        "blockNumber": "10945917",
                        "timestamp": "1601227586",
                    },
                },
                {
                    "amount0": "1142.83",
                    "amount1": "3.11",
                    "amountUSD": "2319.12",
                    "liquidity": "49.86",
                    "pair": {"id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"},
                    "sender": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
                    "to": "0x000000000000000000000000000000000000dEaD",
                    "transaction": {
                        "blockNumber": "10882468",
                        "timestamp": "1600381572",
                    },
                },
                {
                    "amount0": "578.02",
                    "amount1": "2.65",
                    "amountUSD": "1157.09",
                    "liquidity": "37.99",
                    "pair": {"id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"},
                    "sender": "0xf164fc0ec4e93095b804a4795bbe1e041497b92a",
                    "to": "0x000000000000000000000000000000000000dEaD",
                    "transaction": {
                        "blockNumber": "10262368",
                        "timestamp": "1592117410",
                    },
                },
            ],
        }
        transaction_dict = self.uniswap.clean_transactions(mints_burns)
        assert transaction_dict == {
            "0x3b3d4eefdc603b232907a7f3d0ed1eea5c62b5f7": [
                {
                    "amount0": Decimal("130.28"),
                    "amount1": Decimal("8.57"),
                    "amountUSD": Decimal("6039.62"),
                    "liquidity": Decimal("24.11"),
                    "pair": {"id": "0x3b3d4eefdc603b232907a7f3d0ed1eea5c62b5f7"},
                    "sender": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
                    "to": "0x000000000000000000000000000000000000dEaD",
                    "transaction": {
                        "block_number": 10945917,
                        "timestamp": datetime(2020, 9, 27, 17, 26, 26),
                    },
                    "type": "mint",
                }
            ],
            "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11": [
                {
                    "amount0": Decimal("578.02"),
                    "amount1": Decimal("2.65"),
                    "amountUSD": Decimal("1157.09"),
                    "liquidity": Decimal("37.99"),
                    "pair": {"id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"},
                    "sender": "0xf164fc0ec4e93095b804a4795bbe1e041497b92a",
                    "to": "0x000000000000000000000000000000000000dEaD",
                    "transaction": {
                        "block_number": 10262368,
                        "timestamp": datetime(2020, 6, 14, 6, 50, 10),
                    },
                    "type": "mint",
                },
                {
                    "amount0": Decimal("531.21"),
                    "amount1": Decimal("2.17"),
                    "amountUSD": Decimal("1066.42"),
                    "liquidity": Decimal("33.56"),
                    "pair": {"id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"},
                    "sender": "0x000000000000000000000000000000000000dEaD",
                    "to": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
                    "transaction": {
                        "block_number": 10325381,
                        "timestamp": datetime(2020, 6, 24, 0, 57, 54),
                    },
                    "type": "burn",
                },
                {
                    "amount0": Decimal("1142.83"),
                    "amount1": Decimal("3.11"),
                    "amountUSD": Decimal("2319.12"),
                    "liquidity": Decimal("49.86"),
                    "pair": {"id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"},
                    "sender": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
                    "to": "0x000000000000000000000000000000000000dEaD",
                    "transaction": {
                        "block_number": 10882468,
                        "timestamp": datetime(2020, 9, 17, 22, 26, 12),
                    },
                    "type": "mint",
                },
                {
                    "amount0": Decimal("1378.90"),
                    "amount1": Decimal("3.94"),
                    "amountUSD": Decimal("2762.05"),
                    "liquidity": Decimal("53.44"),
                    "pair": {"id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"},
                    "sender": "0x000000000000000000000000000000000000dEaD",
                    "to": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
                    "transaction": {
                        "block_number": 11282090,
                        "timestamp": datetime(2020, 11, 18, 13, 2, 55),
                    },
                    "type": "burn",
                },
            ],
        }

    def test_portfolio(self):
        """Basic portfolio testing."""
        price = 300
        positions = []
        mints_burns = {
            "mints": [],
            "burns": [],
        }
        with patch_get_liquidity_positions(
            positions
        ) as m_get_liquidity_positions, patch_get_staking_positions(
            positions
        ) as m_get_staking_positions, patch_get_lp_transactions(
            mints_burns
        ) as m_get_lp_transactions, patch_get_eth_price(
            price
        ) as m_get_eth_price:
            data = self.uniswap.portfolio(self.address)
        assert m_get_liquidity_positions.call_args_list == [mock.call(self.address)]
        assert m_get_staking_positions.call_args_list == [mock.call(self.address)]
        assert m_get_lp_transactions.call_args_list == [mock.call(self.address, [])]
        assert m_get_eth_price.call_args_list == [mock.call()]
        assert data == {
            "address": "0x000000000000000000000000000000000000dEaD",
            "pairs": [],
            "balance_usd": 0,
        }

    def test_portfolio_positions(self):
        """Portfolio with positions testing."""
        price = 300
        liquidity_positions = [
            {
                "liquidityTokenBalance": "65.417152403305745713",
                "pair": {
                    "id": "0x3b3d4eefdc603b232907a7f3d0ed1eea5c62b5f7",
                    "reserve0": "98885.875625086259763385",
                    "reserve1": "3065.622053657196599417",
                    "reserveUSD": "2755342.621143665226669595853113687",
                    "token0": {
                        "derivedETH": "0.03100161710940527870014085576340626",
                        "id": "0x0ae055097c6d159879521c384f1d2123d1f195e6",
                        "name": "STAKE",
                        "symbol": "STAKE",
                    },
                    "token0Price": "32.25638186779036564112849328358329",
                    "token1": {
                        "derivedETH": "1",
                        "id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                        "name": "Wrapped Ether",
                        "symbol": "WETH",
                    },
                    "token1Price": "0.03100161710940527870014085576340626",
                    "totalSupply": "12132.548610419336726782",
                },
            },
            {
                "liquidityTokenBalance": "123.321",
                "pair": {
                    "id": "0xd3d2e2692501a5c9ca623199d38826e513033a17",
                    "reserve0": "7795837.60970437134772868",
                    "reserve1": "64207.224033613483840543",
                    "reserveUSD": "48844843.23332099147592073020832003",
                    "token0": {
                        "derivedETH": "0.008236090494456606334236333082884844",
                        "id": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
                        "name": "Uniswap",
                        "symbol": "UNI",
                    },
                    "token0Price": "121.4168300692010713970072022761557",
                    "token1": {
                        "derivedETH": "1",
                        "id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                        "name": "Wrapped Ether",
                        "symbol": "WETH",
                    },
                    "token1Price": "0.008236090494456606334236333082884844",
                    "totalSupply": "383443.946054848107867734",
                },
            },
        ]
        staking_positions = [
            {
                "pair": {
                    "id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
                    "reserve0": "202079477.297395245222385992",
                    "reserve1": "554825.663433614212350256",
                    "reserveUSD": "438900192.169828320338927756595308",
                    "token0": {
                        "derivedETH": "0.002745581445745187399781487618568183",
                        "id": "0x6b175474e89094c44da98b954eedeac495271d0f",
                        "name": "Dai Stablecoin",
                        "symbol": "DAI",
                    },
                    "token0Price": "364.2215755608687365540815738979592",
                    "token1": {
                        "derivedETH": "1",
                        "id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                        "name": "Wrapped Ether",
                        "symbol": "WETH",
                    },
                    "token1Price": "0.002745581445745187399781487618568183",
                    "totalSupply": "8967094.518364383041536096",
                    "staking_contract_address": (
                        "0xa1484C3aa22a66C62b77E0AE78E15258bd0cB711"
                    ),
                },
                "liquidityTokenBalance": Decimal("1E-18"),
            }
        ]
        mints_burns = {
            "burns": [],
            "mints": [
                {
                    "amount0": "15860000",
                    "amount1": "600",
                    "amountUSD": "229661.2283368789267441858327732994",
                    "liquidity": "97549.987186057589967631",
                    "pair": {"id": "0xf227e97616063a0ea4143744738f9def2aa06743"},
                    "sender": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
                    "to": "0x000000000000000000000000000000000000dead",
                    "transaction": {
                        "blockNumber": "11046485",
                        "id": (
                            "0x7f9080f8c72c0ec21ec7e1690b9"
                            "4c52ebc4787bca66f2d154f6274..."
                        ),
                        "timestamp": "1602581467",
                    },
                },
                {
                    "amount0": "23188460.096098020166920577",
                    "amount1": "1649.824913049740795957",
                    "amountUSD": "531596.1714480471128118203674972062",
                    "liquidity": "195593.709412655447555532",
                    "pair": {"id": "0xc822d85d2dcedfaf2cefcf69dbd5588e7ffc9f10"},
                    "sender": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
                    "to": "0x000000000000000000000000000000000000dead",
                    "transaction": {
                        "blockNumber": "10543065",
                        "id": (
                            "0x08d4f7eb1896d9ec25d2d36f722"
                            "52cdb45f735b922fd1e515e1ce6..."
                        ),
                        "timestamp": "1595873620",
                    },
                },
            ],
        }
        with patch_get_liquidity_positions(
            liquidity_positions
        ) as m_get_liquidity_positions, patch_get_staking_positions(
            staking_positions
        ) as m_get_staking_positions, patch_get_lp_transactions(
            mints_burns
        ) as m_get_lp_transactions, patch_get_eth_price(
            price
        ) as m_get_eth_price:
            data = self.uniswap.portfolio(self.address)
        assert m_get_liquidity_positions.call_args_list == [mock.call(self.address)]
        assert m_get_staking_positions.call_args_list == [mock.call(self.address)]
        pair_addresses = [
            "0x3b3d4eefdc603b232907a7f3d0ed1eea5c62b5f7",
            "0xd3d2e2692501a5c9ca623199d38826e513033a17",
            "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
        ]
        assert m_get_lp_transactions.call_args_list == [
            mock.call(self.address, pair_addresses)
        ]
        assert m_get_eth_price.call_args_list == [mock.call()]
        assert data == {
            "address": "0x000000000000000000000000000000000000dEaD",
            "balance_usd": Decimal("22307.63671390229301193316137"),
            "pairs": [
                {
                    "balance_usd": Decimal("9917.665522780703135364231718"),
                    "contract_address": "0x3b3d4eefdc603b232907a7f3d0ed1eea5c62b5f7",
                    "owner_balance": Decimal("65.417152403305745713"),
                    "price_usd": Decimal("227.1033654690984538946436433"),
                    "share": Decimal("0.5391872268875643568885981312"),
                    "staking_contract_address": None,
                    "symbol": "STAKE-WETH",
                    "tokens": [
                        {
                            "balance": Decimal("533.1800105663885501708056239"),
                            "balance_usd": Decimal("4958.832761390351567682115858"),
                            "price_usd": Decimal("9.300485132821583610042256729"),
                            "symbol": "STAKE",
                        },
                        {
                            "balance": Decimal("16.52944253796783855894038620"),
                            "balance_usd": Decimal("4958.832761390351567682115860"),
                            "price_usd": Decimal("300"),
                            "symbol": "WETH",
                        },
                    ],
                    "total_supply": Decimal("12132.548610419336726782"),
                    "transactions": [],
                },
                {
                    "balance_usd": Decimal("12389.97119112158987653180554"),
                    "contract_address": "0xd3d2e2692501a5c9ca623199d38826e513033a17",
                    "owner_balance": Decimal("123.321"),
                    "price_usd": Decimal("127.3845727279631862808239477"),
                    "share": Decimal("0.03216141531736690197605588913"),
                    "staking_contract_address": None,
                    "symbol": "UNI-WETH",
                    "tokens": [
                        {
                            "balance": Decimal("2507.251711124511447287084553"),
                            "balance_usd": Decimal("6194.985595560794938265902768"),
                            "price_usd": Decimal("2.470827148336981900270899925"),
                            "symbol": "UNI",
                        },
                        {
                            "balance": Decimal("20.64995198520264979421967589"),
                            "balance_usd": Decimal("6194.985595560794938265902767"),
                            "price_usd": Decimal("300"),
                            "symbol": "WETH",
                        },
                    ],
                    "total_supply": Decimal("383443.946054848107867734"),
                    "transactions": [],
                },
                {
                    "balance_usd": Decimal("3.712410941787299799109246000E-17"),
                    "contract_address": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
                    "owner_balance": Decimal("1E-18"),
                    "price_usd": Decimal("48.94564134134772579153409462"),
                    "share": Decimal("1.115188423576918100500298355E-23"),
                    "staking_contract_address": (
                        "0xa1484C3aa22a66C62b77E0AE78E15258bd0cB711"
                    ),
                    "symbol": "DAI-WETH",
                    "tokens": [
                        {
                            "balance": Decimal("2.253566937245298137197573486E-17"),
                            "balance_usd": Decimal("1.856205470893649899554623000E-17"),
                            "price_usd": Decimal("0.8236744337235562199344462856"),
                            "symbol": "DAI",
                        },
                        {
                            "balance": Decimal("6.187351569645499665182076665E-20"),
                            "balance_usd": Decimal("1.856205470893649899554623000E-17"),
                            "price_usd": Decimal("300"),
                            "symbol": "WETH",
                        },
                    ],
                    "total_supply": Decimal("8967094.518364383041536096"),
                    "transactions": [],
                },
            ],
        }

    def test_portfolio_invalid_address(self):
        """Invalid addresses are handled with an explicit exception."""
        address = "0xInvalidAdress"
        with pytest.raises(self.uniswap.InvalidAddressException, match=address):
            self.uniswap.portfolio(address)

    def test_main(self):
        argv = ["pools/uniswap.py"]
        exit_code = 2
        with patch_sys_argv(argv), patch_portfolio() as m_portfolio, pytest.raises(
            SystemExit, match=str(exit_code)
        ):
            self.uniswap.main()
        assert m_portfolio.call_args_list == []

    def test_main_argv(self):
        argv = ["pools/uniswap.py", self.address]
        with patch_sys_argv(argv), patch_portfolio() as m_portfolio:
            self.uniswap.main()
        assert m_portfolio.call_args_list == [mock.call(self.address)]
