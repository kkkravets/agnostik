import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from agnostik.cli import main


def _http(url, payload=None):
    if "gdc.cancer.gov" in url:
        return {"data": {"name": "Rectum Adenocarcinoma"}}
    query = payload["query"]
    if "SearchDisease" in query:
        return {"data": {"search": {"hits": [{"id": "MONDO_0002169", "name": "rectum adenocarcinoma", "score": 500.0}]}}}
    if "DiseaseContext" in query:
        area = [{"id": "EFO_0010282"}]
        parent = {"id": "MONDO_P", "name": "rectal carcinoma", "therapeuticAreas": area}
        return {"data": {"disease": {"name": "rectum adenocarcinoma", "therapeuticAreas": area, "parents": [parent]}}}
    rows = [
        {"score": 0.9, "target": {"id": "E1", "approvedSymbol": "TP53", "approvedName": "tumor protein p53", "biotype": "protein_coding"}},
        {"score": 0.8, "target": {"id": "E2", "approvedSymbol": "MIR1", "approvedName": "microRNA 1", "biotype": "miRNA"}},
        {"score": 0.7, "target": {"id": "E3", "approvedSymbol": "APC", "approvedName": "APC regulator", "biotype": "protein_coding"}},
    ]
    return {"data": {"disease": {"name": "rectum adenocarcinoma", "associatedTargets": {"count": 3, "rows": rows}}}}


class CliTests(unittest.TestCase):
    def run_main(self, argv, http=_http):
        output = StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(StringIO()):
            exit_code = main(argv, http=http)
        return exit_code, output.getvalue()

    def test_fixed_panel_json_output(self) -> None:
        exit_code, output = self.run_main(["brca", "--fixed-panel", "--json"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(output),
            {
                "tumour_type": "BRCA",
                "candidates": ["EGFR", "ERBB2", "KRAS", "MYC", "WRN", "PRMT5"],
            },
        )

    def test_fixed_panel_rejects_disease_options(self) -> None:
        with self.assertRaises(SystemExit):
            self.run_main(["READ", "--fixed-panel", "--disease-id", "MONDO_1"])

    def test_discovers_and_writes_shortlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            exit_code, output = self.run_main(["read", "--out-dir", str(out_dir), "--json"])

            payload = json.loads(output)
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["candidates"], ["TP53", "APC"])  # the miRNA is skipped
            self.assertEqual(payload["disease"], {"id": "MONDO_0002169", "name": "rectum adenocarcinoma"})
            self.assertEqual(payload["parents"], [{"id": "MONDO_P", "name": "rectal carcinoma"}])
            self.assertEqual((out_dir / "symbols.txt").read_text(), "TP53\nAPC\n")
            self.assertTrue((out_dir / "candidates.csv").is_file())
            self.assertEqual(json.loads((out_dir / "resolution.json").read_text())["disease_id"], "MONDO_0002169")

    def test_no_parents_ranks_the_disease_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, output = self.run_main(["read", "--no-parents", "--out-dir", tmp, "--json"])

            self.assertEqual(json.loads(output)["parents"], [])

    def test_unknown_tumour_code_is_an_error(self) -> None:
        with self.assertRaises(SystemExit):
            self.run_main(["ZZZ"], http=lambda url, payload=None: {"message": "TCGA-ZZZ not found"})


if __name__ == "__main__":
    unittest.main()
