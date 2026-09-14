"""预算执行和经营利润差异归因。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .synthetic import KEY_COLUMNS
from .validation import validate_inputs


@dataclass(frozen=True)
class VarianceResult:
    """预算差异明细、汇总与勾稽结果。"""

    detail: pd.DataFrame
    summary: pd.DataFrame
    reconciliation_difference: float


def calculate_variances(budget: pd.DataFrame, actual: pd.DataFrame) -> VarianceResult:
    """按共同业务键计算预算差异并建立经营利润桥。

    收入桥采用固定顺序：先以预算价格计算数量影响，再以实际数量计算价格
    影响。利润桥在此基础上加入单位变动成本和固定费用影响。该顺序决定交互
    项归属，因此会在项目报告中公开，而不会把它描述成唯一拆分方法。
    """

    validate_inputs(budget, actual)
    detail = actual.merge(budget, on=KEY_COLUMNS, how="left", validate="one_to_one")

    detail["actual_unit_price"] = _safe_divide(
        detail["actual_revenue"], detail["actual_quantity"]
    )
    detail["actual_unit_variable_cost"] = _safe_divide(
        detail["actual_variable_cost"], detail["actual_quantity"]
    )
    detail["budget_revenue"] = detail["budget_quantity"] * detail["budget_unit_price"]
    detail["budget_variable_cost"] = (
        detail["budget_quantity"] * detail["budget_unit_variable_cost"]
    )
    detail["budget_gross_profit"] = detail["budget_revenue"] - detail["budget_variable_cost"]
    detail["actual_gross_profit"] = detail["actual_revenue"] - detail["actual_variable_cost"]
    detail["budget_operating_profit"] = (
        detail["budget_gross_profit"] - detail["budget_fixed_expense"]
    )
    detail["actual_operating_profit"] = (
        detail["actual_gross_profit"] - detail["actual_fixed_expense"]
    )

    detail["revenue_variance"] = detail["actual_revenue"] - detail["budget_revenue"]
    detail["quantity_revenue_impact"] = (
        (detail["actual_quantity"] - detail["budget_quantity"])
        * detail["budget_unit_price"]
    )
    detail["price_revenue_impact"] = (
        (detail["actual_unit_price"] - detail["budget_unit_price"])
        * detail["actual_quantity"]
    )
    detail["variable_cost_variance"] = (
        detail["actual_variable_cost"] - detail["budget_variable_cost"]
    )
    detail["fixed_expense_variance"] = (
        detail["actual_fixed_expense"] - detail["budget_fixed_expense"]
    )
    detail["operating_profit_variance"] = (
        detail["actual_operating_profit"] - detail["budget_operating_profit"]
    )

    budget_unit_margin = detail["budget_unit_price"] - detail["budget_unit_variable_cost"]
    detail["quantity_profit_impact"] = (
        detail["actual_quantity"] - detail["budget_quantity"]
    ) * budget_unit_margin
    detail["price_profit_impact"] = detail["price_revenue_impact"]
    detail["unit_cost_profit_impact"] = -(
        detail["actual_unit_variable_cost"] - detail["budget_unit_variable_cost"]
    ) * detail["actual_quantity"]
    detail["fixed_expense_profit_impact"] = -detail["fixed_expense_variance"]
    detail["explained_profit_variance"] = detail[
        [
            "quantity_profit_impact",
            "price_profit_impact",
            "unit_cost_profit_impact",
            "fixed_expense_profit_impact",
        ]
    ].sum(axis=1)
    detail["reconciliation_difference"] = (
        detail["operating_profit_variance"] - detail["explained_profit_variance"]
    )

    summary = _build_summary(detail)
    difference = float(detail["reconciliation_difference"].sum())
    return VarianceResult(detail=detail, summary=summary, reconciliation_difference=difference)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator.div(denominator.where(denominator.ne(0)))
    zero_with_value = denominator.eq(0) & numerator.ne(0)
    if zero_with_value.any():
        raise ValueError("数量为 0 时，收入或变动成本必须同时为 0")
    return result.fillna(0.0)


def _build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        ("预算收入", "budget_revenue"),
        ("实际收入", "actual_revenue"),
        ("收入差异", "revenue_variance"),
        ("数量对收入影响", "quantity_revenue_impact"),
        ("价格对收入影响", "price_revenue_impact"),
        ("预算经营利润", "budget_operating_profit"),
        ("实际经营利润", "actual_operating_profit"),
        ("经营利润差异", "operating_profit_variance"),
        ("数量对利润影响", "quantity_profit_impact"),
        ("价格对利润影响", "price_profit_impact"),
        ("单位成本对利润影响", "unit_cost_profit_impact"),
        ("固定费用对利润影响", "fixed_expense_profit_impact"),
        ("利润桥勾稽差异", "reconciliation_difference"),
    ]
    return pd.DataFrame(
        [{"metric": label, "amount": float(detail[column].sum())} for label, column in metrics]
    )
