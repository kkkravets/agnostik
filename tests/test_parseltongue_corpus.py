import json
from pathlib import Path
import tempfile
import unittest

from parseltongue import System
from parseltongue.core import load_source

from agnostik.candidates import PRESELECTED_CANDIDATES
from agnostik.objections.bundle import load_export
from agnostik.objections.targets import discover
from agnostik.parseltongue_corpus import (
    TargetResult,
    build_stage4_export,
    discover_sources,
    select_target_sources,
    target_query,
    validate_stage4_export,
)


def target_system(target):
    system = System(overridable=True)
    document = f"{target} has therapeutic evidence in colon adenocarcinoma. PMID 12345678."
    doc_name = f"PMC-{target}"
    system.register_document(doc_name, document)
    load_source(
        system,
        f'''(fact {target.lower()}-paper true
            :evidence (evidence "{doc_name}"
                :quotes ("{target} has therapeutic evidence in colon adenocarcinoma.")
                :explanation "PMID 12345678"))
        (derive {target.lower()}-verdict {target.lower()}-paper
            :using ({target.lower()}-paper))''',
    )
    return system


class Stage3SourceTests(unittest.TestCase):
    def test_selects_target_specific_articles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "PMC2.txt").write_text("KRAS once", encoding="utf-8")
            (root / "PMC1.txt").write_text("KRAS KRAS KRAS", encoding="utf-8")
            (root / "PMC3.txt").write_text("EGFR only", encoding="utf-8")
            selected = select_target_sources(
                discover_sources(root), "KRAS", max_documents=2, max_chars=1_000
            )
            self.assertEqual([path.name for path in selected], ["PMC1.txt", "PMC2.txt"])

    def test_query_requires_exact_boolean_verdict(self):
        query = target_query("EGFR", "colon adenocarcinoma", "COAD")
        self.assertIn("egfr-verdict", query)
        self.assertIn("Boolean", query)
        self.assertIn("verbatim", query)
        self.assertIn(":using", query)


class Stage3ExportTests(unittest.TestCase):
    def test_export_is_directly_consumable_by_stage4(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = [
                TargetResult(
                    target,
                    target_system(target),
                    f"{target.lower()}-verdict",
                    (f"PMC-{target}.txt",),
                    root / target.lower(),
                )
                for target in PRESELECTED_CANDIDATES
            ]
            export_path = root / "stage3-export.json"
            export_path.write_text(
                json.dumps(build_stage4_export(results), default=str), encoding="utf-8"
            )
            validate_stage4_export(export_path, PRESELECTED_CANDIDATES)
            views = discover(load_export(export_path), list(PRESELECTED_CANDIDATES))
            self.assertEqual([view.symbol for view in views], list(PRESELECTED_CANDIDATES))
            self.assertTrue(all(view.verdict is True for view in views))
            self.assertTrue(all(any(fact.is_grounded for fact in view.facts) for view in views))
            payload = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(payload), {"DATA", "STRUCTURE_DATA", "LAYERS", "TAINT_DATA"}
            )


if __name__ == "__main__":
    unittest.main()
