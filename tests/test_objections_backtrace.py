import unittest

from agnostik.objections.backtrace import closure, derivation_path, ledger
from agnostik.objections.bundle import Bundle, Evidence, Node


def node(node_id, kind="fact", value="1", inputs=None, evidence=None):
    return Node(id=node_id, kind=kind, value=value, inputs=inputs or [], evidence=evidence or [])


def evidence(doc, quote, explanation="", before="", after="", verified=True, status="verified"):
    return Evidence(
        doc=doc,
        quotes=[quote],
        quote_contexts={quote: {"before": before, "after": after}},
        explanation=explanation,
        verified=verified,
        status=status,
    )


class BacktraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = Bundle(
            nodes={
                n.id: n
                for n in [
                    node(
                        "src.egfr.trials-recruiting",
                        value="1",
                        evidence=[
                            evidence(
                                "trials-EGFR",
                                "TRIALS recruiting=1",
                                explanation="Trials currently recruiting",
                                before="NCT06940778 | ACTIVE_NOT_RECRUITING",
                                after="NCT01234567 | RECRUITING",
                            )
                        ],
                    ),
                    node(
                        "src.egfr.paper-42345355",
                        value="true",
                        evidence=[
                            evidence(
                                "pubmed-EGFR",
                                "TITLE: Advances in SEC61G research",
                                explanation="PMID 42345355 (crc query, Cancer Biol Ther 2026)",
                            )
                        ],
                    ),
                    node(
                        "src.egfr.binding-sites",
                        value="4",
                        evidence=[evidence("uniprot-EGFR", "UNIPROT binding_sites=4", explanation="UniProt P00533")],
                    ),
                    node(
                        "src.egfr.clinical-traction",
                        kind="calc",
                        value="True",
                        inputs=["src.egfr.trials-recruiting"],
                        evidence=[Evidence(status="derived")],
                    ),
                    node(
                        "egfr-promising",
                        kind="calc",
                        value="True",
                        inputs=["src.egfr.clinical-traction"],
                        evidence=[Evidence(status="derived")],
                    ),
                    node(
                        "src.egfr.dossier-anchored",
                        kind="calc",
                        value="True",
                        inputs=["src.egfr.paper-42345355"],
                        evidence=[Evidence(status="derived")],
                    ),
                ]
            }
        )

    def test_closure_walks_inputs_with_hop_counts(self) -> None:
        chain = dict((n.id, hops) for n, hops in closure(self.bundle, ["egfr-promising"]))

        self.assertEqual(chain["egfr-promising"], 0)
        self.assertEqual(chain["src.egfr.clinical-traction"], 1)
        self.assertEqual(chain["src.egfr.trials-recruiting"], 2)
        self.assertNotIn("src.egfr.paper-42345355", chain)

    def test_aggregate_counter_does_not_inherit_a_neighbouring_nct(self) -> None:
        """A counter sits next to arbitrary trial records; it must stay a document citation."""
        led = ledger(self.bundle, ["egfr-promising"])
        counter = next(c for c in led if c.node_id == "src.egfr.trials-recruiting")

        self.assertEqual(counter.source_type, "document")
        self.assertEqual(counter.source_id, "")

    def test_pmid_comes_from_the_explanation(self) -> None:
        led = ledger(self.bundle, ["src.egfr.dossier-anchored"])
        paper = next(c for c in led if c.node_id == "src.egfr.paper-42345355")

        self.assertEqual(paper.source_type, "pmid")
        self.assertEqual(paper.source_id, "42345355")
        self.assertEqual(paper.url, "https://pubmed.ncbi.nlm.nih.gov/42345355/")

    def test_uniprot_accession_is_recognised(self) -> None:
        led = ledger(self.bundle, ["src.egfr.binding-sites"])

        self.assertEqual(led.citations[0].source_type, "uniprot")
        self.assertEqual(led.citations[0].source_id, "P00533")

    def test_keys_are_sequential_and_verdict_proximal_first(self) -> None:
        led = ledger(
            self.bundle,
            ["egfr-promising"],
            secondary_roots=["src.egfr.dossier-anchored"],
        )

        self.assertEqual(led.keys[: len(led.keys)], [f"E{i}" for i in range(1, len(led.keys) + 1)])
        self.assertEqual(led.citations[0].node_id, "src.egfr.trials-recruiting")
        self.assertTrue(led.citations[-1].hops > led.citations[0].hops)
        self.assertIsNotNone(led.by_key("E1"))
        self.assertIsNone(led.by_key("E99"))

    def test_derivation_path_reaches_the_evidence_node(self) -> None:
        path = derivation_path(self.bundle, "egfr-promising", "src.egfr.trials-recruiting")

        self.assertEqual(
            path,
            ["egfr-promising", "src.egfr.clinical-traction", "src.egfr.trials-recruiting"],
        )

    def test_ledger_limit_is_respected(self) -> None:
        led = ledger(self.bundle, ["egfr-promising"], secondary_roots=["src.egfr.dossier-anchored"], limit=1)

        self.assertEqual(len(led), 1)


if __name__ == "__main__":
    unittest.main()
