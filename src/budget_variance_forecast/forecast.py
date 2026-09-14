"""基于已发生实际和未来假设生成全年滚动预测。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .synthetic import KEY_COLUMNS
from .validation import DataValidationError, validate_inputs


ASSUMPTION_COLUMNS = [
    "scenario",
    "quantity_factor",
    "price_factor",
    "unit_cost_factor",
    "fixed_expense_factor",
]


@dataclass(frozen=True)
class ForecastResult:
    """滚动预测明细、情景汇总和实际截止月份。"""

    detail: pd.DataFrame
    summary: pd.DataFrame
    actual_through: pd.Timestamp


def build_rolling_forecast(
    budget: pd.DataFrame,
    actual: pd.DataFrame,
    assumptions: pd.DataFrame,
) -> ForecastResult:
    """保留截止月份内的实际值，仅对之后月份应用情景假设。"""

    validate_inputs(budget, actual)
    _validate_assumptions(assumptions)
    actual_through = pd.Timestamp(actual["month"].max())
    _validate_actual_periods_are_complete(budget, actual, actual_through)

    actual_lookup = actual.set_index(KEY_COLUMNS)
    rows: list[dict[str, object]] = []
    for assumption in assumptions.itertuples(index=False):
        for budget_row in budget.itertuples(index=False):
            key = (budget_row.month, budget_row.business_unit, budget_row.product)
            is_actual = pd.Timestamp(budget_row.month) <= actual_through
            if is_actual:
                actual_row = actual_lookup.loc[key]
                quantity = float(actual_row["actual_quantity"])
                revenue = float(actual_row["actual_revenue"])
                variable_cost = float(actual_row["actual_variable_cost"])
                fixed_expense = float(actual_row["actual_fixed_expense"])
            else:
                quantity = float(budget_row.budget_quantity * assumption.quantity_factor)
                unit_price = float(budget_row.budget_unit_price * assumption.price_factor)
                unit_cost = float(
                    budget_row.budget_unit_variable_cost * assumption.unit_cost_factor
                )
                revenue = quantity * unit_price
                variable_cost = quantity * unit_cost
                fixed_expense = float(
                    budget_row.budget_fixed_expense * assumption.fixed_expense_factor
                )
            gross_profit = revenue - variable_cost
            rows.append(
                {
                    "scenario": assumption.scenario,
                    "month": budget_row.month,
                    "business_unit": budget_row.business_unit,
                    "product": budget_row.product,
                    "data_type": "实际" if is_actual else "预测",
                    "quantity": quantity,
                    "revenue": revenue,
                    "variable_cost": variable_cost,
                    "fixed_expense": fixed_expense,
                    "gross_profit": gross_profit,
                    "operating_profit": gross_profit - fixed_expense,
                }
            )

    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby("scenario", sort=False, observed=True)[
            ["quantity", "revenue", "variable_cost", "fixed_expense", "gross_profit", "operating_profit"]
        ]
        .sum()
        .reset_index()
    )
    return ForecastResult(detail=detail, summary=summary, actual_through=actual_through)


def _validate_assumptions(assumptions: pd.DataFrame) -> None:
    missing = [column for column in ASSUMPTION_COLUMNS if column not in assumptions.columns]
    if missing:
        raise DataValidationError(f"预测假设表缺少字段：{', '.join(missing)}")
    if assumptions["scenario"].isna().any() or assumptions["scenario"].duplicated().any():
        raise DataValidationError("预测情景名称不能为空或重复")
    factors = assumptions[ASSUMPTION_COLUMNS[1:]].apply(pd.to_numeric, errors="coerce")
    if (factors.isna() | (factors < 0)).any().any():
        raise DataValidationError("预测情景系数必须是非负数字")


def _validate_actual_periods_are_complete(
    budget: pd.DataFrame, actual: pd.DataFrame, actual_through: pd.Timestamp
) -> None:
    expected = budget.loc[budget["month"] <= actual_through, KEY_COLUMNS]
    expected_keys = set(map(tuple, expected.itertuples(index=False, name=None)))
    actual_keys = set(map(tuple, actual[KEY_COLUMNS].itertuples(index=False, name=None)))
    missing = expected_keys - actual_keys
    if missing:
        sample = sorted(missing, key=str)[0]
        raise DataValidationError(f"实际截止月份内存在缺失记录，例如：{sample}")
