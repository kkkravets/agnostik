import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest

from parseltongue import System
from parseltongue.core import load_source

from agnostik.candidates import PRESELECTED_CANDIDATES
from agnostik.objections.bundle import load_export
from agnostik.objections.targets import discover
from agnostik.parseltongue_corpus import (
    TargetResult,
    Stage3Config,
    build_stage4_export,
    discover_sources,
    export_completed_targets,
    run_stage3,
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

    def test_exports_only_completed_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            target_dir = output_dir / "targets" / "egfr"
            target_dir.mkdir(parents=True)
            system = target_system("EGFR")
            (target_dir / "system.json").write_text(
                json.dumps(system.to_dict(), default=str), encoding="utf-8"
            )
            (target_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "target": "EGFR",
                        "status": "complete",
                        "sources": ["PMC-EGFR.txt"],
                    }
                ),
                encoding="utf-8",
            )

            export_path, completed = export_completed_targets(
                output_dir, ("EGFR", "KRAS")
            )

            self.assertEqual(completed, ("EGFR",))
            self.assertTrue(export_path.is_file())
            views = discover(load_export(export_path), ["EGFR"])
            self.assertEqual(views[0].symbol, "EGFR")

    def test_runs_independent_targets_concurrently_with_separate_providers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "sources"
            source_dir.mkdir()
            (source_dir / "paper.txt").write_text("EGFR and KRAS", encoding="utf-8")
            config = Stage3Config(
                tumour_type="COAD",
                cancer_term="colon adenocarcinoma",
                source_dir=source_dir,
                output_dir=root / "output",
                targets=("EGFR", "KRAS"),
            )
            lock = threading.Lock()
            provider_ids = []
            active = 0
            peak_active = 0

            def provider_factory(**kwargs):
                provider = object()
                with lock:
                    provider_ids.append(id(provider))
                return provider

            def pipeline_runner(documents, query, provider):
                nonlocal active, peak_active
                target = "EGFR" if "of EGFR " in query else "KRAS"
                with lock:
                    active += 1
                    peak_active = max(peak_active, active)
                time.sleep(0.05)
                with lock:
                    active -= 1
                return SimpleNamespace(
                    system=target_system(target),
                    output=SimpleNamespace(markdown="", references=[], consistency={}),
                    pass1_source="",
                    pass2_source="",
                    pass3_source="",
                    pass4_raw="",
                )

            run = run_stage3(
                config,
                max_workers=2,
                provider_factory=provider_factory,
                pipeline_runner=pipeline_runner,
            )

            self.assertEqual(run.target_count, 2)
            self.assertEqual(peak_active, 2)
            self.assertEqual(len(set(provider_ids)), 2)

    def test_retries_a_target_after_malformed_model_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "sources"
            source_dir.mkdir()
            (source_dir / "paper.txt").write_text("EGFR", encoding="utf-8")
            config = Stage3Config(
                tumour_type="COAD",
                cancer_term="colon adenocarcinoma",
                source_dir=source_dir,
                output_dir=root / "output",
                targets=("EGFR",),
            )
            attempts = 0

            def pipeline_runner(documents, query, provider):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise NameError("generated symbol is missing")
                return SimpleNamespace(
                    system=target_system("EGFR"),
                    output=SimpleNamespace(markdown="", references=[], consistency={}),
                    pass1_source="",
                    pass2_source="",
                    pass3_source="",
                    pass4_raw="",
                )

            run = run_stage3(
                config,
                max_attempts=2,
                provider_factory=lambda **kwargs: object(),
                pipeline_runner=pipeline_runner,
            )

            self.assertEqual(run.target_count, 1)
            self.assertEqual(attempts, 2)


if __name__ == "__main__":
    unittest.main()
