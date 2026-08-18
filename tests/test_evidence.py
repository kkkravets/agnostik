import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agnostik.evidence import (
    EvidenceConfig,
    build_queries,
    candidate_run_id,
    collect_candidate_evidence,
)


class EvidenceQueryTests(unittest.TestCase):
    def test_queries_are_candidate_and_cancer_specific(self):
        queries = build_queries("egfr", "breast cancer")
        self.assertEqual(queries.clinical_trials, "EGFR breast cancer")
        self.assertIn("EGFR[Title/Abstract]", queries.full_text)
        self.assertIn('"breast cancer"[Title/Abstract]', queries.full_text)

    def test_custom_base_query_is_combined_with_each_gene(self):
        base = '(COAD[Title/Abstract] OR "colon adenocarcinoma"[Title/Abstract])'
        queries = build_queries("kras", "colon adenocarcinoma", base)
        self.assertEqual(
            queries.full_text,
            f"({base}) AND KRAS[Title/Abstract]",
        )
        self.assertEqual(queries.pubmed, queries.full_text)

    def test_run_id_is_stable_and_configuration_sensitive(self):
        first = EvidenceConfig("BRCA", "breast cancer", ("EGFR",), max_articles=5)
        same = EvidenceConfig("brca", " breast  cancer ", ("egfr",), max_articles=5)
        changed = EvidenceConfig("BRCA", "breast cancer", ("EGFR",), max_articles=6)
        self.assertEqual(candidate_run_id(first, "EGFR"), candidate_run_id(same, "egfr"))
        self.assertNotEqual(candidate_run_id(first, "EGFR"), candidate_run_id(changed, "EGFR"))


class EvidenceCollectionTests(unittest.TestCase):
    def test_writes_reproducibility_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = EvidenceConfig(
                "BRCA",
                "breast cancer",
                ("EGFR",),
                max_articles=2,
                max_trials=3,
                output_root=root,
            )

            def fake_runner(command, log_path):
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text("ok", encoding="utf-8")
                if "clinical_trial_finder.py" in command[1]:
                    output = Path(command[command.index("--output") + 1])
                    output.mkdir(parents=True, exist_ok=True)
                    (output / "summary.json").write_text(
                        json.dumps({"total": 3, "recruiting": 1}), encoding="utf-8"
                    )
                else:
                    output = Path(command[command.index("--output") + 1])
                    output.mkdir(parents=True, exist_ok=True)
                    (output / "report.html").write_text("report", encoding="utf-8")

            def fake_downloader(query, maximum, output, **kwargs):
                output.mkdir(parents=True, exist_ok=True)
                (output / "PMC1.txt").write_text("full article", encoding="utf-8")
                return [object(), object()]

            run = collect_candidate_evidence(
                config,
                "EGFR",
                command_runner=fake_runner,
                article_downloader=fake_downloader,
            )

            self.assertEqual(run.status, "complete")
            self.assertEqual(run.article_count, 2)
            self.assertEqual(run.trial_count, 3)
            self.assertTrue((run.run_dir / "manifest.json").is_file())
            self.assertTrue((run.run_dir / "commands.json").is_file())
            self.assertTrue((run.run_dir / "checksums.sha256").is_file())
            self.assertTrue((run.run_dir / "literature" / "sources" / "PMC1.txt").is_file())

    def test_batch_writes_tumour_level_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = EvidenceConfig(
                "COAD",
                "colon adenocarcinoma",
                ("EGFR", "KRAS"),
                article_query="COAD[Title/Abstract]",
                output_root=root,
            )
            fake_runs = [
                type("Run", (), {
                    "gene": gene,
                    "run_id": f"run-{gene.lower()}",
                    "run_dir": root / "coad" / gene.lower() / f"run-{gene.lower()}",
                    "status": "complete",
                    "article_count": 1,
                    "trial_count": 0,
                    "error": "",
                })()
                for gene in config.genes
            ]
            with patch("agnostik.evidence.collect_candidate_evidence", side_effect=fake_runs):
                from agnostik.evidence import collect_evidence_batch

                collect_evidence_batch(config)

            manifest = json.loads(
                (root / "coad" / "batch_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual([item["gene"] for item in manifest["genes"]], ["EGFR", "KRAS"])
            self.assertEqual(
                manifest["genes"][1]["query"],
                "(COAD[Title/Abstract]) AND KRAS[Title/Abstract]",
            )


if __name__ == "__main__":
    unittest.main()
