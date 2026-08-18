import tempfile
import unittest
from pathlib import Path

from agnostik.consistency.engine import EngineResult, parse_items
from agnostik.consistency.generate import TargetFacts, build_system
from agnostik.consistency.report import adjudicate

SCREEN_OUTPUT = """
ScreenItem(name='src.checks.egfr-support-base', category='issue', type='diff_divergence', kind=<DirectiveKind.DIFF: 'diff'>, loc='src/checks.pltg:6:1', detail=DiffResult(name='src.checks.egfr-support-base', replace='src.dossier_egfr.cited-records', with_='src.registry_egfr.subject-records', value_a=8, value_b=2, divergences={'src.checks.egfr-base-intact': [False, True], 'src.checks.proven-verdicts': [5, 6]}))
ScreenItem(name='src.checks.kras-verdict-proven', category='issue', type='potential_fabrication', kind=<DirectiveKind.DERIVE: 'derive'>, loc='src/checks.pltg:223:1', detail='src.checks.kras-verdict-proven')
""".strip()


def facts(symbol="EGFR", verdict=True, cited=8, subject=2, off_target=0, retracted=0, unresolved=0):
    return TargetFacts(
        symbol=symbol,
        verdict=verdict,
        verdict_node=f"{symbol.lower()}-promising",
        cited_records=cited,
        subject_records=subject,
        weak_attribution=cited - subject - off_target,
        off_target=off_target,
        retracted=retracted,
        unresolved=unresolved,
        records=[
            {
                "source_type": "pmid",
                "source_id": "42345355",
                "node_id": f"src.{symbol.lower()}.paper-42345355",
                "quote": "TITLE: A paper",
                "status": "weak-attribution",
                "gene_role": "abstract",
                "indication_role": "title",
                "resolves": True,
                "reason": "mentioned only in the abstract",
            }
        ],
    )


class ParseItemsTests(unittest.TestCase):
    def test_parses_enum_kind(self) -> None:
        """pg-bench prints kind as an enum repr, not a plain string."""
        items = parse_items(SCREEN_OUTPUT)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].kind, "diff")
        self.assertEqual(items[1].kind, "derive")

    def test_extracts_both_sides_of_a_divergence(self) -> None:
        item = parse_items(SCREEN_OUTPUT)[0]

        self.assertTrue(item.is_divergence)
        self.assertEqual(item.replace, "src.dossier_egfr.cited-records")
        self.assertEqual(item.with_, "src.registry_egfr.subject-records")
        self.assertEqual((item.value_a, item.value_b), ("8", "2"))
        self.assertEqual(item.consequences["src.checks.egfr-base-intact"], ["False", "True"])

    def test_short_name_drops_the_namespace(self) -> None:
        self.assertEqual(parse_items(SCREEN_OUTPUT)[1].short_name, "kras-verdict-proven")

    def test_empty_output_yields_nothing(self) -> None:
        self.assertEqual(parse_items(""), [])


class AdjudicationTests(unittest.TestCase):
    def test_narrowed_base_still_counts_as_proven(self) -> None:
        engine = EngineResult(values={"src.checks.egfr-verdict-proven": "True"})
        row = adjudicate([facts()], engine)[0]

        self.assertTrue(row["verdict_proven"])
        self.assertFalse(row["support_base_intact"])
        self.assertEqual(row["base_narrowed_by"], 6)
        self.assertIn("narrowed base", row["standing"])

    def test_off_target_record_makes_the_verdict_unproven(self) -> None:
        engine = EngineResult(values={"src.checks.kras-verdict-proven": "False"})
        row = adjudicate([facts(symbol="KRAS", off_target=1)], engine)[0]

        self.assertFalse(row["verdict_proven"])
        self.assertIn("never name KRAS", row["standing"])

    def test_engine_silence_is_not_read_as_proof(self) -> None:
        row = adjudicate([facts()], EngineResult())[0]

        self.assertFalse(row["verdict_proven"])

    def test_failed_checks_are_attached_to_their_target(self) -> None:
        engine = EngineResult(
            issues=parse_items(SCREEN_OUTPUT),
            values={"src.checks.egfr-verdict-proven": "True"},
        )
        row = adjudicate([facts()], engine)[0]

        self.assertEqual(len(row["failed_checks"]), 1)
        self.assertEqual(row["failed_checks"][0]["check"], "egfr-support-base")


class BuildSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_writes_a_complete_system(self) -> None:
        entry = build_system([facts(), facts(symbol="KRAS", off_target=1)], ["export.html"], self.root)

        self.assertTrue(entry.exists())
        for name in ("src/rules.pltg", "src/checks.pltg", "src/dossier_egfr.pltg",
                     "src/registry_egfr.pltg", "docs/charter.md", "docs/dossier-EGFR.txt"):
            self.assertTrue((self.root / name).exists(), name)

    def test_dossier_facts_quote_their_document(self) -> None:
        build_system([facts()], ["export.html"], self.root)
        module = (self.root / "src/dossier_egfr.pltg").read_text()
        document = (self.root / "docs/dossier-EGFR.txt").read_text()

        for quote in ("DOSSIER cited_records=8", "DOSSIER SUPPORTS pmid 42345355"):
            self.assertIn(quote, module)
            self.assertIn(quote, document)  # the engine verifies this literally

    def test_every_target_gets_the_four_comparisons(self) -> None:
        build_system([facts()], ["export.html"], self.root)
        checks = (self.root / "src/checks.pltg").read_text()

        for name in ("egfr-support-base", "egfr-off-target", "egfr-retracted", "egfr-unresolved"):
            self.assertIn(f"(diff {name}", checks)

    def test_sound_records_produce_no_diff(self) -> None:
        clean = facts()
        clean.records[0]["status"] = "sound"
        build_system([clean], ["export.html"], self.root)

        self.assertNotIn("supports-pmid-42345355)", (self.root / "src/checks.pltg").read_text())


if __name__ == "__main__":
    unittest.main()
