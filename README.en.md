# Budget Variance and Rolling Forecast

[中文](README.md) · English

Explain operating-profit movements and track how forecasts compare with subsequently realized results.

## Analytical approach and deliverables

- Reconcile volume, mix, price, unit-cost and fixed-expense effects to the total profit variance.
- Preserve actual months and apply scenario assumptions only to future months.
- Save named forecast vintages with input hashes, assumptions and a checksum; existing versions cannot be overwritten.
- Review revenue and operating profit by vintage, scenario and lead time using MAE, RMSE, signed bias and WAPE. Missing actuals remain pending.

The synthetic example has a favourable revenue variance of CNY 17,584 but an adverse operating-profit variance of CNY 10,724.36. The review demo reconstructs March, June and September vintages; it does not claim they were issued historically. See [review methodology](docs/forecast-review.md).

## Reproduce

Run from the repository root with Python 3.12:

```powershell
python -m pip install -e .
python -m budget_variance_forecast.demo
python -m budget_variance_forecast.review --output-dir forecast_review_output
python -m unittest discover -s tests -v
```

## Interpretation and limitations

Positive error means forecast minus actual. WAPE is undefined when the sum of absolute actuals is zero. Compare matching target periods and lead times; scenario assumptions are not calibrated forecasts. Use a new output directory to rerun the immutable-vintage demo.

Business examples use synthetic data and contain no private company or customer records. Only the separately labelled World Bank case in the macro repository uses public economic observations. Refer to current source and CI for this update; older release tags and screenshots describe earlier snapshots.
