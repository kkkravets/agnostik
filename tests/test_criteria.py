import logging
import unittest

from parseltongue import System
from parseltongue.core.atoms import Symbol

from agnostik.criteria import combination_source, load_criteria, parse_criteria, parse_verdict
from agnostik.formalization import DEFAULT_CRITERIA
from agnostik.statements import load_statements

logging.getLogger("parseltongue").setLevel(logging.CRITICAL)

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

## R5 Provenance
Every fact quotes its document.
"""


def with_rule(old, new):
    return parse_criteria("rules", RULES.replace(old, new))


class CriteriaParsingTests(unittest.TestCase):
    def test_reads_rules_questions_thresholds_and_the_verdict(self):
        criteria = parse_criteria("rules", RULES)
        self.assertEqual([rule.id for rule in criteria.rules], ["R1", "R2", "R3"])
        self.assertEqual([rule.threshold for rule in criteria.rules], [2, 1, None])
        self.assertEqual(criteria.rules[1].kinds, frozenset({"trial"}))
        self.assertEqual(criteria.rules[2].kinds, frozenset({"article", "trial"}))
        self.assertEqual(criteria.rules[0].ask, "Does this publication describe a compound acting on the target?")
        self.assertEqual(criteria.verdict, ("and", "R1", "R2"))
        self.assertEqual(criteria.scope, "Scope: only the supplied documents count.")
        self.assertEqual([rule.id for rule in criteria.for_kind("trial")], ["R2", "R3"])

    def test_the_shipped_criteria_file_parses(self):
        criteria = load_criteria(DEFAULT_CRITERIA)
        self.assertEqual([rule.id for rule in criteria.rules], ["R1", "R2", "R3", "R4", "R5"])
        self.assertEqual(criteria.verdict, ("and", ("and", "R1", "R3"), "R4"))
        self.assertIsNone(criteria.rules[4].threshold)

    def test_verdict_expressions_nest_and_negate(self):
        self.assertEqual(parse_verdict("R1 and (R2 or not R3)"), ("and", "R1", ("or", "R2", ("not", "R3"))))
        for broken in ("R1 and", "(R1 or R2", "R1 R2", "and R1"):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                parse_verdict(broken)

    def test_the_verdict_may_only_name_rules_that_are_counted(self):
        with self.assertRaisesRegex(ValueError, "R3"):
            with_rule("verdict: R1 and R2", "verdict: R1 and R3")
        with self.assertRaisesRegex(ValueError, "R9"):
            with_rule("verdict: R1 and R2", "verdict: R1 and R9")

    def test_malformed_rules_are_rejected_before_any_model_call(self):
        for old, new in (
            ("applies to: publications\n", "applies to: preprints\n"),
            ("    ask: Is this trial in phase 3 or recruiting?\n", ""),
            ("met when: at least 2 documents answer yes", "met when: most documents"),
            ("met when: at least 2 documents answer yes", "met whenever: at least 2"),
            ("    verdict: R1 and R2\n", ""),
        ):
            with self.subTest(new=new), self.assertRaises(ValueError):
                with_rule(old, new)


class CombinationTests(unittest.TestCase):
    def system_with_answers(self, values):
        criteria = parse_criteria("rules", RULES)
        system = System(overridable=False)
        system.register_document("rules", RULES)
        answers = {"R1": [], "R2": [], "R3": []}
        for name, value in values.items():
            load_statements(system, f'(fact {name} {value} :origin "per-document answer")')
            answers[name.split(".")[1].upper()].append(name)
        report = load_statements(system, combination_source(criteria, "egfr-verdict", answers))
        self.assertEqual(report.failed, [])
        return system

    def test_counts_yes_answers_and_decides_the_verdict_by_the_rules(self):
        system = self.system_with_answers({"pmc1.r1": "true", "pmc2.r1": "false", "pmc3.r1": "true", "nct1.r2": "true", "pmc3.r3": "true"})
        self.assertEqual(system.evaluate(Symbol("criteria.r1-count")), 2)
        self.assertIs(system.evaluate(Symbol("criteria.r1-met")), True)
        self.assertEqual(system.evaluate(Symbol("criteria.r3-count")), 1)
        self.assertNotIn("criteria.r3-met", system.engine.terms)
        self.assertIs(system.evaluate(Symbol("egfr-verdict")), True)

    def test_a_rule_below_its_threshold_rejects(self):
        system = self.system_with_answers({"pmc1.r1": "true", "nct1.r2": "true"})
        self.assertIs(system.evaluate(Symbol("criteria.r1-met")), False)
        self.assertIs(system.evaluate(Symbol("egfr-verdict")), False)

    def test_no_answers_count_as_zero(self):
        system = self.system_with_answers({})
        self.assertEqual(system.evaluate(Symbol("criteria.r2-count")), 0)
        self.assertIs(system.evaluate(Symbol("egfr-verdict")), False)

    def test_every_combination_statement_quotes_its_rule_verbatim(self):
        system = self.system_with_answers({"pmc1.r1": "true"})
        for name in ("criteria.r1-count", "criteria.r1-met", "egfr-verdict"):
            self.assertTrue(system.engine.terms[name].origin.verified, name)


if __name__ == "__main__":
    unittest.main()
