import unittest

from agnostik.candidates import PRESELECTED_CANDIDATES, select_candidates


class SelectCandidatesTests(unittest.TestCase):
    def test_returns_fixed_v1_panel(self) -> None:
        selection = select_candidates("BRCA")

        self.assertEqual(selection.tumour_type, "BRCA")
        self.assertEqual(
            selection.candidates,
            ("EGFR", "ERBB2", "KRAS", "MYC", "WRN", "PRMT5"),
        )
        self.assertIs(selection.candidates, PRESELECTED_CANDIDATES)

    def test_normalizes_tumour_type(self) -> None:
        self.assertEqual(select_candidates("  luad ").tumour_type, "LUAD")

    def test_rejects_invalid_tumour_type(self) -> None:
        for value in ("", " ", "breast cancer", "BRCA!"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    select_candidates(value)


if __name__ == "__main__":
    unittest.main()

