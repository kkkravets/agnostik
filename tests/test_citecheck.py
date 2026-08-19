import unittest

from agnostik.citecheck.check import CitationCheck, _grade, target_of
from agnostik.citecheck.emit import counters_for
from agnostik.citecheck.registry import Record, normalise_title


def check(**kwargs) -> CitationCheck:
    base = dict(
        key="E1",
        node_id="src.prmt5.paper-1",
        target="PRMT5",
        source_type="pmid",
        source_id="1",
        url="",
        quote="TITLE: A paper",
        doc="pubmed-PRMT5",
    )
    base.update(kwargs)
    return CitationCheck(**base)


ALIASES = ["PRMT5", "JBP1", "Protein arginine N-methyltransferase 5"]


class GradingTests(unittest.TestCase):
    def test_subject_level_record_is_sound(self) -> None:
        record = Record(
            "pmid", "1", exists=True,
            title="PRMT5 drives colorectal cancer progression",
            abstract="We show colorectal tumours depend on PRMT5.",
        )
        c = check(quote="TITLE: PRMT5 drives colorectal cancer progression")
        _grade(c, record, "PRMT5", ALIASES)

        self.assertEqual(c.status, "sound")
        self.assertEqual(c.gene_role, "title")
        self.assertEqual(c.indication_role, "title")

    def test_mention_in_abstract_only_is_weak_attribution(self) -> None:
        record = Record(
            "pmid", "1", exists=True,
            title="A nuclear isoform of HADH inhibits colorectal tumour progression",
            abstract="Loss of the isoform activates PRMT5 signalling.",
        )
        c = check(quote="TITLE: A nuclear isoform of HADH inhibits colorectal tumour progression")
        _grade(c, record, "PRMT5", ALIASES)

        self.assertEqual(c.status, "weak-attribution")
        self.assertEqual(c.gene_role, "abstract")
        self.assertTrue(any("not the subject" in r for r in c.reasons))

    def test_record_never_naming_the_gene_is_off_target(self) -> None:
        record = Record("pmid", "1", exists=True, title="IL-27 shapes NK cells in colorectal cancer",
                        abstract="No mention of the target here.")
        c = check(quote="TITLE: IL-27 shapes NK cells in colorectal cancer")
        _grade(c, record, "PRMT5", ALIASES)

        self.assertEqual(c.status, "off-target")

    def test_alias_counts_as_the_gene(self) -> None:
        """ERBB2 appears as HER2 far more often than as its symbol."""
        record = Record("pmid", "2", exists=True,
                        title="Anti-HER2 therapy in metastatic colorectal cancer",
                        abstract="HER2 amplified disease.")
        c = check(target="ERBB2", source_id="2", quote="TITLE: Anti-HER2 therapy in metastatic colorectal cancer")
        _grade(c, record, "ERBB2", ["ERBB2", "HER2", "Receptor tyrosine-protein kinase erbB-2"])

        self.assertEqual(c.gene_role, "title")
        self.assertEqual(c.status, "sound")

    def test_retraction_outranks_everything(self) -> None:
        record = Record("pmid", "1", exists=True, title="PRMT5 in colorectal cancer",
                        abstract="PRMT5", publication_types=["Journal Article", "Retracted Publication"])
        c = check(quote="TITLE: PRMT5 in colorectal cancer")
        _grade(c, record, "PRMT5", ALIASES)

        self.assertEqual(c.status, "retracted")
        self.assertTrue(c.retracted)

    def test_unresolved_record(self) -> None:
        c = check()
        _grade(c, Record("pmid", "1", exists=False, note="no record returned by PubMed"), "PRMT5", ALIASES)

        self.assertEqual(c.status, "unresolved")
        self.assertFalse(c.resolves)

    def test_offline_record_is_not_checked(self) -> None:
        c = check()
        _grade(c, Record("pmid", "1", exists=None, note="offline: not checked"), "PRMT5", ALIASES)

        self.assertEqual(c.status, "not-checked")
        self.assertIsNone(c.resolves)

    def test_title_drift_is_flagged(self) -> None:
        record = Record("pmid", "1", exists=True, title="PRMT5 controls splicing in colorectal cancer",
                        abstract="PRMT5 colorectal")
        c = check(quote="TITLE: Something else entirely about a different protein")
        _grade(c, record, "PRMT5", ALIASES)

        self.assertEqual(c.status, "title-drift")
        self.assertLess(c.title_similarity, 0.88)

    def test_truncated_quote_still_matches(self) -> None:
        """The dossier truncates long titles; a prefix is fidelity, not drift."""
        full = "PRMT5 upregulates KCNMB4 expression via histone methylation to promote resistance in colorectal cancer"
        record = Record("pmid", "1", exists=True, title=full, abstract="colorectal")
        c = check(quote=f"TITLE: {full[:70]}")
        _grade(c, record, "PRMT5", ALIASES)

        self.assertEqual(c.title_verdict, "match")

    def test_uniprot_is_not_asked_about_indication(self) -> None:
        record = Record("uniprot", "O14744", exists=True,
                        title="Protein arginine N-methyltransferase 5", abstract="PRMT5")
        c = check(source_type="uniprot", source_id="O14744", quote="UNIPROT binding_sites=7")
        _grade(c, record, "PRMT5", ALIASES)

        self.assertEqual(c.indication_role, "not-applicable")
        self.assertEqual(c.status, "sound")

    def test_trial_without_the_gene_is_weak_not_off_target(self) -> None:
        """Trials name drugs, not genes — free-text matching is the real finding."""
        record = Record("nct", "NCT1", exists=True, title="Study of a bispecific in colorectal cancer",
                        conditions=["Colorectal Cancer"])
        c = check(source_type="nct", source_id="NCT1", quote="TITLE: Study of a bispecific in colorectal cancer")
        _grade(c, record, "PRMT5", ALIASES)

        self.assertEqual(c.status, "weak-attribution")
        self.assertTrue(any("free-text" in r for r in c.reasons))


class HelperTests(unittest.TestCase):
    def test_target_of_reads_the_namespace(self) -> None:
        self.assertEqual(target_of("src.prmt5.paper-1", ["EGFR", "PRMT5"]), "PRMT5")
        self.assertEqual(target_of("shortlist-size", ["EGFR", "PRMT5"]), "")

    def test_normalise_title_strips_punctuation(self) -> None:
        self.assertEqual(normalise_title("PRMT5: a review."), "prmt5  a review")

    def test_counters_add_up(self) -> None:
        checks = [
            check(status="sound", gene_role="title"),
            check(status="weak-attribution", gene_role="abstract"),
            check(status="off-target", gene_role="absent"),
            check(status="retracted"),
        ]
        counters = counters_for(checks)

        self.assertEqual(counters["subject_records"], 1)
        self.assertEqual(counters["weak_attribution"], 1)
        self.assertEqual(counters["off_target"], 1)
        self.assertEqual(counters["retracted"], 1)
        self.assertEqual(counters["checked_total"], 4)


if __name__ == "__main__":
    unittest.main()
