from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BYBIT_PUBLIC_LINEAR_WS_URL = 'wss://stream.bybit.com/v5/public/linear'
BYBIT_PUBLIC_REST_BASE_URL = 'https://api.bybit.com'
DEFAULT_SYMBOLS = ('BTCUSDT', 'ETHUSDT')


@dataclass(frozen=True)
class BybitPublicCollectorConfig:
    data_dir: Path | str
    symbols: Sequence[str] = DEFAULT_SYMBOLS
    category: str = 'linear'
    orderbook_depth: int = 50
    kline_interval: str = '1'
    websocket_url: str = BYBIT_PUBLIC_LINEAR_WS_URL
    reconnect_delay_seconds: float = 2.0
    max_reconnect_delay_seconds: float = 60.0

    def normalized_symbols(self) -> tuple[str, ...]:
        symbols = tuple(symbol.upper() for symbol in self.symbols)
        if not symbols:
            raise ValueError('at least one symbol is required')
        return symbols


@dataclass(frozen=True)
class ProcessResult:
    processed: bool = False
    ignored: bool = False
    topic: str | None = None
    symbol: str | None = None
    gap_detected: bool = False
    resync_performed: bool = False


@dataclass
class OrderBookState:
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    update_id: int | None = None
    sequence: int | None = None

    def apply_snapshot(self, bids: Iterable[Sequence[str]], asks: Iterable[Sequence[str]], update_id: int | None, sequence: int | None) -> None:
        self.bids = _levels_to_book(bids)
        self.asks = _levels_to_book(asks)
        self.update_id = update_id
        self.sequence = sequence

    def apply_delta(self, bids: Iterable[Sequence[str]], asks: Iterable[Sequence[str]], update_id: int | None, sequence: int | None) -> None:
        _apply_level_deltas(self.bids, bids)
        _apply_level_deltas(self.asks, asks)
        self.update_id = update_id
        self.sequence = sequence

    def best_bid(self) -> tuple[float, float] | None:
        if not self.bids:
            return None
        price = max(self.bids)
        return price, self.bids[price]

    def best_ask(self) -> tuple[float, float] | None:
        if not self.asks:
            return None
        price = min(self.asks)
        return price, self.asks[price]


class RestClientProtocol(Protocol):
    def fetch_orderbook_snapshot(self, symbol: str, limit: int = 50) -> dict[str, Any]: ...


class BybitPublicRestClient:
    def __init__(
        self,
        *,
        base_url: str = BYBIT_PUBLIC_REST_BASE_URL,
        category: str = 'linear',
        timeout_seconds: float = 10.0,
        http_get_json: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.category = category
        self.timeout_seconds = timeout_seconds
        self._http_get_json = http_get_json or self._default_http_get_json

    def fetch_orderbook_snapshot(self, symbol: str, limit: int = 50) -> dict[str, Any]:
        query = urlencode({'category': self.category, 'symbol': symbol.upper(), 'limit': int(limit)})
        url = f'{self.base_url}/v5/market/orderbook?{query}'
        response = self._http_get_json(url)
        ret_code = response.get('retCode')
        if ret_code != 0:
            raise RuntimeError(f'Bybit orderbook snapshot failed for {symbol}: retCode={ret_code} retMsg={response.get("retMsg")}')
        result = response.get('result')
        if not isinstance(result, Mapping):
            raise RuntimeError(f'Bybit orderbook snapshot response missing result for {symbol}')
        ts = result.get('ts') or response.get('time') or _now_ms()
        return {
            'topic': f'orderbook.{limit}.{symbol.upper()}',
            'type': 'snapshot',
            'ts': ts,
            'data': dict(result),
        }

    def _default_http_get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={'User-Agent': 'markov-strategy-bybit-public-collector/0.1'})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - public Bybit HTTPS endpoint
                payload = response.read().decode('utf-8')
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f'Bybit public REST request failed: {exc}') from exc
        return json.loads(payload)


class BybitPublicCollector:
    def __init__(
        self,
        config: BybitPublicCollectorConfig,
        *,
        rest_client: RestClientProtocol | None = None,
        websocket_connect: Callable[[str], Any] | None = None,
    ) -> None:
        self.config = config
        self.data_dir = Path(config.data_dir)
        self.symbols = set(config.normalized_symbols())
        self.rest_client = rest_client or BybitPublicRestClient(category=config.category)
        self.websocket_connect = websocket_connect
        self.orderbooks: dict[str, OrderBookState] = {symbol: OrderBookState() for symbol in self.symbols}

    def process_message(self, message: str | bytes | Mapping[str, Any], *, raw_already_written: bool = False) -> ProcessResult:
        event = _coerce_event(message)
        topic = event.get('topic')
        if not topic:
            return ProcessResult(ignored=True)
        symbol = _symbol_from_topic(str(topic))
        if symbol is None or symbol not in self.symbols:
            return ProcessResult(ignored=True, topic=str(topic), symbol=symbol)

        if not raw_already_written:
            self._append_jsonl(self._raw_path(symbol), event)

        if str(topic).startswith('publicTrade.'):
            self._process_trade_event(symbol, event)
            return ProcessResult(processed=True, topic=str(topic), symbol=symbol)
        if str(topic).startswith(f'kline.{self.config.kline_interval}.'):
            self._process_kline_event(symbol, event)
            return ProcessResult(processed=True, topic=str(topic), symbol=symbol)
        if str(topic).startswith(f'orderbook.{self.config.orderbook_depth}.'):
            return self._process_orderbook_event(symbol, event)
        return ProcessResult(ignored=True, topic=str(topic), symbol=symbol)

    async def collect_once(self, *, max_messages: int | None = None) -> int:
        connect = self.websocket_connect or _load_websockets_connect()
        processed = 0
        async with connect(self.config.websocket_url) as websocket:
            await websocket.send(json.dumps({'op': 'subscribe', 'args': build_bybit_public_subscribe_args(self.config.normalized_symbols())}))
            async for raw_message in websocket:
                result = self.process_message(raw_message)
                processed += 1
                if max_messages is not None and processed >= max_messages:
                    break
                if result.ignored and _is_subscription_ack(raw_message):
                    continue
        return processed

    async def run_forever(self) -> None:
        delay = self.config.reconnect_delay_seconds
        while True:
            try:
                await self.collect_once()
                delay = self.config.reconnect_delay_seconds
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - live reconnect loop
                self._append_jsonl(self.data_dir / 'status' / 'errors.jsonl', {'timestamp_ms': _now_ms(), 'error': repr(exc)})
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.config.max_reconnect_delay_seconds)

    def _process_trade_event(self, symbol: str, event: Mapping[str, Any]) -> None:
        for trade in _as_list(event.get('data')):
            row = normalize_trade(symbol, trade)
            self._append_jsonl(self.data_dir / 'normalized' / 'trades' / f'{symbol}.jsonl', row)

    def _process_kline_event(self, symbol: str, event: Mapping[str, Any]) -> None:
        for kline in _as_list(event.get('data')):
            row = normalize_kline(symbol, kline)
            self._append_jsonl(self.data_dir / 'normalized' / 'ohlcv_1m' / f'{symbol}.jsonl', row)

    def _process_orderbook_event(self, symbol: str, event: Mapping[str, Any]) -> ProcessResult:
        data = event.get('data')
        if not isinstance(data, Mapping):
            return ProcessResult(ignored=True, topic=str(event.get('topic')), symbol=symbol)

        state = self.orderbooks.setdefault(symbol, OrderBookState())
        event_type = str(event.get('type') or 'snapshot')
        update_id = _optional_int(data.get('u'))
        sequence = _optional_int(data.get('seq'))
        gap_detected = _has_orderbook_gap(state, event_type=event_type, update_id=update_id, sequence=sequence)
        if gap_detected:
            snapshot = self.rest_client.fetch_orderbook_snapshot(symbol, limit=self.config.orderbook_depth)
            self._append_jsonl(self._raw_path(symbol), snapshot)
            self._process_orderbook_event(symbol, snapshot)
            return ProcessResult(
                processed=True,
                topic=str(event.get('topic')),
                symbol=symbol,
                gap_detected=True,
                resync_performed=True,
            )

        bids = data.get('b') or []
        asks = data.get('a') or []
        if event_type == 'snapshot' or state.update_id is None:
            state.apply_snapshot(bids, asks, update_id, sequence)
        else:
            if update_id is not None and state.update_id is not None and update_id <= state.update_id:
                return ProcessResult(ignored=True, topic=str(event.get('topic')), symbol=symbol)
            state.apply_delta(bids, asks, update_id, sequence)

        spread = self._spread_row(symbol, event, state)
        if spread is not None:
            self._append_jsonl(self.data_dir / 'normalized' / 'best_bid_ask_spread' / f'{symbol}.jsonl', spread)
        return ProcessResult(processed=True, topic=str(event.get('topic')), symbol=symbol)

    def _spread_row(self, symbol: str, event: Mapping[str, Any], state: OrderBookState) -> dict[str, Any] | None:
        best_bid = state.best_bid()
        best_ask = state.best_ask()
        if best_bid is None or best_ask is None:
            return None
        bid_price, bid_size = best_bid
        ask_price, ask_size = best_ask
        mid = (bid_price + ask_price) / 2.0
        spread = ask_price - bid_price
        return {
            'symbol': symbol,
            'timestamp_ms': _optional_int(event.get('ts')) or _now_ms(),
            'update_id': state.update_id,
            'sequence': state.sequence,
            'bid_price': bid_price,
            'bid_size': bid_size,
            'ask_price': ask_price,
            'ask_size': ask_size,
            'spread': spread,
            'spread_bps': (spread / mid * 10_000.0) if mid else 0.0,
        }

    def _append_jsonl(self, path: Path, record: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n')

    def _raw_path(self, symbol: str) -> Path:
        return self.data_dir / 'raw' / f'{symbol}.jsonl'


def build_bybit_public_subscribe_args(symbols: Sequence[str], *, kline_interval: str = '1', orderbook_depth: int = 50) -> list[str]:
    args: list[str] = []
    for symbol in symbols:
        normalized = symbol.upper()
        args.extend(
            [
                f'publicTrade.{normalized}',
                f'kline.{kline_interval}.{normalized}',
                f'orderbook.{orderbook_depth}.{normalized}',
            ]
        )
    return args


def normalize_trade(symbol: str, trade: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'symbol': symbol,
        'trade_id': str(trade.get('i') or trade.get('tradeId') or ''),
        'timestamp_ms': int(trade.get('T') or trade.get('timestamp') or 0),
        'side': str(trade.get('S') or trade.get('side') or ''),
        'price': _required_float(trade.get('p') or trade.get('price'), 'trade price'),
        'size': _required_float(trade.get('v') or trade.get('size'), 'trade size'),
        'block_trade': bool(trade.get('BT', False)),
    }


def normalize_kline(symbol: str, kline: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'symbol': symbol,
        'start_ms': int(kline.get('start') or 0),
        'end_ms': int(kline.get('end') or 0),
        'interval': str(kline.get('interval') or '1'),
        'open': _required_float(kline.get('open'), 'kline open'),
        'high': _required_float(kline.get('high'), 'kline high'),
        'low': _required_float(kline.get('low'), 'kline low'),
        'close': _required_float(kline.get('close'), 'kline close'),
        'volume': _required_float(kline.get('volume'), 'kline volume'),
        'turnover': _required_float(kline.get('turnover'), 'kline turnover'),
        'confirmed': bool(kline.get('confirm', False)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = BybitPublicCollectorConfig(
        data_dir=args.data_dir,
        symbols=tuple(args.symbol or DEFAULT_SYMBOLS),
        orderbook_depth=args.orderbook_depth,
        kline_interval=args.kline_interval,
    )
    collector = BybitPublicCollector(config)
    asyncio.run(collector.run_forever())
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Research-only Bybit public market data collector; no API keys are used.')
    parser.add_argument('--data-dir', default='data/bybit_public', help='Directory for raw and normalized JSONL output')
    parser.add_argument('--symbol', action='append', default=None, help='Linear symbol to collect; repeatable')
    parser.add_argument('--orderbook-depth', type=int, default=50)
    parser.add_argument('--kline-interval', default='1')
    return parser


def _coerce_event(message: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(message, Mapping):
        return dict(message)
    if isinstance(message, bytes):
        message = message.decode('utf-8')
    return json.loads(message)


def _symbol_from_topic(topic: str) -> str | None:
    parts = topic.split('.')
    if len(parts) < 2:
        return None
    return parts[-1].upper()


def _as_list(value: Any) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [value]
    return [item for item in value if isinstance(item, Mapping)]


def _levels_to_book(levels: Iterable[Sequence[str]]) -> dict[float, float]:
    book: dict[float, float] = {}
    for level in levels:
        price = float(level[0])
        size = float(level[1])
        if size > 0:
            book[price] = size
    return book


def _apply_level_deltas(book: dict[float, float], levels: Iterable[Sequence[str]]) -> None:
    for level in levels:
        price = float(level[0])
        size = float(level[1])
        if size <= 0:
            book.pop(price, None)
        else:
            book[price] = size


def _has_orderbook_gap(
    state: OrderBookState,
    *,
    event_type: str,
    update_id: int | None,
    sequence: int | None,
) -> bool:
    if event_type == 'snapshot' or state.update_id is None:
        return False
    if update_id is not None and state.update_id is not None and update_id <= state.update_id:
        return False
    if sequence is not None and state.sequence is not None and sequence > state.sequence + 1:
        return True
    if sequence is None and update_id is not None and state.update_id is not None and update_id > state.update_id + 1:
        return True
    return False


def _optional_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    return int(value)


def _required_float(value: Any, field_name: str) -> float:
    if value is None or value == '':
        raise ValueError(f'missing {field_name}')
    return float(value)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _is_subscription_ack(message: str | bytes | Mapping[str, Any]) -> bool:
    event = _coerce_event(message)
    return event.get('op') == 'subscribe' and 'topic' not in event


def _load_websockets_connect() -> Callable[[str], Any]:
    try:
        import websockets
    except ImportError as exc:  # pragma: no cover - depends on optional env
        raise RuntimeError('websockets is required for live collection; install project optional/runtime dependencies') from exc
    return websockets.connect


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
