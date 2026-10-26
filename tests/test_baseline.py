import unittest
import pandas as pd
from budget_variance_forecast.baseline import run_rate_snapshot
from budget_variance_forecast.synthetic import build_synthetic_dataset
from budget_variance_forecast.validation import DataValidationError

class BaselineTests(unittest.TestCase):
    def test_mean_matches_hand_calculation(self):
        d=build_synthetic_dataset(actual_months=3)
        result=run_rate_snapshot(d.budget,d.actual,'M03','2026-03-01')
        first=result.iloc[0]
        h=d.actual[d.actual.business_unit.eq(first['business_unit']) & d.actual['product'].eq(first['product'])]
        self.assertAlmostEqual(first.revenue,h.actual_revenue.mean())
        self.assertEqual(len(result),36)
    def test_future_values_cannot_enter_cutoff(self):
        d=build_synthetic_dataset(actual_months=12)
        with self.assertRaises(DataValidationError): run_rate_snapshot(d.budget,d.actual,'M03','2026-03-01')
        cutoff=pd.Timestamp('2026-03-01'); before=d.actual[d.actual.month<=cutoff]
        expected=run_rate_snapshot(d.budget,before,'M03',cutoff)
        d.actual.loc[d.actual.month>cutoff,'actual_revenue']=1e9
        actual=run_rate_snapshot(d.budget,d.actual[d.actual.month<=cutoff],'M03',cutoff)
        pd.testing.assert_frame_equal(expected,actual)
