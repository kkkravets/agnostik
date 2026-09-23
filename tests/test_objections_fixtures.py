"""Integration coverage for the checked-in objection example (no model/API calls)."""

from pathlib import Path
import sys
import unittest

from parseltongue.core import Evidence, Symbol, load_pltg

from agnostik.objections.backtrace import ledger
from agnostik.objections.bundle import load_exports
from agnostik.objections.targets import discover


FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "objection-workflow" / "fixtures"
EXPECTED_VERDICTS = {
    "EGFR": True,
    "ERBB2": True,
    "KRAS": True,
    "MYC": False,
    "WRN": True,
    "PRMT5": False,
}


class ObjectionFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exercise the real loader, including relative load-document/import paths.
        # Loading only the HTML would never detect a missing source TXT file.
        try:
            cls.system = load_pltg(str(FIXTURES / "shortlist.pltg"))
        except Exception as exc:
            if sys.flags.utf8_mode or "codec can't decode" not in str(exc):
                raise
            raise RuntimeError(
                "Parseltongue reads load-document sources with the locale encoding, "
                "so this fixture's UTF-8 documents fail on Windows. Re-run with "
                "PYTHONUTF8=1 (see README)."
            ) from exc
        cls.bundle = load_exports([
            FIXTURES / "candidate-dossiers.html",
            FIXTURES / "candidate-verdicts.html",
        ])

    def test_registered_documents_match_fixture_files(self):
        expected = {"charter": FIXTURES / "docs" / "charter.md"}
        for target in EXPECTED_VERDICTS:
            for provider in ("pubmed", "trials", "uniprot"):
                name = f"{provider}-{target}"
                expected[name] = FIXTURES / "docs" / f"{name}.txt"

        self.assertEqual(set(self.system.documents), set(expected))
        for name, path in expected.items():
            with self.subTest(document=name):
                self.assertEqual(
                    self.system.documents[name], path.read_text(encoding="utf-8")
                )

    def test_exported_quotes_match_loaded_system_and_documents(self):
        sources = {**self.system.engine.facts, **self.system.engine.axioms}
        quoted_nodes = set()
        for node in self.bundle.nodes.values():
            for evidence in node.evidence:
                if not evidence.quotes:
                    continue
                with self.subTest(node=node.id, document=evidence.doc):
                    self.assertIn(node.id, sources)
                    origin = sources[node.id].origin
                    self.assertIsInstance(origin, Evidence)
                    self.assertEqual(evidence.doc, origin.document)
                    self.assertEqual(evidence.quotes, list(origin.quotes))
                    self.assertTrue(origin.verified)
                    self.assertTrue(evidence.verified)
                    self.assertIn(evidence.doc, self.system.documents)
                    for quote in evidence.quotes:
                        self.assertIn(quote, self.system.documents[evidence.doc])
                    quoted_nodes.add(node.id)

        # Require coverage of all grounded facts/rules, not just whatever happens
        # to remain in the exports if a fixture is accidentally truncated.
        expected = {
            name for name, fact in sources.items()
            if isinstance(fact.origin, Evidence) and fact.origin.quotes
        }
        self.assertTrue(expected)
        self.assertEqual(quoted_nodes, expected)

    def test_exported_verdicts_agree_with_fixture_system(self):
        views = discover(self.bundle, list(EXPECTED_VERDICTS))
        self.assertEqual(len(views), len(EXPECTED_VERDICTS))
        for view in views:
            with self.subTest(target=view.symbol):
                self.assertFalse(view.missing)
                self.assertIsNotNone(view.verdict_node)
                self.assertEqual(view.verdict_node.id, f"{view.symbol.lower()}-promising")
                self.assertIs(view.verdict, EXPECTED_VERDICTS[view.symbol])
                self.assertEqual(
                    self.system.evaluate(Symbol(view.verdict_node.id)), view.verdict
                )
                evidence = ledger(self.bundle, [view.verdict_node.id])
                self.assertGreater(len(evidence), 0)
                self.assertIn("charter", {c.doc for c in evidence})
                self.assertIn(f"pubmed-{view.symbol}", {c.doc for c in evidence})

    def test_egfr_ledger_links_papers_but_not_aggregate_counters(self):
        evidence = ledger(
            self.bundle,
            ["egfr-promising"],
            secondary_roots=["src.egfr.dossier-anchored"],
        )
        by_node = {c.node_id: c for c in evidence}
        paper = by_node["src.egfr.paper-42492133"]
        self.assertEqual(paper.doc, "pubmed-EGFR")
        self.assertEqual(paper.source_type, "pmid")
        self.assertEqual(paper.source_id, "42492133")
        self.assertEqual(paper.url, "https://pubmed.ncbi.nlm.nih.gov/42492133/")

        for node, doc in (
            ("src.egfr.in-vivo-hits", "pubmed-EGFR"),
            ("src.egfr.trials-recruiting", "trials-EGFR"),
        ):
            with self.subTest(counter=node):
                counter = by_node[node]
                self.assertEqual(counter.doc, doc)
                self.assertEqual(counter.source_type, "document")
                self.assertEqual(counter.source_id, "")
                self.assertEqual(counter.url, "")


if __name__ == "__main__":
    unittest.main()
