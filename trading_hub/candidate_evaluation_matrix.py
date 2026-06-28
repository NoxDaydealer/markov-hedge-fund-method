from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from trading_hub.go_no_go_gate import evaluate_go_no_go
from trading_hub.hft_evaluator import WalkForwardConfig, evaluate_intraday_strategy, walk_forward_evaluate

ParamGrid = Mapping[str, Sequence[Any]]
AdapterFactory = Callable[..., Any]


@dataclass(frozen=True)
class CandidateSpec:
    """One local, paper-only strategy candidate family for matrix evaluation."""

    name: str
    adapter_factory: AdapterFactory
    param_grid: ParamGrid
    signal_column: str = 'signal'


DEFAULT_WALK_FORWARD = WalkForwardConfig(
    train_bars=10_080,  # 7 days of 1m bars
    validation_bars=2_880,  # 2 days
    test_bars=2_880,  # 2 days
    step_bars=2_880,
)

DEFAULT_REPORT_COLUMNS = [
    'symbol',
    'candidate',
    'params',
    'full_net_pnl',
    'full_max_drawdown',
    'full_fee_to_gross_profit',
    'full_trades',
    'full_win_rate',
    'folds',
    'gate',
    'reasons_failed',
    'avg_test_net_pnl',
    'worst_test_drawdown',
    'worst_fee_to_gross_profit',
    'avg_test_trades',
    'fraction_folds_beat_random',
]


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """Load local OHLCV CSV data for research-only evaluation."""

    frame = pd.read_csv(path)
    frame.columns = [str(column).strip().lower().replace(' ', '_') for column in frame.columns]
    for ts_col in ('timestamp', 'date', 'time', 'datetime'):
        if ts_col in frame.columns:
            frame[ts_col] = pd.to_datetime(frame[ts_col], errors='coerce')
            frame = frame.dropna(subset=[ts_col]).set_index(ts_col).sort_index()
            frame.index.name = None
            break
    required = ['open', 'high', 'low', 'close', 'volume']
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f'OHLCV data missing required columns: {missing}')
    frame = frame.loc[:, required].copy()
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    frame = frame.dropna(subset=required)
    if frame.empty:
        raise ValueError(f'OHLCV CSV has no usable rows: {path}')
    return frame


def run_candidate_matrix(
    data_by_symbol: Mapping[str, pd.DataFrame],
    candidate_specs: Sequence[CandidateSpec],
    *,
    walk_forward_config: WalkForwardConfig = DEFAULT_WALK_FORWARD,
    max_combinations_per_candidate: int = 64,
    min_trades_per_fold: int = 20,
) -> pd.DataFrame:
    """Evaluate candidate parameter grids across symbols with full + walk-forward gates.

    This helper is deliberately local/paper-only: it consumes caller-supplied OHLCV
    frames, asks adapters for signal columns, evaluates through the shared HFT
    evaluator, and never fetches data or connects to brokers/exchanges.
    """

    if max_combinations_per_candidate < 1:
        raise ValueError('max_combinations_per_candidate must be at least 1')
    rows: list[dict[str, Any]] = []
    for symbol, data in data_by_symbol.items():
        for spec in candidate_specs:
            combos = _parameter_combinations(spec.param_grid)
            if len(combos) > max_combinations_per_candidate:
                raise ValueError(
                    f'{spec.name} has {len(combos)} parameter combinations, '
                    f'exceeding max_combinations_per_candidate={max_combinations_per_candidate}'
                )
            for params in combos:
                rows.append(
                    _evaluate_one_candidate(
                        symbol,
                        data,
                        spec,
                        params,
                        walk_forward_config,
                        min_trades_per_fold,
                    )
                )
    result = pd.DataFrame.from_records(rows)
    if result.empty:
        return pd.DataFrame(columns=DEFAULT_REPORT_COLUMNS)
    result = result.loc[:, DEFAULT_REPORT_COLUMNS]
    return result.sort_values(
        by=['gate', 'avg_test_net_pnl', 'full_net_pnl'],
        ascending=[True, False, False],
        kind='stable',
    ).reset_index(drop=True)


def write_candidate_matrix_reports(matrix: pd.DataFrame, reports_dir: str | Path, date_str: str) -> tuple[Path, Path, Path]:
    """Write CSV, Markdown table, and concise summary for a candidate matrix."""

    out_dir = Path(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f'candidate_evaluation_matrix_{date_str}.csv'
    md_path = out_dir / f'candidate_evaluation_matrix_{date_str}.md'
    summary_path = out_dir / 'candidate_evaluation_matrix_summary.md'

    matrix.to_csv(csv_path, index=False)
    markdown = _matrix_markdown(matrix, date_str)
    md_path.write_text(markdown, encoding='utf-8')
    summary_path.write_text(_summary_markdown(matrix, date_str, csv_path, md_path), encoding='utf-8')
    return csv_path, md_path, summary_path


def _evaluate_one_candidate(
    symbol: str,
    data: pd.DataFrame,
    spec: CandidateSpec,
    params: Mapping[str, Any],
    walk_forward_config: WalkForwardConfig,
    min_trades_per_fold: int,
) -> dict[str, Any]:
    adapter = spec.adapter_factory(**params)
    signals = adapter.generate_signals(data)
    if not isinstance(signals, pd.DataFrame):
        raise TypeError(f'{spec.name}.generate_signals() must return a pandas DataFrame')
    if spec.signal_column not in signals.columns:
        raise ValueError(f"{spec.name} output missing signal column '{spec.signal_column}'")
    signal = signals.loc[:, spec.signal_column]
    if isinstance(signal, pd.DataFrame):
        raise ValueError(f"{spec.name} signal column '{spec.signal_column}' must be unique")

    label = f'{spec.name}:{symbol}'
    full = evaluate_intraday_strategy(data, signal, name=label)
    folds = walk_forward_evaluate(data, signal, walk_forward_config, name=label)
    gate = evaluate_go_no_go(folds, min_trades_per_fold=min_trades_per_fold)
    full_metrics = full.metrics
    summary = gate.metrics_summary
    return {
        'symbol': symbol,
        'candidate': spec.name,
        'params': _stable_json(params),
        'full_net_pnl': full_metrics['net_pnl'],
        'full_max_drawdown': full_metrics['max_drawdown'],
        'full_fee_to_gross_profit': full_metrics['fee_to_gross_profit'],
        'full_trades': full_metrics['trades'],
        'full_win_rate': full_metrics['win_rate'],
        'folds': len(folds),
        'gate': gate.verdict,
        'reasons_failed': '; '.join(gate.reasons_failed),
        'avg_test_net_pnl': summary.get('avg_net_pnl', 0.0),
        'worst_test_drawdown': summary.get('worst_drawdown', 0.0),
        'worst_fee_to_gross_profit': summary.get('worst_fee_to_gross_profit', 0.0),
        'avg_test_trades': summary.get('avg_trades', 0.0),
        'fraction_folds_beat_random': summary.get('fraction_folds_beat_random', 0.0),
    }


def _parameter_combinations(param_grid: ParamGrid) -> list[dict[str, Any]]:
    names = list(param_grid.keys())
    combos: list[dict[str, Any]] = [{}]
    for name in names:
        values = param_grid[name]
        if isinstance(values, (str, bytes)):
            raise TypeError(f"param_grid['{name}'] must be a sequence, not a string")
        values_list = list(values)
        if not values_list:
            raise ValueError(f"param_grid['{name}'] must contain at least one value")
        combos = [{**base, name: value} for base in combos for value in values_list]
    return combos


def _stable_json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(',', ':'), default=str)


def _matrix_markdown(matrix: pd.DataFrame, date_str: str) -> str:
    view = matrix.copy()
    for col in [
        'full_net_pnl',
        'full_max_drawdown',
        'full_fee_to_gross_profit',
        'full_win_rate',
        'avg_test_net_pnl',
        'worst_test_drawdown',
        'worst_fee_to_gross_profit',
        'avg_test_trades',
        'fraction_folds_beat_random',
    ]:
        if col in view.columns:
            view[col] = view[col].map(lambda x: f'{float(x):.6f}')
    top = view.head(30)
    active = view[pd.to_numeric(view['full_trades'], errors='coerce').fillna(0) > 0].head(30)
    return '\n'.join(
        [
            f'# Trading Hub Candidate Evaluation Matrix — {date_str}',
            '',
            'Paper/research only. No broker/API integration and no live orders.',
            '',
            f'Rows evaluated: {len(matrix)}',
            '',
            '## Top rows by gate/test/full metrics',
            '',
            _plain_markdown_table(top),
            '',
            '## Top active rows only',
            '',
            _plain_markdown_table(active),
            '',
        ]
    )


def _plain_markdown_table(frame: pd.DataFrame) -> str:
    """Render a small markdown table without pandas' optional tabulate dependency."""

    if frame.empty:
        return '_No rows._'
    headers = [str(column) for column in frame.columns]
    rendered_rows = [[str(value) for value in row] for row in frame.itertuples(index=False, name=None)]
    widths = [len(header) for header in headers]
    for row in rendered_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def render(cells: list[str]) -> str:
        return '| ' + ' | '.join(cell.ljust(widths[idx]) for idx, cell in enumerate(cells)) + ' |'

    lines = [render(headers), '| ' + ' | '.join('-' * width for width in widths) + ' |']
    lines.extend(render(row) for row in rendered_rows)
    return '\n'.join(lines)


def _summary_markdown(matrix: pd.DataFrame, date_str: str, csv_path: Path, md_path: Path) -> str:
    counts = matrix['gate'].value_counts().to_dict() if 'gate' in matrix else {}
    go_count = int(counts.get('go', 0))
    no_go_count = int(counts.get('no_go', 0))
    insufficient = int(counts.get('insufficient_data', 0))
    lines = [
        f'# Candidate Evaluation Matrix Summary — {date_str}',
        '',
        '## Scope',
        '',
        'Controlled local evaluation across candidate strategy families and BTC/ETH 1m OHLCV. Research/paper-only; live trading remains locked.',
        '',
        '## Outputs',
        '',
        f'- CSV: `{csv_path}`',
        f'- Markdown: `{md_path}`',
        '',
        '## Gate counts',
        '',
        f'- go: {go_count}',
        f'- no_go: {no_go_count}',
        f'- insufficient_data: {insufficient}',
        '',
    ]
    if go_count:
        lines.extend(['## GO candidates', ''])
        for _, row in matrix[matrix['gate'] == 'go'].head(10).iterrows():
            lines.append(f"- {row['symbol']} {row['candidate']} {row['params']} avg_test_net_pnl={row['avg_test_net_pnl']:.6f}")
    else:
        active = matrix[matrix['full_trades'] > 0].sort_values(['avg_test_net_pnl', 'full_net_pnl'], ascending=[False, False])
        lines.extend([
            '## Interpretation',
            '',
            'No candidate passed the walk-forward gate. Do not start a paper portfolio from this matrix yet; use the failure reasons to expand/refine candidates.',
            '',
            '## Least-bad active rows',
            '',
        ])
        if active.empty:
            lines.append('- No candidate produced trades under this matrix.')
        else:
            for _, row in active.head(5).iterrows():
                lines.append(
                    f"- {row['symbol']} {row['candidate']} full_net_pnl={row['full_net_pnl']:.6f}, "
                    f"full_trades={int(row['full_trades'])}, avg_test_net_pnl={row['avg_test_net_pnl']:.6f}; "
                    f"params={row['params']}"
                )
    lines.append('')
    return '\n'.join(lines)
