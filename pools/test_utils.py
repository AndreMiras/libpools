from unittest import mock

GQL_ETH_PRICE_RESPONSE = {"bundle": {"ethPrice": "321.123"}}
GQL_LIQUIDITY_POSITIONS_RESPONSE = {
    "user": {
        "liquidityPositions": [
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
    }
}

GQL_PAIR_INFO_RESPONSE = {
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
    }
}


GQL_MINTS_BURNS_TX_RESPONSE = {
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
                "id": "0x7f9080f8c72c0ec21ec7e1690b94c52ebc4787bca66f2d154f6274...",
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
                "id": "0x08d4f7eb1896d9ec25d2d36f72252cdb45f735b922fd1e515e1ce6...",
                "timestamp": "1595873620",
            },
        },
    ],
}


GQL_TOKEN_DAY_DATA_RESPONSE = {
    "tokenDayDatas": [
        {"date": 1603584000, "priceUSD": "1.0037"},
        {"date": 1603497600, "priceUSD": "1.0053"},
        {"date": 1603411200, "priceUSD": "1.0063"},
        {"date": 1603324800, "priceUSD": "1.0047"},
        {"date": 1603238400, "priceUSD": "1.0059"},
        {"date": 1603152000, "priceUSD": "1.0049"},
    ]
}
GQL_PAIR_DAY_DATA_RESPONSE = {
    "pair": {
        "id": "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11",
        "reserveUSD": "415905325.9588990528391949333277547",
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
        "totalSupply": "8730969.742669688720211513",
    },
    "pairDayDatas": [
        {
            "date": 1603584000,
            "reserveUSD": "433176263.4363820888744425087438633",
            "totalSupply": "9069902.755513910975050686",
        },
        {
            "date": 1603497600,
            "reserveUSD": "435317156.2189432956087607791883648",
            "totalSupply": "9065803.30917003335268362",
        },
        {
            "date": 1603411200,
            "reserveUSD": "432572804.7594039159237288025989709",
            "totalSupply": "9033867.416922493126112964",
        },
        {
            "date": 1603324800,
            "reserveUSD": "431764296.8691012640837948223336187",
            "totalSupply": "8963586.802246124942226919",
        },
        {
            "date": 1603238400,
            "reserveUSD": "423735194.9935538342436108196570895",
            "totalSupply": "9037152.290229410449908895",
        },
        {
            "date": 1603152000,
            "reserveUSD": "411207002.0385470304033146757759173",
            "totalSupply": "9054265.837647610072038259",
        },
    ],
}

GQL_PAIRS_RESPONSE = {
    "pairs": [
        {
            "id": "0xc5ddc3e9d103b9dfdf32ae7096f1392cf88696f9",
            "reserve0": "2063243.37701238",
            "reserve1": "78990431.276124196481995237",
            "reserveUSD": "1155422539.501794978568848429540974",
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
            "totalSupply": "6.764183030477266625",
        },
        {
            "id": "0xbb2b8038a1640196fbe3e38816f3e67cba72d940",
            "reserve0": "26186.56317714",
            "reserve1": "854243.645375842632389955",
            "reserveUSD": "688815654.2814067218630940203749505",
            "token0": {
                "derivedETH": "32.62144938979884788549711871554279",
                "id": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
                "name": "Wrapped BTC",
                "symbol": "WBTC",
            },
            "token0Price": "0.03065467717423717613465000666387854",
            "token1": {
                "derivedETH": "1",
                "id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                "name": "Wrapped Ether",
                "symbol": "WETH",
            },
            "token1Price": "32.62144938979884788549711871554279",
            "totalSupply": "1.375359727911146499",
        },
        {
            "id": "0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc",
            "reserve0": "317611971.451732",
            "reserve1": "786437.873958944776984124",
            "reserveUSD": "634135172.5331979997924002078257594",
            "token0": {
                "derivedETH": "0.002476096446756450426416512921592668",
                "id": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                "name": "USD//C",
                "symbol": "USDC",
            },
            "token0Price": "403.861489850261997342877776919223",
            "token1": {
                "derivedETH": "1",
                "id": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                "name": "Wrapped Ether",
                "symbol": "WETH",
            },
            "token1Price": "0.002476096446756450426416512921592668",
            "totalSupply": "12.621500317891400641",
        },
    ]
}


def patch_web3_contract(m_contract):
    return mock.patch("pools.uniswap.web3.eth.contract", m_contract)


def patch_client_execute(m_execute):
    return mock.patch("pools.uniswap.Client.execute", m_execute)


def patch_session_fetch_schema():
    """Bypassing `fetch_schema()` on unit tests."""
    return mock.patch("gql.client.SyncClientSession.fetch_schema")
