import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from budget_variance_forecast.synthetic import build_synthetic_dataset
from budget_variance_forecast.review import create_snapshot, save_snapshot, load_snapshot, review_forecasts
from budget_variance_forecast.validation import DataValidationError


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.d = build_synthetic_dataset(actual_months=3)
        self.s = create_snapshot(self.d.budget, self.d.actual, self.d.assumptions, 'M03', '2026-03-31')
        self.actual = build_synthetic_dataset(actual_months=12).actual

    def test_forecasts_only_and_future_actuals_rejected(self):
        self.assertTrue((self.s.month > self.s.as_of).all())
        with self.assertRaises(DataValidationError):
            create_snapshot(self.d.budget, self.actual, self.d.assumptions, 'M03', '2026-03-01')

    def test_snapshot_is_immutable_and_checksum_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            path = save_snapshot(self.s, folder, provenance='test')
            self.assertEqual(len(load_snapshot(path)), len(self.s))
            with self.assertRaises(FileExistsError):
                save_snapshot(self.s, folder, provenance='test')
            with (path/'forecast.csv').open('a') as f:
                f.write('tampered')
            with self.assertRaisesRegex(DataValidationError, 'checksum'):
                load_snapshot(path)

    def test_known_error_metrics_and_zero_denominator(self):
        one = self.s.iloc[[0]].copy()
        actual = self.actual.merge(one[['month', 'business_unit', 'product']], on=['month', 'business_unit', 'product'])
        one['revenue'] = float(actual.actual_revenue.iloc[0])+10
        _, scores = review_forecasts(one, actual)
        revenue = scores[scores.metric.eq('revenue')].iloc[0]
        self.assertAlmostEqual(revenue.bias, 10)
        self.assertAlmostEqual(revenue.mae, 10)
        self.assertAlmostEqual(revenue.rmse, 10)
        actual['actual_revenue'] = 0.
        _, scores = review_forecasts(one, actual)
        self.assertTrue(np.isnan(scores[scores.metric.eq('revenue')].wape.iloc[0]))

    def test_missing_actuals_are_pending_not_zero(self):
        partial = self.actual[self.actual.month.dt.month <= 4]
        detail, scores = review_forecasts(self.s, partial)
        self.assertTrue(detail.loc[detail.status.eq('pending_actual'), 'error'].isna().all())
        self.assertGreater(scores.n_pending.sum(), 0)
        self.assertEqual(scores.n_scored.sum(), 4*3*2)

    def test_duplicate_versions_or_actuals_are_rejected(self):
        for forecasts, actual in ((pd.concat([self.s, self.s]), self.actual),
                                  (self.s, pd.concat([self.actual, self.actual.iloc[[0]]]))):
            with self.assertRaises(DataValidationError):
                review_forecasts(forecasts, actual)
        different_day = self.s.iloc[[0]].copy()
        different_day['month'] += pd.Timedelta(days=10)
        with self.assertRaises(DataValidationError):
            review_forecasts(pd.concat([self.s, different_day]), self.actual)
        blank = self.s.copy()
        blank['scenario'] = ' '
        with self.assertRaises(DataValidationError):
            review_forecasts(blank, self.actual)

    def test_different_vintages_remain_separate(self):
        newer = build_synthetic_dataset(actual_months=6)
        s2 = create_snapshot(newer.budget, newer.actual, newer.assumptions, 'M06', '2026-06-01')
        detail, scores = review_forecasts(pd.concat([self.s, s2]), self.actual)
        self.assertEqual(set(scores.version), {'M03', 'M06'})
        july = detail[detail.month.eq(pd.Timestamp('2026-07-01'))]
        self.assertEqual(set(july.horizon_months), {1, 4})
