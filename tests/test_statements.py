import logging
import unittest

from parseltongue import System
from parseltongue.core.atoms import Symbol

from agnostik.statements import load_statements, split_statements

logging.getLogger("parseltongue").setLevel(logging.CRITICAL)

PAPER = "Compound X inhibits EGFR. Xenograft tumours shrank."


def paper_system():
    system = System(overridable=False)
    system.register_document("PMC1", PAPER)
    return system


def fact(name, value, quote):
    return f'(fact {name} {value} :evidence (evidence "PMC1" :quotes ("{quote}") :explanation "e"))'


class SplitStatementTests(unittest.TestCase):
    def test_an_unmatched_closing_parenthesis_drops_nothing_after_it(self):
        pieces, notes = split_statements('(fact a 1 :origin "o"))\n(fact b 2 :origin "o")')
        self.assertEqual([text for _, text in pieces], ['(fact a 1 :origin "o")', '(fact b 2 :origin "o")'])
        self.assertEqual(notes, ["ignored 1 unmatched ')' on line 1"])

    def test_an_unfinished_last_statement_is_dropped_and_noted(self):
        pieces, notes = split_statements('(fact a 1 :origin "o")\n(fact b 2 :origin "o"')
        self.assertEqual(len(pieces), 1)
        self.assertEqual(notes, ["dropped an unfinished statement starting on line 2"])

    def test_parentheses_inside_strings_and_comments_do_not_count(self):
        source = '; a comment with ) in it\n(fact a 1 :origin "text with ) and (")'
        pieces, notes = split_statements(source)
        self.assertEqual(len(pieces), 1)
        self.assertEqual(notes, [])

    def test_code_fences_around_the_output_are_ignored_and_noted(self):
        pieces, notes = split_statements('```scheme\n(fact a 1 :origin "o")\n```')
        self.assertEqual(len(pieces), 1)
        self.assertEqual(notes, ["ignored text outside any statement on line 1, 3"])


class LoadStatementTests(unittest.TestCase):
    def test_names_are_namespaced_and_references_follow(self):
        system = paper_system()
        report = load_statements(
            system,
            fact("inhibitor", "true", "Compound X inhibits EGFR.") + "\n(derive r1 inhibitor :using (inhibitor))",
            prefix="pmc1.",
        )
        self.assertEqual(report.names, ["pmc1.inhibitor", "pmc1.r1"])
        self.assertEqual(report.failed, [])
        self.assertTrue(system.engine.facts["pmc1.inhibitor"].origin.verified)
        self.assertIs(system.evaluate(Symbol("pmc1.r1")), True)

    def test_a_reference_written_without_its_prefix_resolves_to_the_earlier_name(self):
        system = paper_system()
        load_statements(system, fact("inhibitor", "true", "Compound X inhibits EGFR."), prefix="pmc1.")
        report = load_statements(system, "(derive pmc1.r1 inhibitor :using (inhibitor))", prefix="pmc1.")
        self.assertEqual(report.failed, [])
        self.assertEqual(system.engine.theorems["pmc1.r1"].derivation, ["pmc1.inhibitor"])

    def test_a_reused_name_is_loaded_beside_the_original_with_a_diff(self):
        system = paper_system()
        report = load_statements(
            system,
            fact("tumours-shrank", "true", "Xenograft tumours shrank.") + '\n(fact tumours-shrank false :origin "second reading")',
        )
        self.assertIs(system.engine.facts["tumours-shrank"].wff, True)
        self.assertIs(system.engine.facts["tumours-shrank.2"].wff, False)
        self.assertEqual(report.renamed, [{"line": 2, "name": "tumours-shrank", "loaded_as": "tumours-shrank.2", "diff": "tumours-shrank.clash"}])
        self.assertIn("tumours-shrank.clash", system.engine.diffs)
        self.assertFalse(system.consistency().consistent)

    def test_terms_and_theorems_are_never_overwritten_either(self):
        system = paper_system()
        load_statements(system, '(defterm score 1 :origin "o")\n(defterm score 2 :origin "o")')
        self.assertEqual(system.evaluate(Symbol("score")), 1)
        self.assertEqual(system.evaluate(Symbol("score.2")), 2)

    def test_a_failing_statement_does_not_stop_the_rest(self):
        system = paper_system()
        report = load_statements(
            system,
            "(derive broken (> missing 1) :using (missing))\n" + fact("inhibitor", "true", "Compound X inhibits EGFR."),
        )
        self.assertEqual(report.names, ["inhibitor"])
        self.assertEqual(len(report.failed), 1)
        self.assertIn("missing", report.failed[0]["error"])

    def test_statements_other_than_directives_are_recorded_not_evaluated(self):
        report = load_statements(paper_system(), '(import (quote other.module))\n(fact a 1 :origin "o")')
        self.assertEqual(report.names, ["a"])
        self.assertIn("not a fact", report.failed[0]["error"])

    def test_an_empty_output_is_noted(self):
        self.assertEqual(load_statements(paper_system(), "").repairs, ["no statements in the output"])

    def test_loaded_statements_replay_into_another_system_unchanged(self):
        first = paper_system()
        report = load_statements(
            first,
            fact("inhibitor", "true", "Compound X inhibits EGFR.")
            + '\n(fact inhibitor false :origin "again")\n(derive r1 inhibitor :using (inhibitor))',
            prefix="pmc1.",
        )
        second = paper_system()
        replayed = load_statements(second, report.source)
        self.assertEqual(replayed.failed, [])
        self.assertEqual(replayed.renamed, [])
        self.assertEqual(sorted(second.engine.facts), sorted(first.engine.facts))
        self.assertEqual(sorted(second.engine.diffs), sorted(first.engine.diffs))
        self.assertIs(second.evaluate(Symbol("pmc1.r1")), True)


if __name__ == "__main__":
    unittest.main()
