#!/usr/bin/env python3
"""Offline unit tests for the AI-output guards in server.py (no API key, no network, no groq package).

    python3 cube-mvp/tests/test_recipes.py
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # noqa: E402

MATS = [
    {"id": "m_stepper_motor", "name": "Stepper Motor", "qty": 2},
    {"id": "m_pulley", "name": "Pulley", "qty": 2},
    {"id": "m_zip_tie", "name": "Zip Tie", "qty": 6},
    {"id": "m_cardboard_tube", "name": "Cardboard Tube", "qty": 3},
]
IDS = {m["id"] for m in MATS}

GOOD = {
    "id": "Hand Crank!", "title": "Hand-Crank Winch", "pitch": "A tabletop winch.",
    "uses_material_ids": [],  # deliberately wrong: server must recompute
    "recipes": [
        {"a": "m_stepper_motor", "b": "m_pulley", "result_id": "crank_unit", "result_name": "Crank Unit", "result_short": "cu"},
        {"a": "crank_unit", "b": "m_cardboard_tube", "result_id": "winch", "result_name": "Winch", "result_short": "WINCHX"},
    ],
    "final_requires": [{"id": "winch", "qty": 1}, {"id": "m_zip_tie", "qty": 2}],
}


def check(idea):
    return server.validate_idea(idea, IDS)


class ValidatorTests(unittest.TestCase):
    def test_good_idea_is_normalised(self):
        idea, problems = check(copy.deepcopy(GOOD))
        self.assertEqual(problems, [])
        self.assertEqual(idea["id"], "hand_crank")
        self.assertEqual(idea["uses_material_ids"], ["m_cardboard_tube", "m_pulley", "m_stepper_motor", "m_zip_tie"])
        self.assertEqual(idea["recipes"][0]["result_short"], "CU")
        self.assertEqual(idea["recipes"][1]["result_short"], "WI")  # invalid 'WINCHX' -> derived from name

    def test_unknown_id(self):
        bad = copy.deepcopy(GOOD); bad["recipes"][0]["a"] = "m_made_up"
        self.assertTrue(any("unknown id" in p for p in check(bad)[1]))

    def test_result_id_collides_with_material(self):
        bad = copy.deepcopy(GOOD); bad["recipes"][0]["result_id"] = "m_zip_tie"
        self.assertTrue(any("collides" in p for p in check(bad)[1]))

    def test_duplicate_result_id(self):
        bad = copy.deepcopy(GOOD); bad["recipes"][1]["result_id"] = "crank_unit"
        self.assertTrue(any("collides" in p for p in check(bad)[1]))

    def test_forward_reference(self):
        bad = copy.deepcopy(GOOD); bad["recipes"].reverse()
        self.assertTrue(any("unknown id" in p for p in check(bad)[1]))

    def test_repeated_pair_is_rejected_in_either_order(self):
        bad = copy.deepcopy(GOOD)
        bad["recipes"].append({"a": "m_pulley", "b": "m_stepper_motor", "result_id": "twin", "result_name": "Twin", "result_short": "TW"})
        bad["final_requires"].append({"id": "twin", "qty": 1})
        self.assertTrue(any("repeats the pair" in p for p in check(bad)[1]))

    def test_dead_end_recipe(self):
        bad = copy.deepcopy(GOOD); bad["final_requires"] = [{"id": "m_zip_tie", "qty": 2}]
        self.assertTrue(any("dead-end" in p for p in check(bad)[1]))

    def test_quantity_limits(self):
        for qty in (0, -1, 99, "2", 1.5, True):
            bad = copy.deepcopy(GOOD); bad["final_requires"][0]["qty"] = qty
            self.assertTrue(check(bad)[1], f"qty {qty!r} should be rejected")

    def test_too_many_recipes(self):
        bad = copy.deepcopy(GOOD)
        bad["recipes"] = [dict(GOOD["recipes"][0], result_id=f"r{i}", result_name=f"R{i}") for i in range(7)]
        self.assertTrue(any("recipes (max" in p for p in check(bad)[1]))

    def test_markup_is_stripped(self):
        bad = copy.deepcopy(GOOD); bad["title"] = "<img src=x onerror=alert(1)>Winch"; bad["pitch"] = "ok <b>bold</b>"
        idea, problems = check(bad)
        self.assertEqual(problems, [])
        self.assertNotIn("<", idea["title"] + idea["pitch"])

    def test_duplicate_titles_and_ids_are_handled(self):
        a, b, c = copy.deepcopy(GOOD), copy.deepcopy(GOOD), copy.deepcopy(GOOD)
        b["title"] = "hand-crank winch"          # same title, different case -> rejected
        c["title"] = "Another Winch"              # same id as a -> id is suffixed
        rejected = []
        out = server.validate_and_clean({"ideas": [a, b, c]}, MATS, rejected)
        self.assertEqual([i["title"] for i in out], ["Hand-Crank Winch", "Another Winch"])
        self.assertEqual(len({i["id"] for i in out}), 2)
        self.assertEqual(len(rejected), 1)

    def test_idea_cap(self):
        ideas = []
        for i in range(15):
            g = copy.deepcopy(GOOD); g["title"] = f"Winch {i}"; ideas.append(g)
        self.assertEqual(len(server.validate_and_clean({"ideas": ideas}, MATS)), server.MAX_IDEAS)

    def test_garbage_input_does_not_crash(self):
        for data in (None, [], {"ideas": None}, {"ideas": [None, 5, "x", {}]}, {"ideas": [{"recipes": [None], "final_requires": [None], "title": "t", "pitch": "p"}]}):
            self.assertEqual(server.validate_and_clean(data, MATS), [])


class HelperTests(unittest.TestCase):
    def test_api_schema_strips_unsupported_bounds(self):
        out = server.api_schema(server.IDEA_SCHEMA)
        arr = out["properties"]["ideas"]
        self.assertNotIn("minItems", arr)
        self.assertNotIn("maxItems", arr)
        self.assertIn("at least 6", arr["description"])
        self.assertIn("minItems", server.IDEA_SCHEMA["properties"]["ideas"])  # original untouched

    def test_steps_numbering_and_markup_removed(self):
        steps = ["1. Glue the tube.", "Step 2: Tie it", "3) <b>Test</b> gently", "- Done", "", None, 7]
        self.assertEqual(server.clean_steps(steps), ["Glue the tube.", "Tie it", "Test gently", "Done"])
        self.assertEqual(len(server.clean_steps(["x"] * 20)), 9)

    def test_source_suggestions_are_sanitized_and_scoped(self):
        data = {"suggestions": [
            {"material": "Cardboard", "places": ["<b>Reuse center</b>", "Reuse center", "Frame shop"],
             "salvage_tip": "Use a <script>bad</script> clean box.", "safety_note": "Ask first."},
            {"material": "Invented part", "places": ["Nowhere"], "salvage_tip": "", "safety_note": ""},
        ]}
        out = server.clean_source_suggestions(data, ["Cardboard"])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["material"], "Cardboard")
        self.assertEqual(out[0]["places"], ["Reuse center", "Frame shop"])
        self.assertNotIn("<", out[0]["salvage_tip"])

    def test_identify_input_checks(self):
        for bad in (None, "", "not a data url", "data:text/html;base64,AAAA", "data:image/svg+xml;base64,AAAA"):
            with self.assertRaises(ValueError):
                server.identify_material(bad)
        huge = "data:image/jpeg;base64," + "A" * (server.MAX_IMAGE_B64_CHARS + 1)
        with self.assertRaises(ValueError):
            server.identify_material(huge)


if __name__ == "__main__":
    unittest.main(verbosity=2)
