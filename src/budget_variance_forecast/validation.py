"""预算与实际数据契约校验。"""

from __future__ import annotations

import pandas as pd

from .synthetic import KEY_COLUMNS


BUDGET_VALUE_COLUMNS = [
    "budget_quantity",
    "budget_unit_price",
    "budget_unit_variable_cost",
    "budget_fixed_expense",
]
ACTUAL_VALUE_COLUMNS = [
    "actual_quantity",
    "actual_revenue",
    "actual_variable_cost",
    "actual_fixed_expense",
]


class DataValidationError(ValueError):
    """输入数据不满足预算分析的数据契约。"""


def normalize_and_validate_inputs(
    budget: pd.DataFrame, actual: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回经过类型标准化且满足数据契约的预算表和实际表副本。"""

    _require_columns(budget, KEY_COLUMNS + BUDGET_VALUE_COLUMNS, "预算表")
    _require_columns(actual, KEY_COLUMNS + ACTUAL_VALUE_COLUMNS, "实际表")
    if budget.empty or actual.empty:
        empty_label = "预算表" if budget.empty else "实际表"
        raise DataValidationError(f"{empty_label}不能为空")
    budget = budget.copy()
    actual = actual.copy()
    _normalize_frame(budget, BUDGET_VALUE_COLUMNS, "预算表")
    _normalize_frame(actual, ACTUAL_VALUE_COLUMNS, "实际表")
    _require_unique_keys(budget, "预算表")
    _require_unique_keys(actual, "实际表")
    _require_nonnegative(budget, BUDGET_VALUE_COLUMNS, "预算表")
    _require_nonnegative(actual, ACTUAL_VALUE_COLUMNS, "实际表")

    budget_keys = set(map(tuple, budget[KEY_COLUMNS].itertuples(index=False, name=None)))
    actual_keys = set(map(tuple, actual[KEY_COLUMNS].itertuples(index=False, name=None)))
    missing_budget = actual_keys - budget_keys
    if missing_budget:
        sample = sorted(missing_budget, key=str)[0]
        raise DataValidationError(f"实际表存在找不到预算的记录，例如：{sample}")
    return budget, actual


def validate_inputs(budget: pd.DataFrame, actual: pd.DataFrame) -> None:
    """校验字段、主键、数值范围和预算实际键的一致性。"""

    normalize_and_validate_inputs(budget, actual)


def _normalize_frame(frame: pd.DataFrame, value_columns: list[str], label: str) -> None:
    business_keys = frame[["business_unit", "product"]]
    blank_keys = business_keys.isna() | business_keys.astype("string").apply(
        lambda column: column.str.strip().eq("")
    )
    if blank_keys.any().any():
        raise DataValidationError(f"{label}事业部和产品不能为空")
    months = pd.to_datetime(frame["month"], errors="coerce")
    if months.isna().any():
        raise DataValidationError(f"{label}月份必须是有效日期")
    frame["month"] = months.dt.to_period("M").dt.to_timestamp()
    frame[value_columns] = frame[value_columns].apply(pd.to_numeric, errors="coerce")


def _require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise DataValidationError(f"{label}缺少字段：{', '.join(missing)}")


def _require_unique_keys(frame: pd.DataFrame, label: str) -> None:
    duplicated = frame.duplicated(KEY_COLUMNS, keep=False)
    if duplicated.any():
        sample = tuple(frame.loc[duplicated, KEY_COLUMNS].iloc[0])
        raise DataValidationError(f"{label}主键重复，例如：{sample}")


def _require_nonnegative(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    numeric = frame[columns].apply(pd.to_numeric, errors="coerce")
    invalid = numeric.isna() | (numeric < 0)
    if invalid.any().any():
        row_index, column_index = next(zip(*invalid.to_numpy().nonzero()))
        column = columns[column_index]
        raise DataValidationError(f"{label}字段 {column} 存在空值、非数字或负数（行 {row_index + 2}）")
