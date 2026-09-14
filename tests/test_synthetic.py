import unittest

from budget_variance_forecast.synthetic import build_synthetic_dataset


class SyntheticDatasetTest(unittest.TestCase):
    def test_dataset_is_repeatable_and_complete(self) -> None:
        first = build_synthetic_dataset(actual_months=6)
        second = build_synthetic_dataset(actual_months=6)

        self.assertEqual(len(first.budget), 48)
        self.assertEqual(len(first.actual), 24)
        self.assertEqual(len(first.assumptions), 3)
        self.assertTrue(first.budget.equals(second.budget))
        self.assertTrue(first.actual.equals(second.actual))

    def test_actual_month_range_is_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "1 到 12"):
            build_synthetic_dataset(actual_months=0)


if __name__ == "__main__":
    unittest.main()
