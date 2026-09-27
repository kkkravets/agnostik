from pathlib import Path
import tempfile
import unittest

from agnostik.candidates import PRESELECTED_CANDIDATES, load_gene_list, select_candidates


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


class LoadGeneListTests(unittest.TestCase):
    def test_reads_plain_text_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "symbols.txt"
            path.write_text("egfr\n\n# comment\nkras\nEGFR\n")

            self.assertEqual(load_gene_list(path), ("EGFR", "KRAS"))

    def test_reads_opentargets_csv_by_gene_symbol_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "genes.csv"
            path.write_text(
                "opentargets_rank,ensembl_id,gene_symbol,gene_name,biotype,opentargets_association_score\n"
                "1,ENSG1,MSH2,mutS homolog 2,protein_coding,0.92\n"
                "2,ENSG2,APC,APC regulator,protein_coding,0.85\n"
            )

            self.assertEqual(load_gene_list(path), ("MSH2", "APC"))

    def test_top_n_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "symbols.txt"
            path.write_text("MSH2\nAPC\nBRAF\n")

            self.assertEqual(load_gene_list(path, limit=2), ("MSH2", "APC"))

    def test_rejects_missing_gene_symbol_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "genes.csv"
            path.write_text("ensembl_id\nENSG1\n")

            with self.assertRaises(ValueError):
                load_gene_list(path)

    def test_rejects_invalid_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "symbols.txt"
            path.write_text("MSH2\nnot a gene!\n")

            with self.assertRaises(ValueError):
                load_gene_list(path)

    def test_rejects_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "symbols.txt"
            path.write_text("\n\n")

            with self.assertRaises(ValueError):
                load_gene_list(path)


if __name__ == "__main__":
    unittest.main()

