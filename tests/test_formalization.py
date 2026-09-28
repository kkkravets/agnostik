from contextlib import redirect_stdout
import io
import json
import logging
from pathlib import Path
import re
import tempfile
import threading
import time
import unittest

from parseltongue import System
from parseltongue.core import load_source

from agnostik.candidates import PRESELECTED_CANDIDATES
from agnostik.objections.bundle import load_export
from agnostik.objections.targets import discover
from agnostik.formalization import (
    DocumentFailures,
    TargetResult,
    FormalizationConfig,
    build_objections_export,
    discover_sources,
    document_text,
    export_completed_targets,
    run_formalization,
    select_target_documents,
    validate_objections_export,
)
from agnostik.parseltongue_cli import main

logging.getLogger("parseltongue").setLevel(logging.CRITICAL)
logging.getLogger("agnostik.formalization").setLevel(logging.CRITICAL)

RULES = """# Test criteria

Scope: only the supplied documents count.

## R1 Chemical matter
A target has chemical matter when at least two of the supplied publications describe a compound acting on it.

    applies to: publications
    ask: Does this publication describe a compound acting on the target?
    met when: at least 2 documents answer yes

## R2 Clinical traction
A target has clinical traction when at least one trial record is in phase 3 or recruiting.

    applies to: trials
    ask: Is this trial in phase 3 or recruiting?
    met when: at least 1 document answers yes

## R3 Opposing evidence
Evidence against the target must be recorded.

    applies to: publications and trials
    ask: Does this document report evidence against the target?
    record only

## R4 Verdict
A target is promising when it has chemical matter and clinical traction.

    verdict: R1 and R2
"""

TRIAL = (
    "# Trial of Z\n\nClinical trial: NCT1\nRetrieved for target: EGFR\nStatus: RECRUITING\nPhase: PHASE3\n\n"
    "## Summary\n\nZ targets EGFR in colorectal cancer.\n"
)
CORPUS = {
    "PMC1.txt": "Compound X inhibits EGFR in colon cancer cells. Xenograft tumours shrank after EGFR blockade.",
    "PMC2.txt": "Antibody Y binds EGFR.",
    "PMC3.txt": "Inhibitor Z blocks EGFR signalling. Resistance to Z emerged in most patients.",
    "trial-EGFR-NCT1.txt": TRIAL,
    "PMC9.txt": "KRAS only.",
}


def quoted(name, document, quote, value="true"):
    return f'(fact {name} {value} :evidence (evidence "{document}" :quotes ("{quote}") :explanation "e"))'


# What the model writes per document: (extraction, judgement).
OUTPUTS = {
    "PMC1": (
        quoted("inhibitor-x", "PMC1", "Compound X inhibits EGFR in colon cancer cells."),
        "(derive pmc1.r1 pmc1.inhibitor-x :using (pmc1.inhibitor-x))",
    ),
    "PMC2": (
        # The stray ')' after the first fact must not lose the second one.
        quoted("antibody-y", "PMC2", "Antibody Y binds EGFR.") + ")\n" + quoted("binding", "PMC2", "Antibody Y binds EGFR."),
        # Written without the document prefix.
        "(derive r1 antibody-y :using (antibody-y))",
    ),
    "PMC3": (
        quoted("inhibitor-z", "PMC3", "Inhibitor Z blocks EGFR signalling.")
        + "\n"
        + quoted("resistance", "PMC3", "Resistance to Z emerged in most patients.")
        + '\n(fact inhibitor-z false :origin "second reading")',
        "(derive pmc3.r1 pmc3.inhibitor-z :using (pmc3.inhibitor-z))\n(derive pmc3.r3 pmc3.resistance :using (pmc3.resistance))",
    ),
    "trial-EGFR-NCT1": (
        quoted("recruiting", "trial-EGFR-NCT1", "Status: RECRUITING")
        + "\n"
        + quoted("named", "trial-EGFR-NCT1", "Retrieved for target: EGFR"),
        "(derive trial-egfr-nct1.r2 trial-egfr-nct1.recruiting :using (trial-egfr-nct1.recruiting))",
    ),
}


class FakeProvider:
    """Answers each Parseltongue tool call from OUTPUTS, keyed by the document the prompt is about."""

    def __init__(self, fail=(), fail_once=False, delay=0.0):
        self.prompts, self.fail, self.fail_once, self.delay = [], set(fail), fail_once, delay
        self.closed = False
        self.lock = threading.Lock()

    def complete(self, messages, tools, **kwargs):
        tool, user = tools[0]["function"]["name"], messages[-1]["content"]
        found = re.search(r'[Dd]ocument:? "([^"]+)"', user)
        key = found.group(1) if found and tool in ("extract", "derive") else None
        with self.lock:
            self.prompts.append((tool, key, user))
            if self.fail_once:
                self.fail_once = False
                raise RuntimeError("transient provider fault")
        if key in self.fail or tool in self.fail:
            raise RuntimeError("provider fault")
        time.sleep(self.delay)
        if tool == "extract":
            return {"dsl_output": OUTPUTS[key][0]}
        if tool == "derive":
            return {"dsl_output": OUTPUTS[key][1]}
        if tool == "factcheck":
            return {"dsl_output": '(defterm egfr-verdict false :origin "second opinion")'}
        return {"markdown": "EGFR looks promising [[term:egfr-verdict]]."}

    def calls(self, tool=None):
        return [(t, k) for t, k, _ in self.prompts if tool in (None, t)]

    def close(self):
        self.closed = True


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


def make_config(root: Path, corpus=CORPUS, rules=RULES, **overrides) -> FormalizationConfig:
    criteria = root / "rules.md"
    criteria.write_text(rules, encoding="utf-8")
    settings = dict(
        tumour_type="COAD",
        cancer_term="colon adenocarcinoma",
        corpus_manifest=write_corpus(root, corpus),
        output_dir=root / "output",
        targets=("EGFR",),
        criteria=criteria,
    )
    settings.update(overrides)
    return FormalizationConfig(**settings)


def read_manifest(config, target="egfr"):
    return json.loads((config.output_dir / "targets" / target / "manifest.json").read_text(encoding="utf-8"))


class FormalizationSourceTests(unittest.TestCase):
    def test_selects_every_document_naming_the_target_or_an_alias_most_mentions_first(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = write_corpus(
                Path(temporary),
                {"PMC2.txt": "ERBB2 once", "PMC1.txt": "HER2 and HER2 and ERBB2", "PMC3.txt": "EGFR only"},
            )
            selected, excluded = select_target_documents(discover_sources(corpus), "ERBB2", aliases=("HER2",))
            self.assertEqual([path.name for path in selected], ["PMC1.txt", "PMC2.txt"])
            self.assertEqual(excluded, [{"file": "PMC3.txt", "reason": "does not mention ERBB2 or HER2"}])

    def test_the_document_cap_applies_per_kind_and_lists_what_it_left_out(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = write_corpus(
                Path(temporary),
                {
                    "PMC1.txt": "KRAS KRAS KRAS",
                    "PMC2.txt": "KRAS",
                    "trial-KRAS-NCT1.txt": "KRAS trial",
                    "trial-KRAS-NCT2.txt": "KRAS KRAS trial",
                },
            )
            selected, excluded = select_target_documents(discover_sources(corpus), "KRAS", max_documents=1)
            self.assertEqual([path.name for path in selected], ["PMC1.txt", "trial-KRAS-NCT2.txt"])
            self.assertEqual(
                excluded,
                [
                    {"file": "PMC2.txt", "reason": "over --max-documents-per-target (1 articles)"},
                    {"file": "trial-KRAS-NCT1.txt", "reason": "over --max-documents-per-target (1 trials)"},
                ],
            )

    def test_lines_the_pipeline_added_are_not_part_of_the_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            trial = Path(temporary) / "trial-EGFR-NCT1.txt"
            trial.write_text(TRIAL, encoding="utf-8")
            self.assertNotIn("Retrieved for target", document_text(trial))
            self.assertIn("Status: RECRUITING", document_text(trial))

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

    def test_missing_criteria_file_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            FormalizationConfig(
                tumour_type="COAD",
                cancer_term="colon adenocarcinoma",
                corpus_manifest=Path("corpus.json"),
                output_dir=Path("out"),
                criteria=Path("no-such-criteria.md"),
            )

    def test_malformed_criteria_are_rejected_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "verdict"):
                make_config(Path(temporary), rules=RULES.replace("    verdict: R1 and R2\n", ""))


class FormalizationRunTests(unittest.TestCase):
    def test_judges_each_document_alone_and_decides_by_the_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = make_config(Path(temporary))
            provider = FakeProvider()

            run = run_formalization(config, provider_factory=lambda **kwargs: provider)

            # Two calls per document, then one fact-check and one report.
            self.assertEqual(run.model_calls, 10)
            self.assertTrue(provider.closed)
            record = read_manifest(config)
            self.assertIs(record["verdict"], True)
            self.assertEqual(record["verdict_node"], "egfr-verdict")
            self.assertEqual((record["rules"]["R1"]["count"], record["rules"]["R1"]["met"]), (3, True))
            self.assertEqual(record["rules"]["R1"]["yes"], ["pmc1.r1", "pmc2.r1", "pmc3.r1"])
            self.assertEqual((record["rules"]["R2"]["count"], record["rules"]["R2"]["met"]), (1, True))
            self.assertEqual(record["rules"]["R3"]["count"], 1)
            self.assertEqual(record["rules"]["R3"]["unanswered"], ["PMC1", "PMC2", "trial-EGFR-NCT1"])
            self.assertEqual([doc["document"] for doc in record["documents"]], ["PMC1", "PMC2", "PMC3", "trial-EGFR-NCT1"])
            self.assertEqual(record["excluded"], [{"file": "PMC9.txt", "reason": "does not mention EGFR or ERBB1 or HER1"}])

            documents = {doc["document"]: doc for doc in record["documents"]}
            self.assertEqual(documents["PMC2"]["extract"]["repairs"], ["ignored 1 unmatched ')' on line 1"])
            self.assertEqual(documents["PMC3"]["extract"]["renamed"][0]["loaded_as"], "pmc3.inhibitor-z.2")

            system = System.from_dict(
                json.loads((config.output_dir / "targets" / "egfr" / "system.json").read_text(encoding="utf-8")),
                overridable=False,
            )
            self.assertIn("pmc2.binding", system.engine.facts)
            self.assertIn("pmc3.inhibitor-z.2", system.engine.facts)
            # Our own annotation line is not in the registered text, so quoting it never verifies.
            self.assertFalse(system.engine.facts["trial-egfr-nct1.named"].origin.verified)
            self.assertTrue(system.engine.terms["criteria.r1-met"].origin.verified)
            # The fact-check tried to redefine the verdict; it sits next to it instead.
            self.assertIn("egfr-verdict.2", system.engine.terms)
            self.assertEqual(record["factcheck"]["renamed"][0]["name"], "egfr-verdict")

            prompts = {(tool, key): user for tool, key, user in provider.prompts}
            self.assertNotIn("Antibody Y", prompts[("extract", "PMC1")])
            self.assertNotIn("Retrieved for target", prompts[("extract", "trial-EGFR-NCT1")])
            self.assertIn("pmc1.r1: Does this publication describe a compound", prompts[("derive", "PMC1")])
            self.assertNotIn("r2:", prompts[("derive", "PMC1")])
            self.assertIn("trial-egfr-nct1.r2: Is this trial in phase 3", prompts[("derive", "trial-EGFR-NCT1")])

            views = discover(load_export(run.export_path), ["EGFR"])
            self.assertIs(views[0].verdict, True)

    def test_the_review_sees_rule_summaries_not_every_fact(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = make_config(Path(temporary))
            provider = FakeProvider()
            run_formalization(config, provider_factory=lambda **kwargs: provider)
            review = next(user for tool, _, user in provider.prompts if tool == "factcheck")
            self.assertIn("criteria.r1-met = True", review)
            self.assertIn("yes (3): pmc1.r1, pmc2.r1, pmc3.r1", review)
            # R1 holds above its threshold of 2, so no single article decides it and none is quoted.
            self.assertNotIn("Compound X inhibits EGFR", review)
            # R2 rests on one trial and R3 is recorded rather than counted, so their facts are quoted.
            self.assertIn('"Status: RECRUITING"', review)
            self.assertIn('"Resistance to Z emerged in most patients."', review)

    def test_resume_repeats_no_call_whose_prompt_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = make_config(Path(temporary))
            run_formalization(config, provider_factory=lambda **kwargs: FakeProvider())

            idle = FakeProvider(fail={"extract", "derive", "factcheck", "answer"})
            rerun = run_formalization(config, resume=True, provider_factory=lambda **kwargs: idle)
            self.assertEqual((rerun.reused_targets, rerun.model_calls), (1, 0))

            # A new verdict rule changes the target but none of the documents' questions.
            config.criteria.write_text(RULES.replace("verdict: R1 and R2", "verdict: R1 or R2"), encoding="utf-8")
            review_only = FakeProvider()
            rerun = run_formalization(config, resume=True, provider_factory=lambda **kwargs: review_only)
            self.assertEqual(review_only.calls(), [("factcheck", None), ("answer", None)])
            self.assertEqual(rerun.reused_targets, 0)
            self.assertTrue(all(doc["reused"] for doc in read_manifest(config)["documents"]))

    def test_a_failing_document_is_reported_and_only_it_is_retried_on_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = make_config(Path(temporary))
            with self.assertRaisesRegex(DocumentFailures, r"1 of 4 document\(s\) failed after 2 attempt\(s\): PMC2"):
                run_formalization(config, provider_factory=lambda **kwargs: FakeProvider(fail={"PMC2"}))

            provider = FakeProvider()
            run_formalization(config, resume=True, provider_factory=lambda **kwargs: provider)
            self.assertEqual(provider.calls(), [("extract", "PMC2"), ("derive", "PMC2"), ("factcheck", None), ("answer", None)])

    def test_a_failed_call_is_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = make_config(Path(temporary))
            provider = FakeProvider(fail_once=True)
            run = run_formalization(config, max_attempts=2, provider_factory=lambda **kwargs: provider)
            self.assertEqual(run.model_calls, 11)
            self.assertIs(read_manifest(config)["verdict"], True)

    def test_documents_run_concurrently_each_with_its_own_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = make_config(Path(temporary))
            lock, providers, active, peak = threading.Lock(), [], [0], [0]

            class Counting(FakeProvider):
                def complete(self, messages, tools, **kwargs):
                    with lock:
                        active[0] += 1
                        peak[0] = max(peak[0], active[0])
                    try:
                        return super().complete(messages, tools, **kwargs)
                    finally:
                        with lock:
                            active[0] -= 1

            def factory(**kwargs):
                provider = Counting(delay=0.05)
                with lock:
                    providers.append(provider)
                return provider

            run_formalization(config, document_workers=2, provider_factory=factory)
            self.assertEqual(peak[0], 2)
            self.assertGreaterEqual(len(providers), 2)
            self.assertTrue(all(provider.closed for provider in providers))

    def test_runs_independent_targets_concurrently(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = {name: body for name, body in CORPUS.items() if name != "PMC9.txt"}
            corpus["PMC1.txt"] += " KRAS too."
            config = make_config(Path(temporary), corpus=corpus, targets=("EGFR", "KRAS"))
            provider_ids, lock = [], threading.Lock()

            def factory(**kwargs):
                provider = FakeProvider(delay=0.02)
                with lock:
                    provider_ids.append(id(provider))
                return provider

            run = run_formalization(config, max_workers=2, provider_factory=factory)
            self.assertEqual(run.target_count, 2)
            self.assertEqual(len(set(provider_ids)), 2)
            self.assertEqual(read_manifest(config, "kras")["sources"], ["PMC1.txt"])


class FormalizationCliTests(unittest.TestCase):
    def test_dry_run_shows_documents_exclusions_rules_and_calls_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = make_config(root)
            printed = io.StringIO()
            with redirect_stdout(printed):
                main([
                    "COAD", "--input", str(config.corpus_manifest), "--output", str(root / "plan"),
                    "--criteria", str(config.criteria), "--target", "EGFR", "--dry-run", "--json",
                ])
            payload = json.loads(printed.getvalue())
            self.assertEqual(payload["model_calls"], 10)
            target = payload["targets"][0]
            self.assertEqual(target["aliases"], ["ERBB1", "HER1"])
            self.assertEqual([doc["file"] for doc in target["documents"]], ["PMC1.txt", "PMC2.txt", "PMC3.txt", "trial-EGFR-NCT1.txt"])
            self.assertEqual(target["excluded"], {"does not mention EGFR or ERBB1 or HER1": 1})
            self.assertEqual(payload["rules"][0]["met_when"], "at least 2 document(s) answer yes")
            self.assertEqual(payload["rules"][-1]["verdict"], "R1 and R2")
            self.assertFalse((root / "plan").exists())


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


if __name__ == "__main__":
    unittest.main()
