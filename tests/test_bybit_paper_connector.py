from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import logging
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qsl, urlsplit

import pytest

from trading_hub import bybit_paper_connector as connector
from trading_hub.bybit_paper_connector import (
    AUTHENTICATED_READ_PATHS,
    PUBLIC_READ_PATHS,
    BybitApiError,
    BybitAuthError,
    BybitConfigError,
    BybitMalformedResponseError,
    BybitPaperClient,
    BybitPaperConfig,
    BybitTransportError,
    DisabledPaperOrderGateway,
    HttpResponse,
    PaperOrderRequest,
    TradingDisabledError,
    build_auth_headers,
    sign_request,
)

# Obviously fake test credentials; never real values.
FAKE_KEY = 'test-key-AAAA'
FAKE_SECRET = 'test-secret-ZZZZ-do-not-leak'
NOW_MS = 1_700_000_000_000


def ok(result: object, **extra: object) -> HttpResponse:
    payload = {'retCode': 0, 'retMsg': 'OK', 'result': result, 'time': NOW_MS, **extra}
    return HttpResponse(200, json.dumps(payload).encode('utf-8'))


class FakeTransport:
    """Scripted transport: each call pops the next response (or raises it if it is an exception)."""

    def __init__(self, *responses: HttpResponse | BaseException) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, method, url, headers, timeout):
        self.calls.append({'method': method, 'url': url, 'headers': dict(headers), 'timeout': timeout})
        if not self.responses:
            raise AssertionError('unexpected extra HTTP call')
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def make_client(*responses, env=None, **config_overrides) -> tuple[BybitPaperClient, FakeTransport, list[float]]:
    environ = {'BYBIT_API_KEY': FAKE_KEY, 'BYBIT_API_SECRET': FAKE_SECRET, 'BYBIT_ENV': 'testnet', 'BYBIT_CATEGORY': 'linear'}
    environ.update(env or {})
    config = BybitPaperConfig.from_env(environ, **config_overrides)
    transport = FakeTransport(*responses)
    sleeps: list[float] = []
    client = BybitPaperClient(config, transport=transport, clock_ms=lambda: NOW_MS, sleep=sleeps.append)
    return client, transport, sleeps


# ---------------------------------------------------------------------------
# Config / environment safety
# ---------------------------------------------------------------------------


def test_config_defaults_are_testnet_linear_and_trading_disabled():
    config = BybitPaperConfig.from_env({})

    assert config.env == 'testnet'
    assert config.category == 'linear'
    assert config.base_url == 'https://api-testnet.bybit.com'
    assert config.trading_enabled is False
    assert config.has_credentials is False


def test_demo_env_uses_bybit_demo_host():
    assert BybitPaperConfig.from_env({'BYBIT_ENV': 'demo'}).base_url == 'https://api-demo.bybit.com'


@pytest.mark.parametrize('env', ['mainnet', 'live', 'prod', 'https://api.bybit.com', 'TESTNET-x'])
def test_non_paper_environments_are_rejected(env):
    with pytest.raises(BybitConfigError):
        BybitPaperConfig.from_env({'BYBIT_ENV': env})


def test_no_mainnet_host_is_reachable_from_config():
    assert all('api.bybit.com' not in url for url in connector.BYBIT_PAPER_BASE_URLS.values())
    assert set(connector.BYBIT_PAPER_BASE_URLS) == {'testnet', 'demo'}


def test_invalid_category_is_rejected():
    with pytest.raises(BybitConfigError):
        BybitPaperConfig.from_env({'BYBIT_CATEGORY': 'futures'})


def test_config_repr_and_str_never_expose_credentials():
    config = BybitPaperConfig.from_env({'BYBIT_API_KEY': FAKE_KEY, 'BYBIT_API_SECRET': FAKE_SECRET})

    for rendered in (repr(config), str(config), repr(config.api_secret), str(config.api_key), f'{config.api_secret}'):
        assert FAKE_SECRET not in rendered
        assert FAKE_KEY not in rendered
    assert config.has_credentials is True


def test_invalid_trading_flag_fails_closed():
    with pytest.raises(BybitConfigError) as excinfo:
        BybitPaperConfig.from_env({'BYBIT_TRADING_ENABLED': 'maybe'})
    assert 'maybe' not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Trading stays disabled
# ---------------------------------------------------------------------------


def test_trading_hard_default_is_false():
    assert connector.BYBIT_TRADING_ENABLED_DEFAULT is False
    assert BybitPaperConfig().trading_enabled is False
    assert DisabledPaperOrderGateway().trading_enabled is False


@pytest.mark.parametrize('flag', [None, 'false', '0', 'true', '1', 'yes'])
def test_order_gateway_always_refuses_even_when_flag_is_true(flag):
    environ = {} if flag is None else {'BYBIT_TRADING_ENABLED': flag}
    gateway = DisabledPaperOrderGateway(BybitPaperConfig.from_env(environ))
    order = PaperOrderRequest(symbol='BTCUSDT', side='Buy', qty=0.001)

    assert gateway.trading_enabled is False
    with pytest.raises(TradingDisabledError):
        gateway.submit_order(order)
    with pytest.raises(TradingDisabledError):
        gateway.cancel_order('BTCUSDT', 'order-1')


def test_order_gateway_never_touches_the_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('network call attempted')

    monkeypatch.setattr(connector, 'urlopen', forbidden)
    monkeypatch.setattr(connector, 'urllib_transport', forbidden)
    gateway = DisabledPaperOrderGateway(BybitPaperConfig.from_env({'BYBIT_TRADING_ENABLED': 'true'}))

    with pytest.raises(TradingDisabledError, match='not implemented'):
        gateway.submit_order(PaperOrderRequest(symbol='BTCUSDT', side='Sell', qty=1.0))


def test_client_exposes_no_order_or_withdrawal_methods():
    public_methods = {name for name, _ in inspect.getmembers(BybitPaperClient, inspect.isfunction) if not name.startswith('_')}

    assert public_methods == {
        'get_server_time',
        'get_tickers',
        'get_klines',
        'get_orderbook',
        'get_account_info',
        'get_wallet_balance',
        'get_positions',
    }


def test_allowlists_contain_only_read_endpoints():
    for path in PUBLIC_READ_PATHS | AUTHENTICATED_READ_PATHS:
        assert path.startswith(('/v5/market/', '/v5/account/', '/v5/position/list'))
    source = Path(connector.__file__).read_text(encoding='utf-8')
    for forbidden in ('/v5/order/', '/v5/asset/withdraw', '/v5/asset/transfer', "'POST'", 'set-leverage'):
        assert forbidden not in source


def test_non_allowlisted_path_is_refused_before_any_http_call():
    client, transport, _ = make_client()

    with pytest.raises(BybitConfigError):
        client._get('/v5/order/create', {'symbol': 'BTCUSDT'}, authenticated=True)
    with pytest.raises(BybitConfigError):
        client._get('/v5/account/wallet-balance', {}, authenticated=False)
    assert transport.calls == []


# ---------------------------------------------------------------------------
# Authentication / signature
# ---------------------------------------------------------------------------


def test_sign_request_matches_bybit_v5_hmac_sha256_spec():
    expected = hmac.new(
        FAKE_SECRET.encode(), f'{NOW_MS}{FAKE_KEY}5000accountType=UNIFIED'.encode(), hashlib.sha256
    ).hexdigest()

    signature = sign_request(api_key=FAKE_KEY, api_secret=FAKE_SECRET, timestamp_ms=NOW_MS, recv_window_ms=5000, payload='accountType=UNIFIED')

    assert signature == expected
    assert len(signature) == 64


def test_sign_request_known_vector():
    # Computed independently with: printf '%s' '1658384314791key5000category=linear&symbol=BTCUSDT' | openssl dgst -sha256 -hmac secret
    signature = sign_request(api_key='key', api_secret='secret', timestamp_ms=1658384314791, recv_window_ms=5000, payload='category=linear&symbol=BTCUSDT')

    assert signature == 'ccfb83a4990aaab72c1049cfd1dcf888f713c1fb105568d4526c6ced2f2973d8'


def test_authenticated_request_sends_signed_headers_over_exact_query_string():
    client, transport, _ = make_client(ok({'list': []}))

    client.get_wallet_balance(coin='usdt')

    call = transport.calls[0]
    split = urlsplit(call['url'])
    assert call['method'] == 'GET'
    assert f'{split.scheme}://{split.netloc}' == 'https://api-testnet.bybit.com'
    assert split.path == '/v5/account/wallet-balance'
    assert dict(parse_qsl(split.query)) == {'accountType': 'UNIFIED', 'coin': 'USDT'}
    headers = call['headers']
    assert headers['X-BAPI-API-KEY'] == FAKE_KEY
    assert headers['X-BAPI-TIMESTAMP'] == str(NOW_MS)
    assert headers['X-BAPI-RECV-WINDOW'] == '5000'
    assert headers['X-BAPI-SIGN-TYPE'] == '2'
    assert headers['X-BAPI-SIGN'] == sign_request(api_key=FAKE_KEY, api_secret=FAKE_SECRET, timestamp_ms=NOW_MS, recv_window_ms=5000, payload=split.query)
    assert FAKE_SECRET not in json.dumps(call)


def test_public_requests_carry_no_auth_headers():
    client, transport, _ = make_client(ok({'timeSecond': '1700000000', 'timeNano': '1700000000123456789'}))

    result = client.get_server_time()

    assert result['server_time_ms'] == 1700000000123
    assert transport.calls[0]['headers'] == {}


def test_authenticated_read_without_credentials_fails_before_http():
    config = BybitPaperConfig.from_env({})
    transport = FakeTransport()
    client = BybitPaperClient(config, transport=transport, clock_ms=lambda: NOW_MS, sleep=lambda _: None)

    with pytest.raises(BybitAuthError):
        client.get_wallet_balance()
    with pytest.raises(BybitAuthError):
        build_auth_headers(config, timestamp_ms=NOW_MS, query_string='')
    assert transport.calls == []


@pytest.mark.parametrize('ret_code', [10003, 10004, 33004])
def test_auth_ret_codes_raise_auth_error_without_retry(ret_code):
    body = json.dumps({'retCode': ret_code, 'retMsg': 'invalid api key', 'result': {}}).encode()
    client, transport, sleeps = make_client(HttpResponse(200, body))

    with pytest.raises(BybitAuthError) as excinfo:
        client.get_account_info()
    assert len(transport.calls) == 1
    assert sleeps == []
    assert FAKE_SECRET not in str(excinfo.value) and FAKE_KEY not in str(excinfo.value)


def test_http_401_raises_auth_error():
    client, transport, _ = make_client(HttpResponse(401, b''))

    with pytest.raises(BybitAuthError):
        client.get_positions()
    assert len(transport.calls) == 1


def test_each_retry_is_resigned_with_fresh_timestamp():
    config = BybitPaperConfig.from_env({'BYBIT_API_KEY': FAKE_KEY, 'BYBIT_API_SECRET': FAKE_SECRET})
    transport = FakeTransport(TimeoutError(), ok({'list': []}))
    clock = iter([NOW_MS, NOW_MS + 1500, NOW_MS + 1600])
    client = BybitPaperClient(config, transport=transport, clock_ms=lambda: next(clock), sleep=lambda _: None)

    client.get_wallet_balance()

    stamps = [call['headers']['X-BAPI-TIMESTAMP'] for call in transport.calls]
    signs = [call['headers']['X-BAPI-SIGN'] for call in transport.calls]
    assert stamps == [str(NOW_MS), str(NOW_MS + 1500)]
    assert signs[0] != signs[1]


# ---------------------------------------------------------------------------
# Timeout / retry
# ---------------------------------------------------------------------------


def test_timeout_is_passed_to_transport():
    client, transport, _ = make_client(ok({'timeNano': '1'}), timeout_seconds=3.5)

    client.get_server_time()

    assert transport.calls[0]['timeout'] == 3.5


def test_timeout_then_success_retries_with_exponential_backoff():
    ticker = {'symbol': 'BTCUSDT', 'lastPrice': '100'}
    client, transport, sleeps = make_client(TimeoutError('timed out'), URLError('reset'), ok({'list': [ticker]}))

    rows = client.get_tickers('BTCUSDT')

    assert rows[0]['last_price'] == 100.0
    assert len(transport.calls) == 3
    assert sleeps == [0.5, 1.0]


def test_retries_are_bounded_and_raise_transport_error():
    client, transport, sleeps = make_client(TimeoutError(), TimeoutError(), TimeoutError(), TimeoutError(), max_retries=2)

    with pytest.raises(BybitTransportError, match='3 attempt'):
        client.get_server_time()
    assert len(transport.calls) == 3
    assert len(sleeps) == 2
    assert len(transport.responses) == 1


def test_backoff_is_capped():
    client, _, sleeps = make_client(*[TimeoutError()] * 6, max_retries=5, backoff_seconds=1.0, max_backoff_seconds=3.0)

    with pytest.raises(BybitTransportError):
        client.get_server_time()
    assert sleeps == [1.0, 2.0, 3.0, 3.0, 3.0]


def test_max_retries_upper_bound_enforced():
    with pytest.raises(BybitConfigError):
        BybitPaperConfig(max_retries=50)


@pytest.mark.parametrize('status', [429, 502, 503])
def test_retryable_http_status_then_success(status):
    client, transport, sleeps = make_client(HttpResponse(status, b'busy'), ok({'timeNano': '2000000'}))

    assert client.get_server_time()['server_time_ms'] == 2
    assert len(transport.calls) == 2
    assert sleeps == [0.5]


def test_rate_limit_ret_code_is_retried_then_surfaces_api_error():
    limited = HttpResponse(200, json.dumps({'retCode': 10006, 'retMsg': 'Too many visits', 'result': {}}).encode())
    client, transport, _ = make_client(limited, limited, limited)

    with pytest.raises(BybitApiError) as excinfo:
        client.get_server_time()
    assert excinfo.value.ret_code == 10006
    assert len(transport.calls) == 3


def test_non_retryable_api_error_is_not_retried():
    body = json.dumps({'retCode': 10001, 'retMsg': 'params error', 'result': {}}).encode()
    client, transport, sleeps = make_client(HttpResponse(200, body))

    with pytest.raises(BybitApiError) as excinfo:
        client.get_tickers('BTCUSDT')
    assert excinfo.value.ret_code == 10001
    assert len(transport.calls) == 1
    assert sleeps == []


def test_http_400_is_not_retried():
    client, transport, _ = make_client(HttpResponse(400, b'bad'))

    with pytest.raises(BybitApiError):
        client.get_server_time()
    assert len(transport.calls) == 1


def test_retry_logs_never_contain_credentials(caplog):
    client, _, _ = make_client(TimeoutError(), HttpResponse(503, b''), ok({'list': []}))

    with caplog.at_level(logging.DEBUG, logger=connector.__name__):
        client.get_wallet_balance()

    assert caplog.records, 'retries should be logged'
    assert FAKE_SECRET not in caplog.text
    assert FAKE_KEY not in caplog.text


# ---------------------------------------------------------------------------
# Malformed responses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    'body',
    [
        b'<html>gateway error</html>',
        b'\xff\xfe',
        b'[]',
        b'{"retMsg": "OK"}',
        b'{"retCode": "0", "result": {}}',
        b'{"retCode": true, "result": {}}',
    ],
)
def test_malformed_envelopes_raise_and_are_not_retried(body):
    client, transport, sleeps = make_client(HttpResponse(200, body))

    with pytest.raises(BybitMalformedResponseError):
        client.get_server_time()
    assert len(transport.calls) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    'result',
    [
        None,
        {'list': 'not-a-list'},
        {'list': [{'symbol': 'BTCUSDT', 'lastPrice': 'abc'}]},
        {'list': [{'symbol': 'BTCUSDT', 'lastPrice': 'NaN'}]},
        {'list': [{'symbol': 'BTCUSDT', 'lastPrice': '0'}]},
        {'list': [{'symbol': 'BTCUSDT'}]},
        {'list': [{'lastPrice': '100'}]},
        {'list': [{'symbol': 'BTCUSDT', 'lastPrice': '100', 'bid1Price': '101', 'ask1Price': '100'}]},
        {'list': [{'symbol': 'ETHUSDT', 'lastPrice': '100'}]},
    ],
)
def test_malformed_ticker_payloads_raise(result):
    client, _, _ = make_client(ok(result))

    with pytest.raises(BybitMalformedResponseError):
        client.get_tickers('BTCUSDT')


@pytest.mark.parametrize(
    'row',
    [
        ['1700000000000', '10', '9', '8', '9', '1', '10'],  # high < open
        ['1700000000000', '10', '11', '10.5', '10', '1', '10'],  # low > close
        ['1700000000000', '10', '11', '9', '10', '-1', '10'],  # negative volume
        ['1700000000000', '10', '11', '9'],  # too short
        'not-a-row',
        ['abc', '10', '11', '9', '10', '1', '10'],
    ],
)
def test_malformed_klines_raise(row):
    client, _, _ = make_client(ok({'list': [row]}))

    with pytest.raises(BybitMalformedResponseError):
        client.get_klines('BTCUSDT')


def test_duplicate_kline_starts_raise():
    row = ['1700000000000', '10', '11', '9', '10', '1', '10']
    client, _, _ = make_client(ok({'list': [row, row]}))

    with pytest.raises(BybitMalformedResponseError, match='duplicate'):
        client.get_klines('BTCUSDT')


@pytest.mark.parametrize(
    'result',
    [
        {'s': 'ETHUSDT', 'b': [], 'a': [], 'ts': 1},
        {'s': 'BTCUSDT', 'b': [['101', '1']], 'a': [['100', '1']], 'ts': 1},
        {'s': 'BTCUSDT', 'b': [['99', '1'], ['100', '1']], 'a': [], 'ts': 1},
        {'s': 'BTCUSDT', 'b': [['100']], 'a': [], 'ts': 1},
        {'s': 'BTCUSDT', 'b': [], 'a': [], 'ts': None},
    ],
)
def test_malformed_orderbook_raises(result):
    client, _, _ = make_client(ok(result))

    with pytest.raises(BybitMalformedResponseError):
        client.get_orderbook('BTCUSDT')


@pytest.mark.parametrize(
    'account',
    [
        {'accountType': 'UNIFIED', 'coin': 'USDT'},
        {'accountType': 'UNIFIED', 'coin': [{'coin': 'USDT'}]},
        {'accountType': 'UNIFIED', 'coin': [{'coin': 'USDT', 'walletBalance': 'inf'}]},
        {'coin': []},
    ],
)
def test_malformed_wallet_balance_raises(account):
    client, _, _ = make_client(ok({'list': [account]}))

    with pytest.raises(BybitMalformedResponseError):
        client.get_wallet_balance()


@pytest.mark.parametrize(
    'position',
    [
        {'symbol': 'BTCUSDT', 'side': 'Long', 'size': '1'},
        {'symbol': 'BTCUSDT', 'side': 'Buy', 'size': '-1'},
        {'symbol': 'BTCUSDT', 'side': 'Buy'},
    ],
)
def test_malformed_positions_raise(position):
    client, _, _ = make_client(ok({'list': [position], 'nextPageCursor': ''}))

    with pytest.raises(BybitMalformedResponseError):
        client.get_positions()


# ---------------------------------------------------------------------------
# Happy-path normalization
# ---------------------------------------------------------------------------


def test_tickers_normalized_with_source_and_available_at():
    ticker = {
        'symbol': 'BTCUSDT',
        'lastPrice': '65000.5',
        'bid1Price': '65000',
        'ask1Price': '65001',
        'markPrice': '65000.2',
        'indexPrice': '64999.9',
        'volume24h': '1234.5',
        'turnover24h': '80000000',
        'fundingRate': '0.0001',
    }
    client, transport, _ = make_client(ok({'category': 'linear', 'list': [ticker]}))

    [row] = client.get_tickers('btcusdt')

    assert dict(parse_qsl(urlsplit(transport.calls[0]['url']).query)) == {'category': 'linear', 'symbol': 'BTCUSDT'}
    assert row == {
        'source': 'bybit_testnet',
        'symbol': 'BTCUSDT',
        'timestamp_ms': NOW_MS,
        'available_at_ms': NOW_MS,
        'last_price': 65000.5,
        'bid_price': 65000.0,
        'ask_price': 65001.0,
        'mark_price': 65000.2,
        'index_price': 64999.9,
        'volume_24h': 1234.5,
        'turnover_24h': 80000000.0,
        'funding_rate': 0.0001,
    }


def test_klines_sorted_ascending_and_open_bar_not_available():
    closed_start = NOW_MS - 120_000
    open_start = NOW_MS - 30_000
    rows = [
        [str(open_start), '101', '103', '100', '102', '5', '510'],
        [str(closed_start), '100', '102', '99', '101', '4', '404'],
    ]
    client, _, _ = make_client(ok({'symbol': 'BTCUSDT', 'category': 'linear', 'list': rows}))

    klines = client.get_klines('BTCUSDT', interval='1', limit=2)

    assert [k['start_ms'] for k in klines] == [closed_start, open_start]
    assert klines[0]['confirmed'] is True
    assert klines[0]['available_at_ms'] == closed_start + 60_000
    assert klines[0]['end_ms'] == closed_start + 59_999
    assert klines[1]['confirmed'] is False
    assert klines[1]['available_at_ms'] is None


def test_kline_argument_validation():
    client, transport, _ = make_client()

    with pytest.raises(ValueError):
        client.get_klines('BTCUSDT', interval='7')
    with pytest.raises(ValueError):
        client.get_klines('BTCUSDT', limit=5000)
    assert transport.calls == []


def test_orderbook_normalized():
    client, _, _ = make_client(ok({'s': 'BTCUSDT', 'b': [['100', '2'], ['99', '1']], 'a': [['101', '3']], 'ts': 123, 'u': 7, 'seq': 99}))

    book = client.get_orderbook('BTCUSDT', limit=2)

    assert book['bids'] == [(100.0, 2.0), (99.0, 1.0)]
    assert book['asks'] == [(101.0, 3.0)]
    assert book['timestamp_ms'] == 123
    assert book['available_at_ms'] == NOW_MS
    assert (book['update_id'], book['sequence']) == (7, 99)


def test_wallet_balance_normalized_with_empty_optional_fields():
    account = {
        'accountType': 'UNIFIED',
        'totalEquity': '10000.5',
        'totalWalletBalance': '10000',
        'totalAvailableBalance': '',
        'coin': [{'coin': 'USDT', 'walletBalance': '10000', 'equity': '10000.5', 'usdValue': '10000.4', 'unrealisedPnl': '0.5', 'locked': ''}],
    }
    client, _, _ = make_client(ok({'list': [account]}))

    [row] = client.get_wallet_balance()

    assert row['source'] == 'bybit_testnet'
    assert row['total_available_balance'] is None
    assert row['coins'] == [{'coin': 'USDT', 'wallet_balance': 10000.0, 'equity': 10000.5, 'usd_value': 10000.4, 'unrealised_pnl': 0.5, 'locked': None}]


def test_positions_default_to_usdt_settle_and_follow_bounded_pagination():
    page1 = ok({'list': [{'symbol': 'BTCUSDT', 'side': 'Buy', 'size': '0.01', 'avgPrice': '65000', 'leverage': '2', 'positionIdx': 0, 'updatedTime': '1700000000000'}], 'nextPageCursor': 'c1'})
    page2 = ok({'list': [{'symbol': 'ETHUSDT', 'side': '', 'size': '0'}], 'nextPageCursor': ''})
    client, transport, _ = make_client(page1, page2)

    positions = client.get_positions()

    first_query = dict(parse_qsl(urlsplit(transport.calls[0]['url']).query))
    second_query = dict(parse_qsl(urlsplit(transport.calls[1]['url']).query))
    assert first_query == {'category': 'linear', 'limit': '200', 'settleCoin': 'USDT'}
    assert second_query['cursor'] == 'c1'
    assert [p['symbol'] for p in positions] == ['BTCUSDT', 'ETHUSDT']
    assert positions[0]['side'] == 'Buy' and positions[0]['size'] == 0.01 and positions[0]['leverage'] == 2.0
    assert positions[1]['side'] == 'None'


def test_positions_pagination_cap_fails_closed():
    page = ok({'list': [], 'nextPageCursor': 'again'})
    client, transport, _ = make_client(page, page)

    with pytest.raises(BybitApiError, match='max_pages'):
        client.get_positions(max_pages=2)
    assert len(transport.calls) == 2


def test_inverse_positions_require_symbol():
    client, transport, _ = make_client(env={'BYBIT_CATEGORY': 'inverse'})

    with pytest.raises(ValueError):
        client.get_positions()
    assert transport.calls == []


def test_account_info_normalized():
    client, _, _ = make_client(ok({'unifiedMarginStatus': 4, 'marginMode': 'REGULAR_MARGIN'}))

    info = client.get_account_info()

    assert info == {'source': 'bybit_testnet', 'available_at_ms': NOW_MS, 'unified_margin_status': 4, 'margin_mode': 'REGULAR_MARGIN'}
