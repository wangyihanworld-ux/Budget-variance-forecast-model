import unittest
from budget_variance_forecast.synthetic import build_synthetic_dataset
from budget_variance_forecast.forecast import build_rolling_forecast
from budget_variance_forecast.variance import calculate_variances
from budget_variance_forecast.validation import DataValidationError

class InputBoundaries(unittest.TestCase):
    def setUp(self): self.d=build_synthetic_dataset(actual_months=6)
    def test_nonfinite_actual_rejected(self):
        for value in [float('inf'),float('-inf'),float('nan')]:
            x=self.d.actual.copy(); x.loc[0,'actual_revenue']=value
            with self.assertRaises(DataValidationError): calculate_variances(self.d.budget,x)
    def test_nonfinite_assumption_rejected(self):
        x=self.d.assumptions.copy(); x.loc[0,'quantity_factor']=float('inf')
        with self.assertRaises(DataValidationError): build_rolling_forecast(self.d.budget,self.d.actual,x)
    def test_empty_assumptions_rejected(self):
        with self.assertRaisesRegex(DataValidationError,'不能为空'):
            build_rolling_forecast(self.d.budget,self.d.actual,self.d.assumptions.iloc[:0])
    def test_variance_rejects_missing_actual_key(self):
        with self.assertRaisesRegex(DataValidationError,'缺失'):
            calculate_variances(self.d.budget,self.d.actual.iloc[1:])
