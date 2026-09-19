"""Compiler Overpass QL: settings, AND, union, difference, around, out center qt."""

from __future__ import annotations

import unittest

from services.live.engine import (
    clause,
    compile_query,
    eq,
    exists,
    neq,
    nregex,
    regex,
)


class CompileQueryTest(unittest.TestCase):
    def test_settings_json_timeout_no_turbo_shortcuts(self) -> None:
        ql = compile_query(
            (45.0, 7.5, 45.2, 7.8),
            (clause("node", eq("railway", "station"), eq("train", "yes")),),
            timeout=12,
            limit=10,
        )
        self.assertTrue(ql.startswith("[out:json][timeout:12];"))
        self.assertNotIn("{{", ql)
        self.assertNotIn("geocodeArea", ql)
        self.assertIn("out center 10;", ql)
        self.assertNotIn(">;", ql)
        self.assertNotIn("out body", ql)
        self.assertNotIn(" qt;", ql)

    def test_and_filters_on_same_object(self) -> None:
        ql = compile_query(
            None,
            (
                clause(
                    "node",
                    eq("railway", "station"),
                    eq("train", "yes"),
                    exists("wikidata"),
                    neq("station", "subway"),
                ),
            ),
            timeout=12,
            limit=40,
            around=(45.06775, 7.68249, 11000),
        )
        self.assertIn(
            'node["railway"="station"]["train"="yes"]["wikidata"]["station"!="subway"]'
            "(around:11000,45.06775,7.68249);",
            ql,
        )
        self.assertNotIn("(\n", ql)

    def test_union_or_and_difference(self) -> None:
        ql = compile_query(
            (45.0, 7.5, 45.2, 7.8),
            (
                clause("rel", eq("leisure", "stadium"), exists("wikidata")),
                clause("way", eq("leisure", "stadium"), eq("sport", "soccer")),
            ),
            timeout=12,
            limit=8,
            minus=(clause("way", nregex("name", "pala", ignore_case=True)),),
        )
        self.assertIn("(\n", ql)
        self.assertIn('rel["leisure"="stadium"]["wikidata"](45.0,7.5,45.2,7.8);', ql)
        self.assertIn('way["leisure"="stadium"]["sport"="soccer"](45.0,7.5,45.2,7.8);', ql)
        self.assertIn('- way["name"!~"pala",i](45.0,7.5,45.2,7.8);', ql)

    def test_regex_and_kind_way(self) -> None:
        ql = compile_query(
            None,
            (clause("way", eq("shop", "mall"), regex("name", "Shopville|Le Gru", ignore_case=True)),),
            timeout=10,
            limit=12,
            around=(45.07, 7.68, 18000),
        )
        self.assertIn('way["shop"="mall"]["name"~"Shopville|Le Gru",i](around:18000,45.07,7.68);', ql)
        self.assertNotIn("{{bbox}}", ql)


if __name__ == "__main__":
    unittest.main()
