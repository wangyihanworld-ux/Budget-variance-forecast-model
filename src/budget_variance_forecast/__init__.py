"""预算差异分析与滚动预测模型。"""

from .synthetic import SyntheticDataset, build_synthetic_dataset
from .variance import VarianceResult, calculate_variances

__version__ = "0.1.0"

__all__ = [
    "SyntheticDataset",
    "VarianceResult",
    "build_synthetic_dataset",
    "calculate_variances",
]
