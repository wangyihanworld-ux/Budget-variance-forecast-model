"""Persist forecast vintages and score only future periods that later realized."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .forecast import build_rolling_forecast
from .synthetic import KEY_COLUMNS, build_synthetic_dataset
from .validation import DataValidationError, ACTUAL_VALUE_COLUMNS, _normalize_frame, _require_columns, _require_unique_keys, _require_nonnegative

METRICS = ['revenue', 'operating_profit']
SNAPSHOT_KEYS = ['version', 'scenario', *KEY_COLUMNS]


def create_snapshot(budget, actual, assumptions, version, as_of):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', version):
        raise DataValidationError('Version must contain only letters, numbers, underscores or hyphens')
    cutoff = pd.Timestamp(as_of).to_period('M').to_timestamp()
    result = build_rolling_forecast(budget, actual, assumptions)
    if result.actual_through != cutoff:
        raise DataValidationError('Actual cutoff must match as_of; do not include future actuals')
    rows = result.detail[result.detail.data_type == '预测'].copy()
    if rows.empty:
        raise DataValidationError('Snapshot must contain future forecast periods')
    rows = rows[['scenario', *KEY_COLUMNS, *METRICS]]
    rows.insert(0, 'version', version)
    rows.insert(1, 'as_of', cutoff)
    rows['horizon_months'] = (rows.month.dt.year-cutoff.year)*12+rows.month.dt.month-cutoff.month
    if not np.isfinite(rows[METRICS].to_numpy(float)).all():
        raise DataValidationError('Forecast values must be finite')
    rows.attrs['inputs'] = {
        'budget_sha256': hashlib.sha256(budget.to_csv(index=False).encode('utf-8')).hexdigest(),
        'actual_sha256': hashlib.sha256(actual.to_csv(index=False).encode('utf-8')).hexdigest(),
        'assumptions': assumptions.to_dict(orient='records'),
    }
    return rows


def save_snapshot(rows, folder, *, provenance):
    """No overwrite: changes require a new version. Hash detects accidental edits."""
    versions = rows.version.unique()
    if len(versions) != 1 or not re.fullmatch(r'[A-Za-z0-9_-]+', str(versions[0])):
        raise DataValidationError('A snapshot must have one safe version identifier')
    target = Path(folder)/versions[0]
    target.mkdir(parents=True, exist_ok=False)
    payload = rows.to_csv(index=False).encode('utf-8')
    (target/'forecast.csv').write_bytes(payload)
    metadata = dict(version=versions[0], as_of=str(rows.as_of.iloc[0]),
                    sha256=hashlib.sha256(payload).hexdigest(), provenance=provenance,
                    inputs=rows.attrs.get('inputs', {}),
                    error_convention='forecast minus actual; positive means overforecast')
    (target/'metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
    return target


def load_snapshot(folder):
    folder = Path(folder)
    metadata = json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    payload = (folder/'forecast.csv').read_bytes()
    if hashlib.sha256(payload).hexdigest() != metadata['sha256']:
        raise DataValidationError('Snapshot checksum mismatch')
    return pd.read_csv(folder/'forecast.csv', parse_dates=['as_of', 'month'])


def review_forecasts(snapshots, actual):
    forecasts = snapshots.copy()
    required = SNAPSHOT_KEYS + ['as_of', 'horizon_months', *METRICS]
    _require_columns(forecasts, required, '预测版本')
    if forecasts.empty:
        raise DataValidationError('Forecast versions must be nonempty and unique by scenario and business key')
    for col in ('as_of', 'month'):
        forecasts[col] = pd.to_datetime(forecasts[col], errors='coerce').dt.to_period('M').dt.to_timestamp()
    if forecasts[['as_of', 'month']].isna().any().any() or (forecasts.month <= forecasts.as_of).any():
        raise DataValidationError('Only periods after the forecast origin may be scored')
    if forecasts.duplicated(SNAPSHOT_KEYS).any():
        raise DataValidationError('Duplicate normalized forecast keys')
    labels = forecasts[['version', 'scenario', 'business_unit', 'product']]
    if labels.isna().any().any() or labels.astype('string').apply(lambda x: x.str.strip().eq('')).any().any():
        raise DataValidationError('Forecast labels cannot be blank')
    if (forecasts.groupby('version').as_of.nunique() != 1).any():
        raise DataValidationError('Each version must have one forecast origin')
    expected = (forecasts.month.dt.year-forecasts.as_of.dt.year)*12+forecasts.month.dt.month-forecasts.as_of.dt.month
    if not forecasts.horizon_months.eq(expected).all():
        raise DataValidationError('Forecast horizon does not match origin and target')
    if not np.isfinite(forecasts[METRICS].to_numpy(float)).all():
        raise DataValidationError('Forecasts must be finite')
    actual = actual.copy()
    _require_columns(actual, KEY_COLUMNS+ACTUAL_VALUE_COLUMNS, '实际表')
    _normalize_frame(actual, ACTUAL_VALUE_COLUMNS, '实际表')
    _require_unique_keys(actual, '实际表')
    _require_nonnegative(actual, ACTUAL_VALUE_COLUMNS, '实际表')
    if not np.isfinite(actual[ACTUAL_VALUE_COLUMNS].to_numpy(float)).all():
        raise DataValidationError('Actuals must be finite')
    actual['actual_operating_profit'] = actual.actual_revenue-actual.actual_variable_cost-actual.actual_fixed_expense
    joined = forecasts.merge(actual[KEY_COLUMNS+['actual_revenue', 'actual_operating_profit']],
                             on=KEY_COLUMNS, how='left', validate='many_to_one', indicator=True)
    joined['status'] = np.where(joined['_merge'].eq('both'), 'scored', 'pending_actual')
    # Missing actuals stay pending; they are never replaced with zero.
    records = []
    for metric in METRICS:
        part = joined[['version', 'as_of', 'scenario', *KEY_COLUMNS, 'horizon_months', 'status']].copy()
        part['metric'] = metric
        part['forecast'] = joined[metric]
        part['actual'] = joined['actual_'+metric]
        part['error'] = part.forecast-part.actual
        records.append(part)
    detail = pd.concat(records, ignore_index=True)
    rows = []
    # Scores by lead time avoid treating all vintage horizons as equivalent.
    for keys, group in detail.groupby(['version', 'scenario', 'metric', 'horizon_months'], sort=True):
        scored = group[group.status.eq('scored')]
        errors = scored.error
        denominator = float(scored.actual.abs().sum())
        rows.append(dict(zip(['version', 'scenario', 'metric', 'horizon_months'], keys),
                         n_scored=len(scored), n_pending=len(group)-len(scored),
                         bias=float(errors.mean()), mae=float(errors.abs().mean()),
                         rmse=float(np.sqrt((errors**2).mean())),
                         wape=float(errors.abs().sum()/denominator) if denominator else float('nan')))
    return detail, pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='forecast_review_output')
    args = parser.parse_args()
    out = Path(args.output_dir)
    snapshots = []
    for month in (3, 6, 9):
        data = build_synthetic_dataset(actual_months=month)
        rows = create_snapshot(data.budget, data.actual, data.assumptions,
                               f'2026M{month:02}', f'2026-{month:02}-01')
        path = save_snapshot(rows, out/'vintages', provenance='Reconstructed synthetic demonstration; not forecasts actually issued in 2026')
        snapshots.append(load_snapshot(path))
    detail, scores = review_forecasts(pd.concat(snapshots), build_synthetic_dataset(actual_months=12).actual)
    detail.to_csv(out/'review_detail.csv', index=False)
    scores.to_csv(out/'review_metrics.csv', index=False)
    print(f'{len(snapshots)} synthetic vintages; {len(detail)} scored metric rows. Positive bias = overforecast.')
    print('Compare like target months and lead times; these fixed assumptions are scenarios, not calibrated forecasts.')


if __name__ == '__main__':
    main()
