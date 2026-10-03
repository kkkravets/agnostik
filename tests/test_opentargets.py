import unittest

from agnostik.targets.opentargets import merge_targets


def target(ensembl_id, symbol, score, disease_id):
    return {
        "ensembl_id": ensembl_id,
        "gene_symbol": symbol,
        "opentargets_association_score": score,
        "disease_id": disease_id,
    }


class MergeTargetsTests(unittest.TestCase):
    def test_keeps_best_score_per_gene_and_reranks(self) -> None:
        colon = [target("E1", "APC", 0.9, "colon"), target("E2", "KRAS", 0.5, "colon")]
        colorectal = [target("E2", "KRAS", 0.7, "colorectal"), target("E3", "MLH1", 0.6, "colorectal")]

        merged = merge_targets([colon, colorectal], 10)

        self.assertEqual([t["gene_symbol"] for t in merged], ["APC", "KRAS", "MLH1"])
        self.assertEqual([t["opentargets_rank"] for t in merged], [1, 2, 3])
        self.assertEqual(merged[1]["disease_id"], "colorectal")  # the disease that gave KRAS its best score

    def test_truncates_to_n(self) -> None:
        lists = [[target("E1", "A", 0.9, "d"), target("E2", "B", 0.8, "d"), target("E3", "C", 0.7, "d")]]

        self.assertEqual([t["gene_symbol"] for t in merge_targets(lists, 2)], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
