import unittest

from agnostik.objections.backtrace import Citation, Ledger
from agnostik.objections.verify import split_sentences, verify


def make_ledger() -> Ledger:
    return Ledger(
        citations=[
            Citation(
                key="E1",
                node_id="src.egfr.trials-late-phase",
                node_kind="fact",
                node_value="0",
                doc="trials-EGFR",
                quote="TRIALS late_phase=0",
                explanation="Trials in phase 3 or phase 4",
                verified=True,
            ),
            Citation(
                key="E2",
                node_id="src.egfr.paper-42345355",
                node_kind="fact",
                node_value="true",
                doc="pubmed-EGFR",
                quote="TITLE: Advances in SEC61G research",
                explanation="PMID 42345355",
                source_type="pmid",
                source_id="42345355",
                url="https://pubmed.ncbi.nlm.nih.gov/42345355/",
                verified=True,
                resolved=True,
            ),
            Citation(
                key="E3",
                node_id="src.egfr.trial-NCT06940778",
                node_kind="fact",
                node_value="true",
                doc="trials-EGFR",
                quote="TITLE: Liquid biopsy in gastrointestinal tumours",
                explanation="NCT06940778 — status ACTIVE_NOT_RECRUITING",
                source_type="nct",
                source_id="NCT06940778",
                verified=False,
                resolved=False,
            ),
        ]
    )


FIVE_GOOD = (
    "The late-phase trial counter is 0, so clinical traction rests on recruitment alone [E1]. "
    "The anchoring paper is not a colorectal study [E2]. "
    "The cited trial is not recruiting [E3]. "
    "No counter distinguishes CRC-specific activity from pan-cancer activity [E1][E2]. "
    "The verdict therefore reads as triage, not as validation [E1]."
)


class SplitSentencesTests(unittest.TestCase):
    def test_counts_five(self) -> None:
        self.assertEqual(len(split_sentences(FIVE_GOOD)), 5)

    def test_does_not_split_on_common_abbreviations(self) -> None:
        text = "Support is thin, e.g. one study [E1]. The rest is inference [E2]."
        self.assertEqual(len(split_sentences(text)), 2)

    def test_empty_text_yields_nothing(self) -> None:
        self.assertEqual(split_sentences("   "), [])


class VerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.led = make_ledger()

    def test_accepts_a_well_formed_objection(self) -> None:
        result = verify(FIVE_GOOD, self.led)

        self.assertTrue(result.ok)
        self.assertEqual(len(result.sentences), 5)
        self.assertEqual(result.cited_keys, ["E1", "E2", "E3"])

    def test_rejects_wrong_sentence_count(self) -> None:
        result = verify("Only one sentence, cited [E1].", self.led)

        self.assertFalse(result.ok)
        self.assertIn("expected 5 sentences, got 1", " ".join(result.problems))

    def test_rejects_unknown_citation_key(self) -> None:
        text = FIVE_GOOD.replace("[E3]", "[E9]", 1)
        result = verify(text, self.led)

        self.assertFalse(result.ok)
        self.assertTrue(any("unknown key [E9]" in p for s in result.sentences for p in s.problems))

    def test_rejects_uncited_sentence(self) -> None:
        text = FIVE_GOOD.replace("The cited trial is not recruiting [E3].", "The cited trial is not recruiting.")
        result = verify(text, self.led)

        self.assertFalse(result.ok)
        self.assertTrue(any("no citation" in p for s in result.sentences for p in s.problems))

    def test_rejects_invented_pmid(self) -> None:
        text = FIVE_GOOD.replace("[E2]. ", "[E2], see PMID 99999999. ", 1)
        result = verify(text, self.led)

        self.assertFalse(result.ok)
        self.assertTrue(any("PMID 99999999" in p for s in result.sentences for p in s.problems))

    def test_rejects_invented_nct(self) -> None:
        text = FIVE_GOOD.replace("[E3]. ", "[E3] and NCT00000001. ", 1)
        result = verify(text, self.led)

        self.assertFalse(result.ok)
        self.assertTrue(any("NCT00000001" in p for s in result.sentences for p in s.problems))

    def test_warns_about_numbers_absent_from_the_ledger(self) -> None:
        text = FIVE_GOOD.replace("is 0,", "is 47,", 1)
        result = verify(text, self.led)

        self.assertTrue(any("number 47" in w for s in result.sentences for w in s.warnings))

    def test_warns_when_a_cited_record_does_not_resolve(self) -> None:
        result = verify(FIVE_GOOD, self.led)
        third = result.sentences[2]

        self.assertTrue(any("does not resolve" in w for w in third.warnings))
        self.assertTrue(any("could not verify" in w for w in third.warnings))
        self.assertTrue(third.grounded)  # a warning is not a failure

    def test_empty_response_is_a_failure(self) -> None:
        result = verify("", self.led)

        self.assertFalse(result.ok)
        self.assertIn("returned no text", " ".join(result.problems))

    def test_backtrace_is_attached_per_sentence(self) -> None:
        result = verify(FIVE_GOOD, self.led)
        payload = result.to_json()

        first = payload["sentences"][0]["backtrace"][0]
        self.assertEqual(first["node"], "src.egfr.trials-late-phase")
        self.assertEqual(first["quote"], "TRIALS late_phase=0")
        self.assertEqual(payload["sentences"][1]["backtrace"][0]["source"]["id"], "42345355")


if __name__ == "__main__":
    unittest.main()
