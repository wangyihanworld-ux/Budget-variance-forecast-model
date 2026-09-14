"""运行完全脱敏的预算差异演示。"""

from __future__ import annotations

from .synthetic import build_synthetic_dataset
from .variance import calculate_variances


def main() -> None:
    dataset = build_synthetic_dataset(actual_months=6)
    result = calculate_variances(dataset.budget, dataset.actual)

    print("预算差异分析演示（全部数据均为合成数据）")
    print(f"预算记录：{len(dataset.budget)}")
    print(f"实际记录：{len(dataset.actual)}")
    print(f"情景数量：{len(dataset.assumptions)}")
    print()
    print(result.summary.to_string(index=False, formatters={"amount": "{:,.2f}".format}))
    print()
    print(f"利润桥勾稽差异：{result.reconciliation_difference:,.8f}")


if __name__ == "__main__":
    main()
