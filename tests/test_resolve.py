import json
import os
from pathlib import Path
import tempfile
import unittest

from agnostik.candidates import resolution_file
from agnostik.targets.opentargets import DiseaseHit, DiseaseRef
from agnostik.targets.resolve import cancer_term_for, gdc_project_name, resolve_disease


GI, CANCER = {"id": "EFO_0010282"}, {"id": "MONDO_0045024"}  # gastrointestinal disease, cancer
PARENTS = [
    {"id": "MONDO_0004970", "name": "adenocarcinoma", "therapeuticAreas": [CANCER]},
    {"id": "MONDO_P", "name": "rectal carcinoma", "therapeuticAreas": [GI, CANCER]},
]


def make_http(gdc_name="Rectum Adenocarcinoma", hits=None):
    hits = hits if hits is not None else [{"id": "MONDO_0002169", "name": "rectum adenocarcinoma", "score": 500.0}]
    queries = []

    def http(url, payload=None):
        if "gdc.cancer.gov" in url:
            return {"data": {"name": gdc_name}} if gdc_name else {"message": "TCGA-ZZZ not found"}
        queries.append(payload["query"])
        if "DiseaseContext" in payload["query"]:
            disease = {"name": "rectum adenocarcinoma", "therapeuticAreas": [GI, CANCER], "parents": PARENTS}
            return {"data": {"disease": disease}}
        return {"data": {"search": {"hits": hits}}}

    http.queries = queries
    return http


class ResolveTests(unittest.TestCase):
    def test_gdc_name_for_code(self) -> None:
        self.assertEqual(gdc_project_name("read", http=make_http()), "Rectum Adenocarcinoma")

    def test_unknown_code_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "not found"):
            gdc_project_name("ZZZ", http=make_http(gdc_name=None))

    def test_exact_match_has_no_warnings(self) -> None:
        resolution = resolve_disease("READ", http=make_http())

        self.assertEqual(resolution.disease_id, "MONDO_0002169")
        self.assertEqual(resolution.cancer_term, "rectum adenocarcinoma")
        self.assertEqual(resolution.source, "gdc")
        self.assertEqual(resolution.warnings, ())

    def test_inexact_and_close_matches_warn(self) -> None:
        hits = [
            {"id": "MONDO_1", "name": "colorectal cancer", "score": 100.0},
            {"id": "MONDO_2", "name": "colon carcinoma", "score": 80.0},
        ]
        resolution = resolve_disease("COAD", http=make_http("Colon Adenocarcinoma", hits))

        self.assertEqual(resolution.disease_id, "MONDO_1")
        self.assertEqual(len(resolution.warnings), 2)
        self.assertEqual(resolution.alternatives, (DiseaseHit("MONDO_2", "colon carcinoma", 80.0),))

    def test_disease_id_skips_search(self) -> None:
        http = make_http()
        resolution = resolve_disease("READ", disease_id="MONDO_9", http=http)

        self.assertEqual(resolution.disease_id, "MONDO_9")
        self.assertEqual(resolution.source, "disease-id")
        self.assertFalse(any("SearchDisease" in query for query in http.queries))

    def test_keeps_only_organ_specific_parents(self) -> None:
        resolution = resolve_disease("READ", http=make_http())

        self.assertEqual(resolution.parents, (DiseaseRef("MONDO_P", "rectal carcinoma"),))  # not "adenocarcinoma"

    def test_no_parents_option(self) -> None:
        self.assertEqual(resolve_disease("READ", include_parents=False, http=make_http()).parents, ())

    def test_close_runner_up_that_is_a_parent_does_not_warn(self) -> None:
        hits = [
            {"id": "MONDO_0002169", "name": "rectum adenocarcinoma", "score": 100.0},
            {"id": "MONDO_P", "name": "rectal carcinoma", "score": 90.0},
        ]

        self.assertEqual(resolve_disease("READ", http=make_http(hits=hits)).warnings, ())
        self.assertEqual(len(resolve_disease("READ", include_parents=False, http=make_http(hits=hits)).warnings), 1)

    def test_disease_name_skips_gdc(self) -> None:
        http = make_http(gdc_name=None)
        resolution = resolve_disease("READ", disease="rectal cancer", http=http)

        self.assertEqual(resolution.cancer_term, "rectal cancer")
        self.assertEqual(resolution.source, "disease")

    def test_no_hits_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "--disease-id"):
            resolve_disease("READ", http=make_http(hits=[]))

    def test_cancer_term_prefers_saved_resolution(self) -> None:
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                self.assertEqual(cancer_term_for("READ", http=make_http()), "rectum adenocarcinoma")
                saved = resolution_file("READ")
                saved.parent.mkdir(parents=True)
                saved.write_text(json.dumps({"cancer_term": "rectal cancer"}), encoding="utf-8")
                self.assertEqual(cancer_term_for("READ", http=make_http(gdc_name=None)), "rectal cancer")
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
