import json
import tempfile
import unittest
from pathlib import Path

from agnostik.objections.bundle import ExportError, load_export, load_exports

VIZ_HTML = """<!doctype html><html><body><script>
const DATA = [
  {"id": "src.egfr.binding-sites", "kind": "fact", "value": "4", "depth": 0, "inputs": [],
   "module": "src", "evidence": [{"doc": "uniprot-EGFR", "quotes": ["UNIPROT binding_sites=4"],
   "explanation": "binding sites; brackets ] and ; inside a quote", "verified": true, "status": "verified"}]},
  {"id": "egfr-promising", "kind": "calc", "value": "True", "depth": 2,
   "inputs": [{"name": "src.egfr.binding-sites", "inProbe": true}], "module": "",
   "evidence": [{"status": "derived"}]}
];
const LAYERS = {"layers": [], "edges": [{"source": "src.egfr.binding-sites", "target": "egfr-promising", "type": "uses"}]};
const TAINT_DATA = {"sources": ["src.egfr.binding-sites"], "tainted": ["egfr-promising"],
                    "reasons": {"egfr-promising": "derived from unverified"}};
</script></body></html>"""


class LoadExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _write(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_parses_viz_html(self) -> None:
        bundle = load_export(self._write("viz.html", VIZ_HTML))

        self.assertEqual(len(bundle), 2)
        self.assertEqual(bundle.globals_found, ["DATA", "LAYERS", "TAINT_DATA"])
        self.assertEqual(bundle.tainted, {"egfr-promising"})

    def test_quote_containing_brackets_survives(self) -> None:
        """The literal scanner is string-aware; a lazy regex would truncate here."""
        bundle = load_export(self._write("viz.html", VIZ_HTML))
        node = bundle.get("src.egfr.binding-sites")

        assert node is not None
        self.assertIn("brackets ] and ; inside a quote", node.evidence[0].explanation)

    def test_inputs_normalise_to_names(self) -> None:
        bundle = load_export(self._write("viz.html", VIZ_HTML))

        self.assertEqual(bundle.get("egfr-promising").inputs, ["src.egfr.binding-sites"])
        self.assertEqual(bundle.consumers("src.egfr.binding-sites"), ["egfr-promising"])

    def test_accepts_plain_json_array_and_object(self) -> None:
        items = [{"id": "a", "kind": "fact", "value": "1", "inputs": [], "evidence": []}]
        as_array = load_export(self._write("a.json", json.dumps(items)))
        as_object = load_export(self._write("b.json", json.dumps({"DATA": items})))

        self.assertEqual(len(as_array), 1)
        self.assertEqual(len(as_object), 1)

    def test_rejects_files_without_globals(self) -> None:
        with self.assertRaises(ExportError):
            load_export(self._write("plain.html", "<html><body>no data here</body></html>"))
        with self.assertRaises(ExportError):
            load_export(self._write("other.json", json.dumps({"unrelated": 1})))

    def test_missing_file_is_an_export_error(self) -> None:
        with self.assertRaises(ExportError):
            load_export(self.dir / "nope.html")

    def test_merge_adds_nodes_without_dropping_evidence(self) -> None:
        second = json.dumps(
            {
                "DATA": [
                    {"id": "egfr-promising", "kind": "calc", "value": "True", "inputs": [], "evidence": []},
                    {"id": "wrn-promising", "kind": "calc", "value": "False", "inputs": [], "evidence": []},
                ]
            }
        )
        merged = load_exports([self._write("viz.html", VIZ_HTML), self._write("more.json", second)])

        self.assertEqual(len(merged), 3)
        self.assertEqual(merged.get("egfr-promising").inputs, ["src.egfr.binding-sites"])
        self.assertTrue(merged.get("src.egfr.binding-sites").evidence)


if __name__ == "__main__":
    unittest.main()
