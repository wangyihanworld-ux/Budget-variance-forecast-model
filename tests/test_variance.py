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
        self.assertLess(
            result.profit_bridge["reconciliation_difference"].abs().max(), 1e-8
        )

    def test_mix_is_separated_from_total_volume(self) -> None:
        budget = pd.DataFrame(
            [
                {
                    "month": pd.Timestamp("2026-01-01"),
                    "business_unit": "演示事业部",
                    "product": "低毛利",
                    "budget_quantity": 50.0,
                    "budget_unit_price": 10.0,
                    "budget_unit_variable_cost": 8.0,
                    "budget_fixed_expense": 0.0,
                },
                {
                    "month": pd.Timestamp("2026-01-01"),
                    "business_unit": "演示事业部",
                    "product": "高毛利",
                    "budget_quantity": 50.0,
                    "budget_unit_price": 10.0,
                    "budget_unit_variable_cost": 2.0,
                    "budget_fixed_expense": 0.0,
                },
            ]
        )
        actual = pd.DataFrame(
            [
                {
                    "month": pd.Timestamp("2026-01-01"),
                    "business_unit": "演示事业部",
                    "product": "低毛利",
                    "actual_quantity": 40.0,
                    "actual_revenue": 400.0,
                    "actual_variable_cost": 320.0,
                    "actual_fixed_expense": 0.0,
                },
                {
                    "month": pd.Timestamp("2026-01-01"),
                    "business_unit": "演示事业部",
                    "product": "高毛利",
                    "actual_quantity": 60.0,
                    "actual_revenue": 600.0,
                    "actual_variable_cost": 120.0,
                    "actual_fixed_expense": 0.0,
                },
            ]
        )
        bridge = calculate_variances(budget, actual).profit_bridge.iloc[0]
        self.assertAlmostEqual(bridge["volume_profit_impact"], 0.0)
        self.assertAlmostEqual(bridge["mix_profit_impact"], 60.0)
        self.assertAlmostEqual(bridge["operating_profit_variance"], 60.0)

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

    def test_excel_style_numeric_text_and_month_are_normalized(self) -> None:
        budget = one_row_budget(budget_quantity="100", budget_unit_price="10")
        actual = one_row_actual(actual_quantity="100", actual_revenue="1100")
        budget["month"] = "2026-01-31"
        actual["month"] = "2026-01-01"
        result = calculate_variances(budget, actual)
        self.assertAlmostEqual(result.detail.iloc[0]["price_profit_impact"], 100.0)

    def test_invalid_month_is_rejected(self) -> None:
        actual = one_row_actual()
        actual["month"] = pd.Series(["不是日期"], dtype="object")
        with self.assertRaisesRegex(DataValidationError, "有效日期"):
            calculate_variances(one_row_budget(), actual)
        blank_product = one_row_actual()
        blank_product.loc[0, "product"] = "  "
        with self.assertRaisesRegex(DataValidationError, "不能为空"):
            calculate_variances(one_row_budget(), blank_product)

    def test_empty_actual_is_rejected(self) -> None:
        with self.assertRaisesRegex(DataValidationError, "实际表不能为空"):
            calculate_variances(one_row_budget(), one_row_actual().iloc[0:0])


if __name__ == "__main__":
    unittest.main()
