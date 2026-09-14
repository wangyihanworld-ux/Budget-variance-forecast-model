"""生成完全合成、可重复的预算与实际数据。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


KEY_COLUMNS = ["month", "business_unit", "product"]


@dataclass(frozen=True)
class SyntheticDataset:
    """项目演示所需的预算、实际和预测假设。"""

    budget: pd.DataFrame
    actual: pd.DataFrame
    assumptions: pd.DataFrame


PRODUCTS = (
    ("消费事业部", "标准版", 1_000, 120.0, 68.0),
    ("消费事业部", "专业版", 650, 180.0, 102.0),
    ("企业事业部", "标准方案", 420, 360.0, 205.0),
    ("企业事业部", "高级方案", 260, 520.0, 288.0),
)


def build_synthetic_dataset(actual_months: int = 6) -> SyntheticDataset:
    """构造 2026 年预算以及指定已发生月份的实际数据。

    数据中的事业部、产品、数量、价格和费用均为虚构值。生成过程不读取
    外部文件、网络、数据库或环境变量，因此相同参数始终得到相同结果。
    """

    if not 1 <= actual_months <= 12:
        raise ValueError("actual_months 必须在 1 到 12 之间")

    budget_rows: list[dict[str, object]] = []
    actual_rows: list[dict[str, object]] = []
    quantity_factors = (0.94, 1.03, 0.98, 1.08, 1.01, 0.96)
    price_factors = (1.00, 0.99, 1.02, 1.01)
    cost_factors = (1.02, 1.01, 1.04, 0.99)

    for month_number in range(1, 13):
        month = pd.Timestamp(2026, month_number, 1)
        seasonality = 1 + (month_number - 6.5) * 0.012
        for product_index, (unit, product, base_qty, price, unit_cost) in enumerate(PRODUCTS):
            budget_quantity = round(base_qty * seasonality)
            fixed_expense = 32_000.0 if unit == "消费事业部" else 46_000.0
            budget_rows.append(
                {
                    "month": month,
                    "business_unit": unit,
                    "product": product,
                    "budget_quantity": float(budget_quantity),
                    "budget_unit_price": price,
                    "budget_unit_variable_cost": unit_cost,
                    "budget_fixed_expense": fixed_expense / 2,
                }
            )

            if month_number <= actual_months:
                quantity_factor = quantity_factors[(month_number + product_index - 1) % len(quantity_factors)]
                actual_quantity = round(budget_quantity * quantity_factor)
                actual_price = price * price_factors[product_index]
                actual_unit_cost = unit_cost * cost_factors[product_index]
                expense_factor = 1.03 if month_number in (2, 5) else 0.99
                actual_rows.append(
                    {
                        "month": month,
                        "business_unit": unit,
                        "product": product,
                        "actual_quantity": float(actual_quantity),
                        "actual_revenue": actual_quantity * actual_price,
                        "actual_variable_cost": actual_quantity * actual_unit_cost,
                        "actual_fixed_expense": fixed_expense * expense_factor / 2,
                    }
                )

    assumptions = pd.DataFrame(
        [
            ["谨慎", 0.97, 0.99, 1.03, 1.02],
            ["基准", 1.00, 1.00, 1.00, 1.00],
            ["乐观", 1.06, 1.01, 0.99, 1.00],
        ],
        columns=[
            "scenario",
            "quantity_factor",
            "price_factor",
            "unit_cost_factor",
            "fixed_expense_factor",
        ],
    )
    return SyntheticDataset(
        budget=pd.DataFrame(budget_rows),
        actual=pd.DataFrame(actual_rows),
        assumptions=assumptions,
    )
