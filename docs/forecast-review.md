# Forecast-vintage review / 预测版本复盘

A version records its actual-through month, scenario, future target month, business unit/product and revenue/profit forecasts. Only periods after the version's origin enter scoring. Creation refuses an actual cutoff different from the requested origin. This monthly demonstration assumes actuals through that month are available; use a later operational origin if accounting close is delayed.

`save_snapshot` writes a new version directory and refuses overwrite. Metadata includes assumptions, hashes of budget/actual inputs, the forecast file checksum and a user-supplied provenance description. Hashes detect accidental edits; they are not a digital signature or historical timestamp proof. Input files must be separately retained under the user's data-retention policy.

`review_forecasts` matches later actuals by month/business unit/product. Missing actuals remain `pending_actual`; they are not zero. Duplicate forecast or actual keys are rejected. Scores are grouped by version, scenario, metric and lead time. This avoids silently blending different horizons; when comparing vintages, explicitly choose common target months and appropriate lead times from the detail file.

- Error and Bias = forecast minus actual; positive means overforecast.
- MAE = mean absolute error; RMSE = square root of mean squared error.
- WAPE = sum absolute errors / sum absolute actuals; undefined when the denominator is zero.
- Profit may be negative. Errors use currency units, and WAPE is a ratio, not percentage points.
- Pending actuals do not contribute to metrics. Groups without scored observations have blank metrics.

```powershell
python -m budget_variance_forecast.review --output-dir forecast_review_output
```

Run in the repository root after `pip install -e .`. Use a new output folder on rerun: overwriting an existing vintage is intentionally rejected.

The committed [example](review-example/) reconstructs March, June and September versions using synthetic data and fixed scenario factors, then scores synthetic full-year actuals. It is not evidence that forecasts were issued historically or that the scenario assumptions are calibrated. It contains 216 forecast rows and 432 metric-level review rows. It is useful for inspecting the audit trail and error definitions, not claiming predictive performance.

For production use, save each version when actually approved, retain its original inputs and assumptions, identify any restated actuals, and run `review_forecasts` with the later actual table. Do not regenerate old forecasts from newly observed outcomes.
