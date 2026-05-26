from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from trading_hub.bybit_public_collector import (
    BybitPublicCollector,
    BybitPublicCollectorConfig,
    BybitPublicRestClient,
    build_bybit_public_subscribe_args,
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def test_subscription_args_include_requested_public_linear_topics():
    args = build_bybit_public_subscribe_args(['BTCUSDT', 'ETHUSDT'])

    assert args == [
        'publicTrade.BTCUSDT',
        'kline.1.BTCUSDT',
        'orderbook.50.BTCUSDT',
        'publicTrade.ETHUSDT',
        'kline.1.ETHUSDT',
        'orderbook.50.ETHUSDT',
    ]


def test_collector_writes_raw_and_normalized_trade_kline_and_spread(tmp_path: Path):
    collector = BybitPublicCollector(BybitPublicCollectorConfig(data_dir=tmp_path, symbols=['BTCUSDT']))

    collector.process_message(
        {
            'topic': 'publicTrade.BTCUSDT',
            'type': 'snapshot',
            'ts': 1700000000123,
            'data': [
                {
                    'T': 1700000000120,
                    's': 'BTCUSDT',
                    'S': 'Buy',
                    'v': '0.125',
                    'p': '35000.5',
                    'i': 'trade-1',
                    'BT': False,
                }
            ],
        }
    )
    collector.process_message(
        {
            'topic': 'kline.1.BTCUSDT',
            'type': 'snapshot',
            'ts': 1700000060000,
            'data': [
                {
                    'start': 1700000040000,
                    'end': 1700000099999,
                    'interval': '1',
                    'open': '35000',
                    'high': '35010',
                    'low': '34990',
                    'close': '35005',
                    'volume': '12.5',
                    'turnover': '437500',
                    'confirm': True,
                    'timestamp': 1700000060000,
                }
            ],
        }
    )
    collector.process_message(
        {
            'topic': 'orderbook.50.BTCUSDT',
            'type': 'snapshot',
            'ts': 1700000000200,
            'data': {
                's': 'BTCUSDT',
                'b': [['35000.0', '1.5'], ['34999.5', '2.0']],
                'a': [['35001.0', '1.25'], ['35002.0', '1.75']],
                'u': 100,
                'seq': 200,
                'cts': 1700000000190,
            },
        }
    )

    raw = read_jsonl(tmp_path / 'raw' / 'BTCUSDT.jsonl')
    assert [row['topic'] for row in raw] == [
        'publicTrade.BTCUSDT',
        'kline.1.BTCUSDT',
        'orderbook.50.BTCUSDT',
    ]

    trades = read_jsonl(tmp_path / 'normalized' / 'trades' / 'BTCUSDT.jsonl')
    assert trades == [
        {
            'symbol': 'BTCUSDT',
            'trade_id': 'trade-1',
            'timestamp_ms': 1700000000120,
            'side': 'Buy',
            'price': 35000.5,
            'size': 0.125,
            'block_trade': False,
        }
    ]

    ohlcv = read_jsonl(tmp_path / 'normalized' / 'ohlcv_1m' / 'BTCUSDT.jsonl')
    assert ohlcv == [
        {
            'symbol': 'BTCUSDT',
            'start_ms': 1700000040000,
            'end_ms': 1700000099999,
            'interval': '1',
            'open': 35000.0,
            'high': 35010.0,
            'low': 34990.0,
            'close': 35005.0,
            'volume': 12.5,
            'turnover': 437500.0,
            'confirmed': True,
        }
    ]

    spreads = read_jsonl(tmp_path / 'normalized' / 'best_bid_ask_spread' / 'BTCUSDT.jsonl')
    assert spreads == [
        {
            'symbol': 'BTCUSDT',
            'timestamp_ms': 1700000000200,
            'update_id': 100,
            'sequence': 200,
            'bid_price': 35000.0,
            'bid_size': 1.5,
            'ask_price': 35001.0,
            'ask_size': 1.25,
            'spread': 1.0,
            'spread_bps': pytest.approx(0.28571020413994086),
        }
    ]


def test_orderbook_delta_updates_levels_and_removes_zero_size_levels(tmp_path: Path):
    collector = BybitPublicCollector(BybitPublicCollectorConfig(data_dir=tmp_path, symbols=['BTCUSDT']))
    collector.process_message(
        {
            'topic': 'orderbook.50.BTCUSDT',
            'type': 'snapshot',
            'ts': 10,
            'data': {
                's': 'BTCUSDT',
                'b': [['100', '2'], ['99', '3']],
                'a': [['101', '4'], ['102', '5']],
                'u': 1,
                'seq': 10,
            },
        }
    )

    collector.process_message(
        {
            'topic': 'orderbook.50.BTCUSDT',
            'type': 'delta',
            'ts': 20,
            'data': {
                's': 'BTCUSDT',
                'b': [['100', '0'], ['98', '6']],
                'a': [['101', '3.5']],
                'u': 2,
                'seq': 11,
            },
        }
    )

    spreads = read_jsonl(tmp_path / 'normalized' / 'best_bid_ask_spread' / 'BTCUSDT.jsonl')
    assert spreads[-1] == {
        'symbol': 'BTCUSDT',
        'timestamp_ms': 20,
        'update_id': 2,
        'sequence': 11,
        'bid_price': 99.0,
        'bid_size': 3.0,
        'ask_price': 101.0,
        'ask_size': 3.5,
        'spread': 2.0,
        'spread_bps': pytest.approx(200.0),
    }


class StubRestClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_orderbook_snapshot(self, symbol: str, limit: int = 50) -> dict:
        self.calls.append(f'{symbol}:{limit}')
        return {
            'topic': f'orderbook.50.{symbol}',
            'type': 'snapshot',
            'ts': 30,
            'data': {
                's': symbol,
                'b': [['200', '1']],
                'a': [['201', '1']],
                'u': 99,
                'seq': 99,
            },
        }


def test_orderbook_sequence_gap_triggers_rest_snapshot_resync(tmp_path: Path):
    rest_client = StubRestClient()
    collector = BybitPublicCollector(
        BybitPublicCollectorConfig(data_dir=tmp_path, symbols=['BTCUSDT']),
        rest_client=rest_client,
    )
    collector.process_message(
        {
            'topic': 'orderbook.50.BTCUSDT',
            'type': 'snapshot',
            'ts': 10,
            'data': {'s': 'BTCUSDT', 'b': [['100', '1']], 'a': [['101', '1']], 'u': 1, 'seq': 10},
        }
    )

    result = collector.process_message(
        {
            'topic': 'orderbook.50.BTCUSDT',
            'type': 'delta',
            'ts': 20,
            'data': {'s': 'BTCUSDT', 'b': [['100', '2']], 'a': [], 'u': 2, 'seq': 13},
        }
    )

    assert result.resync_performed is True
    assert result.gap_detected is True
    assert rest_client.calls == ['BTCUSDT:50']
    spreads = read_jsonl(tmp_path / 'normalized' / 'best_bid_ask_spread' / 'BTCUSDT.jsonl')
    assert spreads[-1]['bid_price'] == 200.0
    assert spreads[-1]['ask_price'] == 201.0


def test_rest_client_builds_public_orderbook_snapshot_from_bybit_response(monkeypatch):
    requested: list[str] = []

    def fake_get_json(url: str) -> dict:
        requested.append(url)
        return {
            'retCode': 0,
            'result': {
                's': 'ETHUSDT',
                'b': [['3000', '2']],
                'a': [['3001', '3']],
                'u': 123,
                'seq': 456,
                'ts': 170,
            },
        }

    client = BybitPublicRestClient(http_get_json=fake_get_json)

    snapshot = client.fetch_orderbook_snapshot('ETHUSDT', limit=50)

    assert requested == [
        'https://api.bybit.com/v5/market/orderbook?category=linear&symbol=ETHUSDT&limit=50'
    ]
    assert snapshot == {
        'topic': 'orderbook.50.ETHUSDT',
        'type': 'snapshot',
        'ts': 170,
        'data': {'s': 'ETHUSDT', 'b': [['3000', '2']], 'a': [['3001', '3']], 'u': 123, 'seq': 456, 'ts': 170},
    }


class FakeWebSocket:
    def __init__(self, messages: list[dict]) -> None:
        self.messages = [json.dumps(message) for message in messages]
        self.sent: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, payload: str) -> None:
        self.sent.append(payload)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.messages:
            raise StopAsyncIteration
        return self.messages.pop(0)


class FakeWebSocketConnector:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket
        self.urls: list[str] = []

    def __call__(self, url: str):
        self.urls.append(url)
        return self.websocket


def test_collect_once_subscribes_and_processes_mocked_websocket_events(tmp_path: Path):
    websocket = FakeWebSocket(
        [
            {'success': True, 'op': 'subscribe'},
            {
                'topic': 'publicTrade.BTCUSDT',
                'type': 'snapshot',
                'ts': 1,
                'data': [{'T': 1, 's': 'BTCUSDT', 'S': 'Sell', 'v': '0.5', 'p': '100', 'i': 't1'}],
            },
        ]
    )
    connector = FakeWebSocketConnector(websocket)
    collector = BybitPublicCollector(
        BybitPublicCollectorConfig(data_dir=tmp_path, symbols=['BTCUSDT']),
        websocket_connect=connector,
    )

    processed = asyncio.run(collector.collect_once(max_messages=2))

    assert processed == 2
    assert connector.urls == ['wss://stream.bybit.com/v5/public/linear']
    assert json.loads(websocket.sent[0]) == {
        'op': 'subscribe',
        'args': ['publicTrade.BTCUSDT', 'kline.1.BTCUSDT', 'orderbook.50.BTCUSDT'],
    }
    trades = read_jsonl(tmp_path / 'normalized' / 'trades' / 'BTCUSDT.jsonl')
    assert trades[0]['trade_id'] == 't1'
    assert trades[0]['side'] == 'Sell'
