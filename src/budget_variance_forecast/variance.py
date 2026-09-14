"""预算执行和经营利润差异归因。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .synthetic import KEY_COLUMNS
from .validation import normalize_and_validate_inputs


@dataclass(frozen=True)
class VarianceResult:
    """预算差异明细、汇总与勾稽结果。"""

    detail: pd.DataFrame
    profit_bridge: pd.DataFrame
    summary: pd.DataFrame
    reconciliation_difference: float


def calculate_variances(budget: pd.DataFrame, actual: pd.DataFrame) -> VarianceResult:
    """按共同业务键计算预算差异并建立经营利润桥。

    收入桥采用固定顺序：先以预算价格计算数量影响，再以实际数量计算价格
    影响。利润桥在此基础上加入单位变动成本和固定费用影响。该顺序决定交互
    项归属，因此会在项目报告中公开，而不会把它描述成唯一拆分方法。
    """

    budget, actual = normalize_and_validate_inputs(budget, actual)
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

    profit_bridge = _build_profit_bridge(detail)
    summary = _build_summary(detail, profit_bridge)
    difference = float(profit_bridge["reconciliation_difference"].sum())
    return VarianceResult(
        detail=detail,
        profit_bridge=profit_bridge,
        summary=summary,
        reconciliation_difference=difference,
    )


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator.div(denominator.where(denominator.ne(0)))
    zero_with_value = denominator.eq(0) & numerator.ne(0)
    if zero_with_value.any():
        raise ValueError("数量为 0 时，收入或变动成本必须同时为 0")
    return result.fillna(0.0)


def _build_profit_bridge(detail: pd.DataFrame) -> pd.DataFrame:
    """按月份和事业部把总销量变化与产品结构变化分开。"""

    rows: list[dict[str, object]] = []
    for (month, business_unit), group in detail.groupby(
        ["month", "business_unit"], sort=True, observed=True
    ):
        budget_quantity = float(group["budget_quantity"].sum())
        actual_quantity = float(group["actual_quantity"].sum())
        if budget_quantity <= 0:
            raise ValueError("产品结构归因要求每个月和事业部的预算总销量大于 0")

        budget_unit_margin = (
            group["budget_unit_price"] - group["budget_unit_variable_cost"]
        )
        budget_mix = group["budget_quantity"] / budget_quantity
        budget_average_margin = float((budget_mix * budget_unit_margin).sum())
        expected_at_actual_volume = actual_quantity * budget_mix

        volume_impact = (actual_quantity - budget_quantity) * budget_average_margin
        mix_impact = float(
            ((group["actual_quantity"] - expected_at_actual_volume) * budget_unit_margin).sum()
        )
        price_impact = float(group["price_profit_impact"].sum())
        unit_cost_impact = float(group["unit_cost_profit_impact"].sum())
        fixed_expense_impact = float(group["fixed_expense_profit_impact"].sum())
        operating_profit_variance = float(group["operating_profit_variance"].sum())
        explained = (
            volume_impact
            + mix_impact
            + price_impact
            + unit_cost_impact
            + fixed_expense_impact
        )
        rows.append(
            {
                "month": month,
                "business_unit": business_unit,
                "operating_profit_variance": operating_profit_variance,
                "volume_profit_impact": volume_impact,
                "mix_profit_impact": mix_impact,
                "price_profit_impact": price_impact,
                "unit_cost_profit_impact": unit_cost_impact,
                "fixed_expense_profit_impact": fixed_expense_impact,
                "explained_profit_variance": explained,
                "reconciliation_difference": operating_profit_variance - explained,
            }
        )
    return pd.DataFrame(rows)


def _build_summary(detail: pd.DataFrame, profit_bridge: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        ("预算收入", "budget_revenue"),
        ("实际收入", "actual_revenue"),
        ("收入差异", "revenue_variance"),
        ("数量对收入影响", "quantity_revenue_impact"),
        ("价格对收入影响", "price_revenue_impact"),
        ("预算经营利润", "budget_operating_profit"),
        ("实际经营利润", "actual_operating_profit"),
        ("经营利润差异", "operating_profit_variance"),
        ("销量对利润影响", "volume_profit_impact"),
        ("产品结构对利润影响", "mix_profit_impact"),
        ("价格对利润影响", "price_profit_impact"),
        ("单位成本对利润影响", "unit_cost_profit_impact"),
        ("固定费用对利润影响", "fixed_expense_profit_impact"),
        ("利润桥勾稽差异", "reconciliation_difference"),
    ]
    detail_metrics = metrics[:8]
    bridge_metrics = metrics[8:]
    rows = [
        {"metric": label, "amount": float(detail[column].sum())}
        for label, column in detail_metrics
    ]
    rows.extend(
        {
            "metric": label,
            "amount": float(profit_bridge[column].sum()),
        }
        for label, column in bridge_metrics
    )
    return pd.DataFrame(rows)
