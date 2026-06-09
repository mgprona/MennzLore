"""
tests/test_xml_unwrap.py
========================
Unit tests for engine/phase3_global_lore._unwrap_xml_arrays (Bug #3, #3 N-layer)
and engine/phase3_auto_verify._as_list (Bug #5, #16).

Run:
    python -m pytest tests/ -v
or:
    python tests/test_xml_unwrap.py
"""
import sys
import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR.parent))

from engine.phase3_global_lore import _unwrap_xml_arrays
from engine.phase3_auto_verify import _as_list


class TestUnwrapXmlArrays(unittest.TestCase):
    """Bug #3 + Bug #3 N-layer — unwrap JSON arrays wrapped by MCP layer."""

    def test_no_wrap(self):
        self.assertEqual(_unwrap_xml_arrays([1, 2, 3]), [1, 2, 3])

    def test_single_wrap_list(self):
        self.assertEqual(
            _unwrap_xml_arrays({"item": [1, 2, 3]}),
            [1, 2, 3],
        )

    def test_double_wrap_list(self):
        self.assertEqual(
            _unwrap_xml_arrays({"item": {"item": [1, 2, 3]}}),
            [1, 2, 3],
        )

    def test_triple_wrap_list(self):
        """Bug #3 N-layer — MCP can wrap up to 3 layers."""
        self.assertEqual(
            _unwrap_xml_arrays({"item": {"item": {"item": [1, 2, 3]}}}),
            [1, 2, 3],
        )

    def test_quad_wrap_list(self):
        """Defensive: handle 4+ layers too."""
        self.assertEqual(
            _unwrap_xml_arrays({"item": {"item": {"item": {"item": [1, 2, 3]}}}}),
            [1, 2, 3],
        )

    def test_wrap_dict_of_strings(self):
        """A wrapped scalar string."""
        self.assertEqual(_unwrap_xml_arrays({"item": "hello"}), "hello")

    def test_wrap_scalar_int(self):
        self.assertEqual(_unwrap_xml_arrays({"item": 42}), 42)

    def test_non_item_dict_passthrough(self):
        data = {"name": "John", "age": 30}
        self.assertEqual(_unwrap_xml_arrays(data), data)

    def test_sibling_keys_preserved(self):
        """Dict with multiple keys is real data, not a wrapper."""
        data = {"item": [1, 2], "other": "x"}
        result = _unwrap_xml_arrays(data)
        self.assertEqual(result, {"item": [1, 2], "other": "x"})

    def test_nested_mixed(self):
        data = {
            "a": [1, 2],
            "b": {"item": [3, 4]},
            "c": {"item": {"item": [5, 6]}},
        }
        result = _unwrap_xml_arrays(data)
        self.assertEqual(result, {"a": [1, 2], "b": [3, 4], "c": [5, 6]})

    def test_doyle_case_realistic(self):
        """The actual shape seen in production logs."""
        data = {
            "characters": {
                "item": {
                    "item": [
                        {"name": "Watson"},
                        {"name": "Holmes"},
                    ]
                }
            }
        }
        result = _unwrap_xml_arrays(data)
        self.assertEqual(result, {"characters": [{"name": "Watson"}, {"name": "Holmes"}]})

    def test_idempotent(self):
        data = {"item": {"item": [1, 2, 3]}}
        once = _unwrap_xml_arrays(data)
        twice = _unwrap_xml_arrays(once)
        self.assertEqual(once, twice)
        # And again
        thrice = _unwrap_xml_arrays(twice)
        self.assertEqual(once, thrice)

    def test_empty_list(self):
        self.assertEqual(_unwrap_xml_arrays([]), [])
        self.assertEqual(_unwrap_xml_arrays({"item": []}), [])

    def test_none(self):
        self.assertIsNone(_unwrap_xml_arrays(None))

    def test_recursive_in_nested_dict(self):
        """When walking nested dicts, the wrap-removal must apply at every level."""
        data = {
            "book_metadata": {"title": {"item": "A Study in Scarlet"}},
            "characters": {"item": {"item": [{"name": "Holmes"}]}},
        }
        result = _unwrap_xml_arrays(data)
        self.assertEqual(
            result,
            {
                "book_metadata": {"title": "A Study in Scarlet"},
                "characters": [{"name": "Holmes"}],
            },
        )


class TestAsList(unittest.TestCase):
    """Bug #5 + Bug #16 — coerce string/list/wrapped to list of strings."""

    def test_plain_string(self):
        self.assertEqual(_as_list("EP001"), ["EP001"])

    def test_plain_list(self):
        self.assertEqual(_as_list(["EP001", "EP002"]), ["EP001", "EP002"])

    def test_single_wrap_dict(self):
        """Bug #16 — {item: EP001} should unwrap to ['EP001']."""
        self.assertEqual(_as_list({"item": "EP001"}), ["EP001"])

    def test_single_wrap_list(self):
        self.assertEqual(_as_list({"item": ["EP001", "EP002"]}), ["EP001", "EP002"])

    def test_none(self):
        self.assertEqual(_as_list(None), [])

    def test_empty_list(self):
        self.assertEqual(_as_list([]), [])

    def test_list_with_none(self):
        self.assertEqual(_as_list(["EP001", None, "EP002"]), ["EP001", "EP002"])

    def test_number(self):
        self.assertEqual(_as_list(42), ["42"])

    def test_dict_with_other_keys(self):
        """A dict that's not a wrapper passes through str() unchanged."""
        # This is not a clean result but documents the current behavior.
        result = _as_list({"name": "John"})
        self.assertEqual(result, ["{'name': 'John'}"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
