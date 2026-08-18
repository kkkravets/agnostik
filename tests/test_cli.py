import contextlib
from io import StringIO
import json
import unittest

from agnostik.cli import main


class CliTests(unittest.TestCase):
    def test_json_output(self) -> None:
        output = StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main(["brca", "--json"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "tumour_type": "BRCA",
                "candidates": ["EGFR", "ERBB2", "KRAS", "MYC", "WRN", "PRMT5"],
            },
        )


if __name__ == "__main__":
    unittest.main()
