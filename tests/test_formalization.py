import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from parseltongue import System
from parseltongue.core import load_source

from agnostik.candidates import PRESELECTED_CANDIDATES
from agnostik.objections.bundle import load_export
from agnostik.objections.targets import discover
from agnostik.formalization import (
    TargetResult,
    FormalizationConfig,
    _run_pipeline,
    build_objections_export,
    discover_sources,
    export_completed_targets,
    run_formalization,
    select_target_sources,
    target_query,
    validate_objections_export,
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


def write_corpus(root: Path, articles: dict[str, str]) -> Path:
    """Write article files under root/evidence plus the corpus.json naming them."""
    source_dir = root / "evidence"
    source_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, body in articles.items():
        (source_dir / name).write_text(body, encoding="utf-8")
        entries.append({"name": name, "path": f"evidence/{name}"})
    corpus = root / "corpus.json"
    corpus.write_text(json.dumps({"articles": entries}), encoding="utf-8")
    return corpus


class FormalizationSourceTests(unittest.TestCase):
    def test_selects_target_specific_articles(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = write_corpus(
                Path(temporary),
                {
                    "PMC2.txt": "KRAS once",
                    "PMC1.txt": "KRAS KRAS KRAS",
                    "PMC3.txt": "EGFR only",
                },
            )
            selected = select_target_sources(
                discover_sources(corpus), "KRAS", max_documents=2, max_chars=1_000
            )
            self.assertEqual([path.name for path in selected], ["PMC1.txt", "PMC2.txt"])

    def test_trials_get_a_reserved_share_of_the_character_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = write_corpus(
                Path(temporary),
                {
                    "PMC1.txt": "KRAS " * 100,
                    "trial-KRAS-NCT1.txt": "KRAS trial",
                    "trial-KRAS-NCT2.txt": "KRAS " * 100,
                },
            )
            selected = select_target_sources(
                discover_sources(corpus), "KRAS", max_documents=10, max_chars=520
            )
            # The article alone fits 520 chars; the reserved 20% (104) admits only the short trial.
            self.assertEqual([path.name for path in selected], ["PMC1.txt", "trial-KRAS-NCT1.txt"])

    def test_reads_articles_referenced_by_a_corpus_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = write_corpus(Path(temporary), {"PMC1.txt": "KRAS KRAS"})

            sources = discover_sources(corpus)

            self.assertEqual([path.name for path in sources], ["PMC1.txt"])
            self.assertEqual(sources[0].read_text(encoding="utf-8"), "KRAS KRAS")

    def test_rejects_a_manifest_referencing_a_missing_article(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = Path(temporary) / "corpus.json"
            corpus.write_text(
                json.dumps({"articles": [{"name": "PMC1.txt", "path": "gone/PMC1.txt"}]}),
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                discover_sources(corpus)

    def test_rejects_a_missing_corpus_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                discover_sources(Path(temporary) / "corpus.json")

    def test_documents_are_registered_as_text_never_by_path(self):
        """Parseltongue opens a path with the locale encoding.

        On Windows that rejects 172 and silently mangles 127 of the 300
        articles in the COAD corpus, so the text= branch is load-bearing.
        """
        captured: dict[str, tuple[str | None, str | None]] = {}

        class RecordingPipeline:
            def __init__(self, system, provider):
                pass

            def add_document(self, name, path=None, text=None):
                captured[name] = (path, text)

            def run(self, query):
                return "pipeline-result"

        body = "EGFR inhibitors – β-catenin “signalling”"
        with patch("agnostik.formalization.Pipeline", RecordingPipeline):
            result = _run_pipeline([("paper", body)], "query", object())

        self.assertEqual(result, "pipeline-result")
        self.assertEqual(captured["paper"], (None, body))

    def test_query_requires_exact_boolean_verdict(self):
        query = target_query("EGFR", "colon adenocarcinoma", "COAD")
        self.assertIn("egfr-verdict", query)
        self.assertIn("Boolean", query)
        self.assertIn("verbatim", query)
        self.assertIn(":using", query)


class FormalizationExportTests(unittest.TestCase):
    def test_export_is_directly_consumable_by_objections(self):
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
            export_path = root / "formal-system.json"
            export_path.write_text(
                json.dumps(build_objections_export(results), default=str), encoding="utf-8"
            )
            validate_objections_export(export_path, PRESELECTED_CANDIDATES)
            views = discover(load_export(export_path), list(PRESELECTED_CANDIDATES))
            self.assertEqual([view.symbol for view in views], list(PRESELECTED_CANDIDATES))
            self.assertTrue(all(view.verdict is True for view in views))
            self.assertTrue(all(any(fact.is_grounded for fact in view.facts) for view in views))
            payload = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(payload), {"DATA", "STRUCTURE_DATA", "LAYERS", "TAINT_DATA", "SOURCES"}
            )
            # Documents are cited by stem; SOURCES maps each back to its real file name.
            self.assertEqual(payload["SOURCES"]["PMC-EGFR"], "PMC-EGFR.txt")
            self.assertEqual(load_export(export_path).sources, payload["SOURCES"])

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

    def test_criteria_file_becomes_a_quotable_document_and_is_named_in_the_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = write_corpus(root, {"paper.txt": "EGFR"})
            criteria = root / "rules.md"
            criteria.write_text("R1 A target is promising when it is druggable.", encoding="utf-8")
            seen = {}

            def pipeline_runner(documents, query, provider):
                seen["documents"], seen["query"] = documents, query
                return SimpleNamespace(
                    system=target_system("EGFR"),
                    output=SimpleNamespace(markdown="", references=[], consistency={}),
                    pass1_source="",
                    pass2_source="",
                    pass3_source="",
                    pass4_raw="",
                )

            def run(criteria_path, output):
                config = FormalizationConfig(
                    tumour_type="COAD",
                    cancer_term="colon adenocarcinoma",
                    corpus_manifest=corpus,
                    output_dir=root / output,
                    targets=("EGFR",),
                    criteria=criteria_path,
                )
                run_formalization(config, provider_factory=lambda **kw: object(), pipeline_runner=pipeline_runner)
                return json.loads((root / output / "targets" / "egfr" / "manifest.json").read_text(encoding="utf-8"))

            record = run(criteria, "with")
            self.assertEqual(seen["documents"][0], ("rules", "R1 A target is promising when it is druggable."))
            self.assertIn('document "rules"', seen["query"])
            self.assertEqual(record["criteria"], str(criteria.resolve()))

            fingerprint = record["fingerprint"]
            record = run(None, "without")
            self.assertEqual([name for name, _ in seen["documents"]], ["paper"])
            self.assertNotIn("review criteria", seen["query"])
            self.assertIsNone(record["criteria"])
            self.assertNotEqual(record["fingerprint"], fingerprint)

    def test_missing_criteria_file_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            FormalizationConfig(
                tumour_type="COAD",
                cancer_term="colon adenocarcinoma",
                corpus_manifest=Path("corpus.json"),
                output_dir=Path("out"),
                criteria=Path("no-such-criteria.md"),
            )

    def test_runs_independent_targets_concurrently_with_separate_providers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = write_corpus(root, {"paper.txt": "EGFR and KRAS"})
            config = FormalizationConfig(
                tumour_type="COAD",
                cancer_term="colon adenocarcinoma",
                corpus_manifest=corpus,
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

            run = run_formalization(
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
            corpus = write_corpus(root, {"paper.txt": "EGFR"})
            config = FormalizationConfig(
                tumour_type="COAD",
                cancer_term="colon adenocarcinoma",
                corpus_manifest=corpus,
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

            run = run_formalization(
                config,
                max_attempts=2,
                provider_factory=lambda **kwargs: object(),
                pipeline_runner=pipeline_runner,
            )

            self.assertEqual(run.target_count, 1)
            self.assertEqual(attempts, 2)


if __name__ == "__main__":
    unittest.main()
