"""运行完全脱敏的预算差异演示。"""

from __future__ import annotations

import argparse

from .reporting import generate_demo_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="生成完全脱敏的预算差异与滚动预测演示")
    parser.add_argument("--output-dir", default="demo_output", help="演示文件输出目录")
    args = parser.parse_args()
    artifacts = generate_demo_artifacts(args.output_dir)
    result = artifacts.variance
    forecast = artifacts.forecast

    print("预算差异分析演示（全部数据均为合成数据）")
    print(f"预算记录：{len(artifacts.dataset.budget)}")
    print(f"实际记录：{len(artifacts.dataset.actual)}")
    print(f"情景数量：{len(artifacts.dataset.assumptions)}")
    print()
    print(result.summary.to_string(index=False, formatters={"amount": "{:,.2f}".format}))
    print()
    print(f"利润桥勾稽差异：{result.reconciliation_difference:,.8f}")
    print()
    print(f"实际数据截至：{forecast.actual_through:%Y-%m}")
    print(forecast.summary.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))
    print()
    print(f"合成输入：{artifacts.input_path.resolve()}")
    print(f"管理报告：{artifacts.report_path.resolve()}")


if __name__ == "__main__":
    main()
