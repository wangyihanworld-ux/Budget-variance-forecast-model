"""运行完全脱敏的预算差异演示。"""

from __future__ import annotations

from .synthetic import build_synthetic_dataset
from .forecast import build_rolling_forecast
from .variance import calculate_variances


def main() -> None:
    dataset = build_synthetic_dataset(actual_months=6)
    result = calculate_variances(dataset.budget, dataset.actual)
    forecast = build_rolling_forecast(
        dataset.budget, dataset.actual, dataset.assumptions
    )

    print("预算差异分析演示（全部数据均为合成数据）")
    print(f"预算记录：{len(dataset.budget)}")
    print(f"实际记录：{len(dataset.actual)}")
    print(f"情景数量：{len(dataset.assumptions)}")
    print()
    print(result.summary.to_string(index=False, formatters={"amount": "{:,.2f}".format}))
    print()
    print(f"利润桥勾稽差异：{result.reconciliation_difference:,.8f}")
    print()
    print(f"实际数据截至：{forecast.actual_through:%Y-%m}")
    print(forecast.summary.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))


if __name__ == "__main__":
    main()
