"""Bounded Bybit paper-trading connector (testnet / demo only).

Scope
-----
- Public market reads (server time, tickers, klines, orderbook).
- Authenticated READ-ONLY account reads (account info, wallet balance, positions).
- No live trading, no withdrawals, no transfers, no automatic order execution.
- ``BYBIT_TRADING_ENABLED`` is false by default. The only order interface is
  ``DisabledPaperOrderGateway``, which fails closed on every call and never
  touches the network, regardless of that flag.

Environment variables
---------------------
BYBIT_API_KEY          required for authenticated reads
BYBIT_API_SECRET       required for authenticated reads
BYBIT_ENV              'testnet' (default) or 'demo'; anything else is rejected
BYBIT_CATEGORY         'linear' (default), 'inverse', 'spot' or 'option'
BYBIT_TRADING_ENABLED  'false' (default); a true value still cannot place orders

Secret handling: credential values are never logged, printed, included in
``repr()`` or in exception messages. Only whether they are set is exposed.

Data-quality conventions (matching ``trading_hub.data``): every normalized
record carries ``source`` and ``available_at_ms`` (local receipt time, or bar
close time for klines), numeric fields are parsed strictly and must be finite,
and malformed payloads raise ``BybitMalformedResponseError`` instead of being
silently skipped.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, NoReturn, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Hard-coded hosts: there is deliberately no way to point this connector at mainnet.
BYBIT_PAPER_BASE_URLS: Mapping[str, str] = {
    'testnet': 'https://api-testnet.bybit.com',
    'demo': 'https://api-demo.bybit.com',
}
ALLOWED_CATEGORIES = frozenset({'linear', 'inverse', 'spot', 'option'})
DEFAULT_ENV = 'testnet'
DEFAULT_CATEGORY = 'linear'
DEFAULT_RECV_WINDOW_MS = 5000

# Hard default. Changing the env var does not unlock order placement: no
# order endpoint is implemented in this module.
BYBIT_TRADING_ENABLED_DEFAULT = False

PUBLIC_READ_PATHS = frozenset(
    {
        '/v5/market/time',
        '/v5/market/tickers',
        '/v5/market/kline',
        '/v5/market/orderbook',
    }
)
AUTHENTICATED_READ_PATHS = frozenset(
    {
        '/v5/account/info',
        '/v5/account/wallet-balance',
        '/v5/position/list',
    }
)

# Bybit retCodes. Auth/permission errors are never retried.
_RETRYABLE_RET_CODES = frozenset({10000, 10006, 10016})  # server timeout, rate limit, server error
_AUTH_RET_CODES = frozenset({10003, 10004, 10005, 10007, 10009, 10010, 33004})
_RETRYABLE_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})

_TRUE_VALUES = frozenset({'1', 'true', 'yes', 'on'})
_FALSE_VALUES = frozenset({'', '0', 'false', 'no', 'off'})

_KLINE_INTERVAL_MS: Mapping[str, int] = {
    '1': 60_000,
    '3': 180_000,
    '5': 300_000,
    '15': 900_000,
    '30': 1_800_000,
    '60': 3_600_000,
    '120': 7_200_000,
    '240': 14_400_000,
    '360': 21_600_000,
    '720': 43_200_000,
    'D': 86_400_000,
    'W': 604_800_000,
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BybitConnectorError(RuntimeError):
    """Base error for the paper connector. Messages never contain credentials."""


class BybitConfigError(BybitConnectorError):
    """Invalid or unsafe configuration (e.g. non-paper environment)."""


class BybitAuthError(BybitConnectorError):
    """Missing credentials or Bybit rejected the signature / key."""


class BybitApiError(BybitConnectorError):
    """Bybit returned a non-zero retCode or a non-retryable HTTP error."""

    def __init__(self, message: str, *, ret_code: int | None = None, http_status: int | None = None) -> None:
        super().__init__(message)
        self.ret_code = ret_code
        self.http_status = http_status


class BybitTransportError(BybitConnectorError):
    """Timeout / network failure after all retries were exhausted."""


class BybitMalformedResponseError(BybitConnectorError):
    """Response body is not valid JSON or does not match the expected shape."""


class TradingDisabledError(BybitConnectorError):
    """Raised by every order-related call. Order execution is not implemented."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class _Secret:
    """Holds a credential without ever exposing it via repr/str/format."""

    __slots__ = ('_value',)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return '<redacted>'

    __str__ = __repr__

    def __format__(self, format_spec: str) -> str:
        return '<redacted>'

    def __bool__(self) -> bool:
        return bool(self._value)


@dataclass(frozen=True)
class BybitPaperConfig:
    env: str = DEFAULT_ENV
    category: str = DEFAULT_CATEGORY
    api_key: _Secret | None = field(default=None, repr=False, compare=False)
    api_secret: _Secret | None = field(default=None, repr=False, compare=False)
    trading_enabled: bool = BYBIT_TRADING_ENABLED_DEFAULT
    recv_window_ms: int = DEFAULT_RECV_WINDOW_MS
    timeout_seconds: float = 10.0
    max_retries: int = 2
    backoff_seconds: float = 0.5
    max_backoff_seconds: float = 4.0

    def __post_init__(self) -> None:
        if self.env not in BYBIT_PAPER_BASE_URLS:
            raise BybitConfigError(
                f'BYBIT_ENV={self.env!r} is not allowed; only {sorted(BYBIT_PAPER_BASE_URLS)} are supported (no mainnet)'
            )
        if self.category not in ALLOWED_CATEGORIES:
            raise BybitConfigError(f'BYBIT_CATEGORY={self.category!r} is not one of {sorted(ALLOWED_CATEGORIES)}')
        if self.timeout_seconds <= 0:
            raise BybitConfigError('timeout_seconds must be > 0')
        if not 0 <= self.max_retries <= 5:
            raise BybitConfigError('max_retries must be between 0 and 5')
        if self.recv_window_ms <= 0:
            raise BybitConfigError('recv_window_ms must be > 0')

    @property
    def base_url(self) -> str:
        return BYBIT_PAPER_BASE_URLS[self.env]

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key) and bool(self.api_secret)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None, **overrides: Any) -> 'BybitPaperConfig':
        source = os.environ if environ is None else environ
        api_key = (source.get('BYBIT_API_KEY') or '').strip()
        api_secret = (source.get('BYBIT_API_SECRET') or '').strip()
        values: dict[str, Any] = {
            'env': (source.get('BYBIT_ENV') or DEFAULT_ENV).strip().lower(),
            'category': (source.get('BYBIT_CATEGORY') or DEFAULT_CATEGORY).strip().lower(),
            'api_key': _Secret(api_key) if api_key else None,
            'api_secret': _Secret(api_secret) if api_secret else None,
            'trading_enabled': _parse_bool_flag(source.get('BYBIT_TRADING_ENABLED'), 'BYBIT_TRADING_ENABLED'),
        }
        values.update(overrides)
        return cls(**values)


def _parse_bool_flag(raw: str | None, name: str) -> bool:
    value = (raw or '').strip().lower()
    if value in _FALSE_VALUES:
        return False
    if value in _TRUE_VALUES:
        return True
    raise BybitConfigError(f'{name} must be a boolean flag (true/false)')


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


def sign_request(*, api_key: str, api_secret: str, timestamp_ms: int, recv_window_ms: int, payload: str) -> str:
    """Bybit V5 HMAC-SHA256 signature: hex(HMAC(secret, ts + key + recv_window + payload)).

    For GET requests ``payload`` is the exact query string sent on the wire.
    """
    message = f'{timestamp_ms}{api_key}{recv_window_ms}{payload}'
    return hmac.new(api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()


def build_auth_headers(config: BybitPaperConfig, *, timestamp_ms: int, query_string: str) -> dict[str, str]:
    if not config.has_credentials:
        raise BybitAuthError('BYBIT_API_KEY and BYBIT_API_SECRET must be set for authenticated reads')
    assert config.api_key is not None and config.api_secret is not None
    signature = sign_request(
        api_key=config.api_key.reveal(),
        api_secret=config.api_secret.reveal(),
        timestamp_ms=timestamp_ms,
        recv_window_ms=config.recv_window_ms,
        payload=query_string,
    )
    return {
        'X-BAPI-API-KEY': config.api_key.reveal(),
        'X-BAPI-TIMESTAMP': str(timestamp_ms),
        'X-BAPI-RECV-WINDOW': str(config.recv_window_ms),
        'X-BAPI-SIGN': signature,
        'X-BAPI-SIGN-TYPE': '2',
    }


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


# (method, url, headers, timeout_seconds) -> HttpResponse.
# Must raise TimeoutError / URLError / OSError on network failure.
HttpTransport = Callable[[str, str, Mapping[str, str], float], HttpResponse]


def urllib_transport(method: str, url: str, headers: Mapping[str, str], timeout_seconds: float) -> HttpResponse:
    request = Request(url, method=method, headers={'User-Agent': 'markov-strategy-bybit-paper-connector/0.1', **headers})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed Bybit paper hosts only
            return HttpResponse(status=response.status, body=response.read())
    except HTTPError as exc:
        return HttpResponse(status=exc.code, body=exc.read() or b'')


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class BybitPaperClient:
    """Read-only Bybit testnet/demo client. Exposes GET requests to allowlisted paths only."""

    def __init__(
        self,
        config: BybitPaperConfig | None = None,
        *,
        transport: HttpTransport | None = None,
        clock_ms: Callable[[], int] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.config = config or BybitPaperConfig.from_env()
        self._transport = transport or urllib_transport
        self._clock_ms = clock_ms or _now_ms
        self._sleep = sleep or time.sleep

    @property
    def source(self) -> str:
        return f'bybit_{self.config.env}'

    # --- public market reads ------------------------------------------------

    def get_server_time(self) -> dict[str, Any]:
        response = self._get('/v5/market/time', {}, authenticated=False)
        result = _require_mapping(response.get('result'), 'result')
        return {
            'source': self.source,
            'server_time_ms': _require_int(result.get('timeNano'), 'timeNano') // 1_000_000,
            'available_at_ms': self._clock_ms(),
        }

    def get_tickers(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {'category': self.config.category}
        if symbol:
            params['symbol'] = symbol.upper()
        response = self._get('/v5/market/tickers', params, authenticated=False)
        received_ms = self._clock_ms()
        result = _require_mapping(response.get('result'), 'result')
        timestamp_ms = _optional_int(response.get('time'), 'time') or received_ms
        rows = [
            normalize_ticker(item, timestamp_ms=timestamp_ms, available_at_ms=received_ms, source=self.source)
            for item in _require_list(result.get('list'), 'result.list')
        ]
        if symbol and any(row['symbol'] != symbol.upper() for row in rows):
            raise BybitMalformedResponseError(f'ticker response contains symbols other than {symbol.upper()}')
        return rows

    def get_klines(self, symbol: str, *, interval: str = '1', limit: int = 200) -> list[dict[str, Any]]:
        if interval not in _KLINE_INTERVAL_MS:
            raise ValueError(f'unsupported kline interval {interval!r}')
        if not 1 <= limit <= 1000:
            raise ValueError('limit must be between 1 and 1000')
        params = {'category': self.config.category, 'symbol': symbol.upper(), 'interval': interval, 'limit': limit}
        response = self._get('/v5/market/kline', params, authenticated=False)
        received_ms = self._clock_ms()
        result = _require_mapping(response.get('result'), 'result')
        rows = [
            normalize_kline_row(row, symbol=symbol.upper(), interval=interval, received_ms=received_ms, source=self.source)
            for row in _require_list(result.get('list'), 'result.list')
        ]
        rows.sort(key=lambda row: row['start_ms'])  # Bybit returns newest first
        starts = [row['start_ms'] for row in rows]
        if len(set(starts)) != len(starts):
            raise BybitMalformedResponseError('kline response contains duplicate start times')
        return rows

    def get_orderbook(self, symbol: str, *, limit: int = 50) -> dict[str, Any]:
        params = {'category': self.config.category, 'symbol': symbol.upper(), 'limit': limit}
        response = self._get('/v5/market/orderbook', params, authenticated=False)
        received_ms = self._clock_ms()
        result = _require_mapping(response.get('result'), 'result')
        return normalize_orderbook(result, symbol=symbol.upper(), available_at_ms=received_ms, source=self.source)

    # --- authenticated read-only account reads ------------------------------

    def get_account_info(self) -> dict[str, Any]:
        response = self._get('/v5/account/info', {}, authenticated=True)
        result = _require_mapping(response.get('result'), 'result')
        return {
            'source': self.source,
            'available_at_ms': self._clock_ms(),
            'unified_margin_status': _optional_int(result.get('unifiedMarginStatus'), 'unifiedMarginStatus'),
            'margin_mode': _optional_str(result.get('marginMode')),
        }

    def get_wallet_balance(self, *, account_type: str = 'UNIFIED', coin: str | None = None) -> list[dict[str, Any]]:
        params = {'accountType': account_type}
        if coin:
            params['coin'] = coin.upper()
        response = self._get('/v5/account/wallet-balance', params, authenticated=True)
        received_ms = self._clock_ms()
        result = _require_mapping(response.get('result'), 'result')
        return [
            normalize_wallet_account(item, available_at_ms=received_ms, source=self.source)
            for item in _require_list(result.get('list'), 'result.list')
        ]

    def get_positions(
        self,
        *,
        symbol: str | None = None,
        settle_coin: str | None = None,
        limit: int = 200,
        max_pages: int = 5,
    ) -> list[dict[str, Any]]:
        # Bybit requires symbol or settleCoin for linear; inverse needs a symbol.
        if not symbol and not settle_coin:
            if self.config.category == 'linear':
                settle_coin = 'USDT'
            elif self.config.category == 'inverse':
                raise ValueError('symbol is required for inverse position reads')
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(max_pages):
            params: dict[str, Any] = {'category': self.config.category, 'limit': limit}
            if symbol:
                params['symbol'] = symbol.upper()
            if settle_coin:
                params['settleCoin'] = settle_coin.upper()
            if cursor:
                params['cursor'] = cursor
            response = self._get('/v5/position/list', params, authenticated=True)
            received_ms = self._clock_ms()
            result = _require_mapping(response.get('result'), 'result')
            rows.extend(
                normalize_position(item, available_at_ms=received_ms, source=self.source)
                for item in _require_list(result.get('list'), 'result.list')
            )
            cursor = _optional_str(result.get('nextPageCursor'))
            if not cursor:
                return rows
        raise BybitApiError(f'position list exceeded max_pages={max_pages}; refusing to return a partial result')

    # --- request core -------------------------------------------------------

    def _get(self, path: str, params: Mapping[str, Any], *, authenticated: bool) -> dict[str, Any]:
        allowed = AUTHENTICATED_READ_PATHS if authenticated else PUBLIC_READ_PATHS
        if path not in allowed:
            raise BybitConfigError(f'path {path!r} is not an allowlisted read-only endpoint')
        if authenticated and not self.config.has_credentials:
            raise BybitAuthError('BYBIT_API_KEY and BYBIT_API_SECRET must be set for authenticated reads')

        query_string = urlencode(sorted((key, str(value)) for key, value in params.items()))
        url = f'{self.config.base_url}{path}' + (f'?{query_string}' if query_string else '')
        attempts = self.config.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            # Re-sign every attempt so the timestamp stays inside recv_window.
            headers = (
                build_auth_headers(self.config, timestamp_ms=self._clock_ms(), query_string=query_string)
                if authenticated
                else {}
            )
            try:
                response = self._transport('GET', url, headers, self.config.timeout_seconds)
            except (TimeoutError, URLError, OSError) as exc:
                last_error = BybitTransportError(f'GET {path} failed: {type(exc).__name__}')
            else:
                try:
                    return self._parse(path, response)
                except _Retryable as exc:
                    last_error = exc.error
            if attempt < attempts:
                delay = min(self.config.backoff_seconds * (2 ** (attempt - 1)), self.config.max_backoff_seconds)
                logger.warning('bybit %s GET %s attempt %d/%d failed (%s); retrying in %.2fs', self.config.env, path, attempt, attempts, last_error, delay)
                self._sleep(delay)

        assert last_error is not None
        if isinstance(last_error, BybitTransportError):
            raise BybitTransportError(f'{last_error} after {attempts} attempt(s)') from None
        raise last_error

    def _parse(self, path: str, response: HttpResponse) -> dict[str, Any]:
        if response.status in _RETRYABLE_HTTP_STATUS:
            raise _Retryable(BybitApiError(f'GET {path} returned HTTP {response.status}', http_status=response.status))
        if response.status in (401, 403):
            raise BybitAuthError(f'GET {path} rejected with HTTP {response.status}')
        if response.status != 200:
            raise BybitApiError(f'GET {path} returned HTTP {response.status}', http_status=response.status)
        try:
            payload = json.loads(response.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BybitMalformedResponseError(f'GET {path} returned non-JSON body') from exc
        if not isinstance(payload, dict):
            raise BybitMalformedResponseError(f'GET {path} returned {type(payload).__name__}, expected object')
        ret_code = payload.get('retCode')
        if isinstance(ret_code, bool) or not isinstance(ret_code, int):
            raise BybitMalformedResponseError(f'GET {path} response missing integer retCode')
        if ret_code == 0:
            return payload
        message = f'GET {path} failed: retCode={ret_code} retMsg={_safe_msg(payload.get("retMsg"))}'
        if ret_code in _AUTH_RET_CODES:
            raise BybitAuthError(message)
        if ret_code in _RETRYABLE_RET_CODES:
            raise _Retryable(BybitApiError(message, ret_code=ret_code, http_status=response.status))
        raise BybitApiError(message, ret_code=ret_code, http_status=response.status)


class _Retryable(Exception):
    def __init__(self, error: BybitConnectorError) -> None:
        super().__init__(str(error))
        self.error = error


# ---------------------------------------------------------------------------
# Disabled paper-order interface (fail-closed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PaperOrderRequest:
    """Shape reserved for future paper-order work. Nothing consumes it yet."""

    symbol: str
    side: str
    qty: float
    order_type: str = 'Market'
    price: float | None = None
    reduce_only: bool = False


class PaperOrderGateway(Protocol):
    def submit_order(self, order: PaperOrderRequest) -> NoReturn: ...

    def cancel_order(self, symbol: str, order_id: str) -> NoReturn: ...


class DisabledPaperOrderGateway:
    """Fail-closed order gateway. Every call raises; no network I/O is ever performed.

    Even with BYBIT_TRADING_ENABLED=true this gateway refuses: order execution
    is intentionally not implemented in this connector.
    """

    def __init__(self, config: BybitPaperConfig | None = None) -> None:
        self.config = config or BybitPaperConfig()

    @property
    def trading_enabled(self) -> bool:
        return False

    def submit_order(self, order: PaperOrderRequest) -> NoReturn:
        self._refuse('submit_order')

    def cancel_order(self, symbol: str, order_id: str) -> NoReturn:
        self._refuse('cancel_order')

    def _refuse(self, action: str) -> NoReturn:
        if not self.config.trading_enabled:
            raise TradingDisabledError(f'{action} refused: BYBIT_TRADING_ENABLED is false')
        raise TradingDisabledError(f'{action} refused: order execution is not implemented in the paper connector')


# ---------------------------------------------------------------------------
# Normalizers (strict; raise BybitMalformedResponseError on bad data)
# ---------------------------------------------------------------------------


def normalize_ticker(item: Any, *, timestamp_ms: int, available_at_ms: int, source: str) -> dict[str, Any]:
    item = _require_mapping(item, 'ticker')
    bid = _optional_float(item.get('bid1Price'), 'bid1Price')
    ask = _optional_float(item.get('ask1Price'), 'ask1Price')
    if bid is not None and ask is not None and bid > ask:
        raise BybitMalformedResponseError(f'crossed ticker for {item.get("symbol")}: bid {bid} > ask {ask}')
    return {
        'source': source,
        'symbol': _require_str(item.get('symbol'), 'symbol'),
        'timestamp_ms': timestamp_ms,
        'available_at_ms': available_at_ms,
        'last_price': _require_positive(_require_float(item.get('lastPrice'), 'lastPrice'), 'lastPrice'),
        'bid_price': bid,
        'ask_price': ask,
        'mark_price': _optional_float(item.get('markPrice'), 'markPrice'),
        'index_price': _optional_float(item.get('indexPrice'), 'indexPrice'),
        'volume_24h': _optional_float(item.get('volume24h'), 'volume24h'),
        'turnover_24h': _optional_float(item.get('turnover24h'), 'turnover24h'),
        'funding_rate': _optional_float(item.get('fundingRate'), 'fundingRate'),
    }


def normalize_kline_row(row: Any, *, symbol: str, interval: str, received_ms: int, source: str) -> dict[str, Any]:
    if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 7:
        raise BybitMalformedResponseError('kline row must be a list of 7 fields')
    start_ms = _require_int(row[0], 'kline start')
    open_, high, low, close, volume, turnover = (
        _require_float(row[index], name)
        for index, name in enumerate(('open', 'high', 'low', 'close', 'volume', 'turnover'), start=1)
    )
    if min(open_, high, low, close) <= 0:
        raise BybitMalformedResponseError(f'non-positive kline price at {start_ms}')
    if high < max(open_, close) or low > min(open_, close) or low > high:
        raise BybitMalformedResponseError(f'inconsistent OHLC at {start_ms}')
    if volume < 0 or turnover < 0:
        raise BybitMalformedResponseError(f'negative kline volume/turnover at {start_ms}')
    close_ms = start_ms + _KLINE_INTERVAL_MS[interval]
    confirmed = close_ms <= received_ms
    return {
        'source': source,
        'symbol': symbol,
        'interval': interval,
        'start_ms': start_ms,
        'end_ms': close_ms - 1,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'turnover': turnover,
        'confirmed': confirmed,
        # PIT: a bar is usable only after it closes; an open bar is never "available".
        'available_at_ms': close_ms if confirmed else None,
    }


def normalize_orderbook(result: Mapping[str, Any], *, symbol: str, available_at_ms: int, source: str) -> dict[str, Any]:
    if _require_str(result.get('s'), 's') != symbol:
        raise BybitMalformedResponseError(f'orderbook symbol mismatch: expected {symbol}')
    bids = _parse_levels(result.get('b'), 'b')
    asks = _parse_levels(result.get('a'), 'a')
    if bids != sorted(bids, key=lambda level: -level[0]) or asks != sorted(asks):
        raise BybitMalformedResponseError('orderbook levels are not sorted')
    if bids and asks and bids[0][0] >= asks[0][0]:
        raise BybitMalformedResponseError(f'crossed orderbook for {symbol}')
    return {
        'source': source,
        'symbol': symbol,
        'timestamp_ms': _require_int(result.get('ts'), 'ts'),
        'available_at_ms': available_at_ms,
        'update_id': _optional_int(result.get('u'), 'u'),
        'sequence': _optional_int(result.get('seq'), 'seq'),
        'bids': bids,
        'asks': asks,
    }


def normalize_wallet_account(item: Any, *, available_at_ms: int, source: str) -> dict[str, Any]:
    item = _require_mapping(item, 'wallet account')
    coins = []
    for coin in _require_list(item.get('coin'), 'coin'):
        coin = _require_mapping(coin, 'coin')
        coins.append(
            {
                'coin': _require_str(coin.get('coin'), 'coin.coin'),
                'wallet_balance': _require_float(coin.get('walletBalance'), 'walletBalance'),
                'equity': _optional_float(coin.get('equity'), 'equity'),
                'usd_value': _optional_float(coin.get('usdValue'), 'usdValue'),
                'unrealised_pnl': _optional_float(coin.get('unrealisedPnl'), 'unrealisedPnl'),
                'locked': _optional_float(coin.get('locked'), 'locked'),
            }
        )
    return {
        'source': source,
        'available_at_ms': available_at_ms,
        'account_type': _require_str(item.get('accountType'), 'accountType'),
        'total_equity': _optional_float(item.get('totalEquity'), 'totalEquity'),
        'total_wallet_balance': _optional_float(item.get('totalWalletBalance'), 'totalWalletBalance'),
        'total_available_balance': _optional_float(item.get('totalAvailableBalance'), 'totalAvailableBalance'),
        'coins': coins,
    }


def normalize_position(item: Any, *, available_at_ms: int, source: str) -> dict[str, Any]:
    item = _require_mapping(item, 'position')
    side = _optional_str(item.get('side')) or 'None'
    if side not in {'Buy', 'Sell', 'None'}:
        raise BybitMalformedResponseError(f'unexpected position side {side!r}')
    size = _require_float(item.get('size'), 'size')
    if size < 0:
        raise BybitMalformedResponseError('position size must be >= 0')
    return {
        'source': source,
        'available_at_ms': available_at_ms,
        'symbol': _require_str(item.get('symbol'), 'symbol'),
        'side': side,
        'size': size,
        'avg_price': _optional_float(item.get('avgPrice'), 'avgPrice'),
        'mark_price': _optional_float(item.get('markPrice'), 'markPrice'),
        'position_value': _optional_float(item.get('positionValue'), 'positionValue'),
        'unrealised_pnl': _optional_float(item.get('unrealisedPnl'), 'unrealisedPnl'),
        'leverage': _optional_float(item.get('leverage'), 'leverage'),
        'position_idx': _optional_int(item.get('positionIdx'), 'positionIdx'),
        'updated_ms': _optional_int(item.get('updatedTime'), 'updatedTime'),
    }


# ---------------------------------------------------------------------------
# Strict field helpers
# ---------------------------------------------------------------------------


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BybitMalformedResponseError(f'{name} must be an object')
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise BybitMalformedResponseError(f'{name} must be a list')
    return value


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise BybitMalformedResponseError(f'{name} must be a non-empty string')
    return value


def _optional_str(value: Any) -> str | None:
    if value is None or value == '':
        return None
    return str(value)


def _require_float(value: Any, name: str) -> float:
    parsed = _optional_float(value, name)
    if parsed is None:
        raise BybitMalformedResponseError(f'missing numeric field {name}')
    return parsed


def _optional_float(value: Any, name: str) -> float | None:
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise BybitMalformedResponseError(f'{name} must be numeric')
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BybitMalformedResponseError(f'{name} is not numeric') from exc
    if not math.isfinite(parsed):
        raise BybitMalformedResponseError(f'{name} is not finite')
    return parsed


def _require_positive(value: float, name: str) -> float:
    if value <= 0:
        raise BybitMalformedResponseError(f'{name} must be > 0')
    return value


def _require_int(value: Any, name: str) -> int:
    parsed = _optional_int(value, name)
    if parsed is None:
        raise BybitMalformedResponseError(f'missing integer field {name}')
    return parsed


def _optional_int(value: Any, name: str) -> int | None:
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise BybitMalformedResponseError(f'{name} must be an integer')
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise BybitMalformedResponseError(f'{name} is not an integer') from exc


def _parse_levels(value: Any, name: str) -> list[tuple[float, float]]:
    levels = []
    for level in _require_list(value, name):
        if not isinstance(level, list) or len(level) < 2:
            raise BybitMalformedResponseError(f'{name} level must be [price, size]')
        price = _require_positive(_require_float(level[0], f'{name} price'), f'{name} price')
        size = _require_float(level[1], f'{name} size')
        if size < 0:
            raise BybitMalformedResponseError(f'{name} size must be >= 0')
        levels.append((price, size))
    return levels


def _safe_msg(value: Any) -> str:
    return str(value)[:200] if value is not None else ''


def _now_ms() -> int:
    return int(time.time() * 1000)
