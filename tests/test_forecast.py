import unittest

import pandas as pd

from budget_variance_forecast.forecast import build_rolling_forecast
from budget_variance_forecast.synthetic import build_synthetic_dataset
from budget_variance_forecast.validation import DataValidationError


class RollingForecastTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = build_synthetic_dataset(actual_months=6)

    def test_actual_months_are_identical_in_every_scenario(self) -> None:
        result = build_rolling_forecast(
            self.dataset.budget, self.dataset.actual, self.dataset.assumptions
        )
        actual_rows = result.detail[result.detail["data_type"] == "实际"]
        comparison_columns = [
            "month", "business_unit", "product", "quantity", "revenue",
            "variable_cost", "fixed_expense", "operating_profit",
        ]
        base = actual_rows[actual_rows["scenario"] == "基准"][comparison_columns]
        for scenario in ("谨慎", "乐观"):
            other = actual_rows[actual_rows["scenario"] == scenario][comparison_columns]
            pd.testing.assert_frame_equal(
                base.reset_index(drop=True), other.reset_index(drop=True)
            )

    def test_only_future_months_use_scenario_factors(self) -> None:
        result = build_rolling_forecast(
            self.dataset.budget, self.dataset.actual, self.dataset.assumptions
        )
        future = result.detail[result.detail["data_type"] == "预测"]
        optimistic = future[future["scenario"] == "乐观"]
        cautious = future[future["scenario"] == "谨慎"]
        self.assertGreater(optimistic["revenue"].sum(), cautious["revenue"].sum())
        self.assertGreater(
            optimistic["operating_profit"].sum(), cautious["operating_profit"].sum()
        )

    def test_full_year_has_one_row_per_budget_key_and_scenario(self) -> None:
        result = build_rolling_forecast(
            self.dataset.budget, self.dataset.actual, self.dataset.assumptions
        )
        self.assertEqual(len(result.detail), 48 * 3)
        self.assertEqual(result.actual_through, pd.Timestamp("2026-06-01"))
        self.assertEqual(set(result.detail["data_type"]), {"实际", "预测"})

    def test_incomplete_actual_period_is_rejected(self) -> None:
        incomplete = self.dataset.actual.drop(index=0)
        with self.assertRaisesRegex(DataValidationError, "截止月份内存在缺失"):
            build_rolling_forecast(
                self.dataset.budget, incomplete, self.dataset.assumptions
            )

    def test_duplicate_scenario_is_rejected(self) -> None:
        duplicated = pd.concat(
            [self.dataset.assumptions, self.dataset.assumptions.iloc[[0]]],
            ignore_index=True,
        )
        with self.assertRaisesRegex(DataValidationError, "重复"):
            build_rolling_forecast(
                self.dataset.budget, self.dataset.actual, duplicated
            )
        blank = self.dataset.assumptions.copy()
        blank.loc[0, "scenario"] = "  "
        with self.assertRaisesRegex(DataValidationError, "不能为空"):
            build_rolling_forecast(
                self.dataset.budget, self.dataset.actual, blank
            )

    def test_numeric_text_scenario_factors_are_normalized(self) -> None:
        assumptions = self.dataset.assumptions.astype(str)
        result = build_rolling_forecast(
            self.dataset.budget, self.dataset.actual, assumptions
        )
        self.assertEqual(len(result.detail), 48 * 3)


if __name__ == "__main__":
    unittest.main()
