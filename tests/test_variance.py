import unittest

import pandas as pd

from budget_variance_forecast.synthetic import build_synthetic_dataset
from budget_variance_forecast.validation import DataValidationError
from budget_variance_forecast.variance import calculate_variances


def one_row_budget(**overrides: float) -> pd.DataFrame:
    row = {
        "month": pd.Timestamp("2026-01-01"),
        "business_unit": "演示事业部",
        "product": "演示产品",
        "budget_quantity": 100.0,
        "budget_unit_price": 10.0,
        "budget_unit_variable_cost": 6.0,
        "budget_fixed_expense": 100.0,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def one_row_actual(**overrides: float) -> pd.DataFrame:
    row = {
        "month": pd.Timestamp("2026-01-01"),
        "business_unit": "演示事业部",
        "product": "演示产品",
        "actual_quantity": 100.0,
        "actual_revenue": 1_000.0,
        "actual_variable_cost": 600.0,
        "actual_fixed_expense": 100.0,
    }
    row.update(overrides)
    return pd.DataFrame([row])


class VarianceCalculationTest(unittest.TestCase):
    def test_price_only_variance(self) -> None:
        result = calculate_variances(
            one_row_budget(), one_row_actual(actual_revenue=1_100.0)
        )
        row = result.detail.iloc[0]
        self.assertAlmostEqual(row["quantity_profit_impact"], 0.0)
        self.assertAlmostEqual(row["price_profit_impact"], 100.0)
        self.assertAlmostEqual(row["operating_profit_variance"], 100.0)
        self.assertAlmostEqual(result.reconciliation_difference, 0.0)

    def test_quantity_only_variance(self) -> None:
        result = calculate_variances(
            one_row_budget(),
            one_row_actual(
                actual_quantity=120.0,
                actual_revenue=1_200.0,
                actual_variable_cost=720.0,
            ),
        )
        row = result.detail.iloc[0]
        self.assertAlmostEqual(row["quantity_profit_impact"], 80.0)
        self.assertAlmostEqual(row["price_profit_impact"], 0.0)
        self.assertAlmostEqual(row["unit_cost_profit_impact"], 0.0)
        self.assertAlmostEqual(row["operating_profit_variance"], 80.0)

    def test_cost_and_expense_increases_are_unfavorable(self) -> None:
        result = calculate_variances(
            one_row_budget(),
            one_row_actual(actual_variable_cost=650.0, actual_fixed_expense=130.0),
        )
        row = result.detail.iloc[0]
        self.assertAlmostEqual(row["unit_cost_profit_impact"], -50.0)
        self.assertAlmostEqual(row["fixed_expense_profit_impact"], -30.0)
        self.assertAlmostEqual(row["operating_profit_variance"], -80.0)
        self.assertAlmostEqual(result.reconciliation_difference, 0.0)

    def test_synthetic_dataset_reconciles(self) -> None:
        dataset = build_synthetic_dataset()
        result = calculate_variances(dataset.budget, dataset.actual)
        self.assertEqual(len(result.detail), 24)
        self.assertAlmostEqual(result.reconciliation_difference, 0.0, places=6)
        self.assertLess(result.detail["reconciliation_difference"].abs().max(), 1e-8)
        revenue_bridge_difference = result.detail["revenue_variance"] - (
            result.detail["quantity_revenue_impact"]
            + result.detail["price_revenue_impact"]
        )
        self.assertLess(revenue_bridge_difference.abs().max(), 1e-8)

    def test_duplicate_key_is_rejected(self) -> None:
        actual = one_row_actual()
        actual = pd.concat([actual, actual], ignore_index=True)
        with self.assertRaisesRegex(DataValidationError, "主键重复"):
            calculate_variances(one_row_budget(), actual)

    def test_actual_without_budget_is_rejected(self) -> None:
        actual = one_row_actual()
        actual.loc[0, "product"] = "未知产品"
        with self.assertRaisesRegex(DataValidationError, "找不到预算"):
            calculate_variances(one_row_budget(), actual)

    def test_zero_quantity_with_revenue_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "数量为 0"):
            calculate_variances(
                one_row_budget(),
                one_row_actual(actual_quantity=0.0, actual_revenue=10.0),
            )


if __name__ == "__main__":
    unittest.main()
