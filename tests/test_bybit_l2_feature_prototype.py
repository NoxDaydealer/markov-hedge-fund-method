from __future__ import annotations

from research.bybit_l2_feature_prototype import compute_aggressive_trade_flow, compute_orderbook_features


def test_orderbook_features_compute_top_n_imbalance_and_delta() -> None:
    first_book = {
        'ts': 1_700_000_000_000,
        'u': 101,
        'seq': 201,
        'b': [['100.0', '2.0'], ['99.5', '3.0']],
        'a': [['100.5', '1.0'], ['101.0', '4.0']],
    }
    row, depths = compute_orderbook_features(first_book, symbol='BTCUSDT', top_ns=[1, 2])

    assert row['best_bid'] == 100.0
    assert row['best_ask'] == 100.5
    assert row['spread_bps'] > 0
    assert row['imbalance_qty_top1'] == (2.0 - 1.0) / (2.0 + 1.0)
    assert row['imbalance_qty_top2'] == 0.0
    assert row['orderbook_delta_imbalance_top1'] == 0.0

    second_book = {
        'ts': 1_700_000_001_000,
        'u': 102,
        'seq': 202,
        'b': [['100.0', '1.0'], ['99.5', '3.0']],
        'a': [['100.5', '3.0'], ['101.0', '4.0']],
    }
    second_row, _ = compute_orderbook_features(second_book, symbol='BTCUSDT', top_ns=[1, 2], previous_depths=depths)

    assert second_row['bid_qty_delta_top1'] == -1.0
    assert second_row['ask_qty_delta_top1'] == 2.0
    assert second_row['orderbook_delta_imbalance_top1'] == (-1.0 - 2.0) / (1.0 + 2.0)


def test_aggressive_trade_flow_dedupes_seen_exec_ids() -> None:
    trades = [
        {'execId': 'a', 'time': '1700000000001', 'side': 'Buy', 'price': '100.0', 'size': '2.0'},
        {'execId': 'b', 'time': '1700000000002', 'side': 'Sell', 'price': '101.0', 'size': '1.0'},
        {'execId': 'a', 'time': '1700000000001', 'side': 'Buy', 'price': '100.0', 'size': '2.0'},
    ]

    row, seen, max_ts = compute_aggressive_trade_flow(trades, seen_exec_ids=set(), previous_trade_ts=None)

    assert row['new_trade_count'] == 2
    assert row['aggressive_buy_qty'] == 2.0
    assert row['aggressive_sell_qty'] == 1.0
    assert row['aggressive_flow_qty_imbalance'] == (2.0 - 1.0) / (2.0 + 1.0)
    assert seen == {'a', 'b'}
    assert max_ts == 1_700_000_000_002

    second_row, second_seen, second_max_ts = compute_aggressive_trade_flow(trades, seen_exec_ids=seen, previous_trade_ts=max_ts)

    assert second_row['new_trade_count'] == 0
    assert second_seen == seen
    assert second_max_ts == max_ts
