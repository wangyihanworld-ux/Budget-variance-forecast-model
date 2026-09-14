"""预算差异分析与滚动预测模型。"""

from .synthetic import SyntheticDataset, build_synthetic_dataset
from .forecast import ForecastResult, build_rolling_forecast
from .variance import VarianceResult, calculate_variances

__version__ = "0.1.0"

__all__ = [
    "SyntheticDataset",
    "ForecastResult",
    "VarianceResult",
    "build_synthetic_dataset",
    "build_rolling_forecast",
    "calculate_variances",
]
