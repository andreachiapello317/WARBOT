"""OSM WORLD: query per categoria, ranking, dedup. Senza rete."""

from __future__ import annotations

import unittest

from services.live.engine import PAGE_CAP, PAGE_SIZE
from services.live.osm import (
    OVERPASS_URL,
    accept_aerodrome,
    accept_hospital,
    accept_rail,
    build_osm_query,
    importance_score,
    normalize_element,
)
from services.live.osm import _dedup_rows, _haversine_m, _should_merge


BOX = (45.4, 9.1, 45.5, 9.3)
CENTER = (45.464, 9.19)


class QueryBuilderTest(unittest.TestCase):
    def test_endpoint_mail_ru(self) -> None:
        self.assertEqual(OVERPASS_URL, "https://maps.mail.ru/osm/tools/overpass/api/interpreter")

    def test_page_size_twenty(self) -> None:
        self.assertEqual(PAGE_SIZE, 20)
        self.assertGreaterEqual(PAGE_CAP, PAGE_SIZE)

    def test_airport_query_is_aerodrome_not_runway(self) -> None:
        ql = build_osm_query("aero", BOX, 12, center=CENTER)
        self.assertIn('["aeroway"="aerodrome"]', ql)
        self.assertIn('["name"]', ql)
        self.assertIn('["iata"]', ql)
        self.assertIn("way[", ql)
        self.assertIn("rel[", ql)
        self.assertNotIn("runway", ql)
        self.assertNotIn("taxiway", ql)
        self.assertNotIn("terminal", ql)
        self.assertNotIn("{{bbox}}", ql)
        self.assertTrue(ql.startswith("[out:json]"))

    def test_station_query_passenger_hubs(self) -> None:
        ql = build_osm_query("rail", BOX, 40, center=CENTER)
        self.assertIn('node["railway"="station"]["train"="yes"]', ql)
        self.assertIn('["station"!="subway"]', ql)
        self.assertIn('["station"!="tram"]', ql)
        self.assertIn('["station"!="light_rail"]', ql)
        self.assertNotIn('["railway"="halt"]', ql)
        self.assertNotIn("bus_stop", ql)
        self.assertNotIn("subway_entrance", ql)

    def test_hospital_query_not_clinic(self) -> None:
        ql = build_osm_query("hosp", BOX, 24, center=CENTER)
        self.assertIn('["amenity"="hospital"]', ql)
        self.assertNotIn("clinic", ql)
        self.assertNotIn("pharmacy", ql)
        self.assertNotIn("doctors", ql)

    def test_port_stadium_mall_land(self) -> None:
        port = build_osm_query("port", BOX, 8, center=CENTER)
        self.assertIn('["industrial"="port"]', port)
        self.assertNotIn("pier", port)
        stad = build_osm_query("stad", BOX, 16, center=CENTER)
        self.assertIn('["leisure"="stadium"]', stad)
        mall = build_osm_query("mall", BOX, 16, center=CENTER)
        self.assertIn('["shop"="mall"]', mall)
        self.assertNotIn("supermarket", mall)
        land = build_osm_query("land", BOX, 20, center=CENTER)
        self.assertIn("wikipedia", land)
        self.assertNotIn('["building"="yes"]', land)


class AcceptFilterTest(unittest.TestCase):
    def test_reject_runway_and_heliport(self) -> None:
        self.assertFalse(accept_aerodrome({"aeroway": "runway", "name": "RWY 36"}))
        self.assertFalse(accept_aerodrome({"aeroway": "terminal", "name": "T1"}))
        self.assertFalse(accept_aerodrome({"aeroway": "aerodrome", "aerodrome": "heliport", "name": "Eli"}))
        self.assertTrue(accept_aerodrome({"aeroway": "aerodrome", "name": "Linate", "iata": "LIN"}))

    def test_reject_metro_bus_platform(self) -> None:
        self.assertFalse(accept_rail({"railway": "station", "station": "subway", "train": "yes", "name": "Duomo"}))
        self.assertFalse(accept_rail({"railway": "halt", "train": "yes", "name": "Fermata"}))
        self.assertFalse(accept_rail({"highway": "bus_stop", "name": "Bus"}))
        self.assertFalse(accept_rail({"railway": "platform", "name": "Binario 1"}))
        self.assertFalse(
            accept_rail({"railway": "station", "train": "yes", "subway": "yes", "name": "Fulton Street"})
        )
        self.assertTrue(
            accept_rail({"railway": "station", "train": "yes", "name": "Milano Centrale", "uic_ref": "8300083"})
        )

    def test_hospital_not_clinic(self) -> None:
        self.assertFalse(accept_hospital({"amenity": "clinic", "name": "Studio"}))
        self.assertFalse(accept_hospital({"amenity": "pharmacy", "name": "Farmacia"}))
        self.assertTrue(accept_hospital({"amenity": "hospital", "name": "Niguarda", "emergency": "yes"}))
        self.assertFalse(accept_hospital({"amenity": "hospital", "name": "Pronto Soccorso San Paolo"}))


class RankingDedupTest(unittest.TestCase):
    def test_rail_city_hint_beats_suburb(self) -> None:
        centrale = {
            "name": "Milano Centrale",
            "category": "rail",
            "lat": 45.486,
            "lon": 9.204,
            "_clat": 45.464,
            "_clon": 9.19,
            "_hint": "Milano",
            "train": "yes",
            "uic": "8300083",
            "building": "train_station",
            "tags": {
                "railway": "station",
                "train": "yes",
                "uic_ref": "8300083",
                "building": "train_station",
                "name": "Milano Centrale",
            },
        }
        stura = {
            "name": "Milano Stura",
            "category": "rail",
            "lat": 45.54,
            "lon": 9.21,
            "_clat": 45.464,
            "_clon": 9.19,
            "_hint": "Milano",
            "train": "yes",
            "tags": {"railway": "station", "train": "yes", "name": "Milano Stura"},
        }
        self.assertGreater(importance_score(centrale), importance_score(stura))
        self.assertGreaterEqual(importance_score(centrale), 6)
        self.assertLess(importance_score(stura), 6)
        rer = {
            "name": "Cité Universitaire",
            "category": "rail",
            "lat": 48.82,
            "lon": 2.34,
            "_clat": 48.85,
            "_clon": 2.35,
            "_hint": "Paris",
            "train": "yes",
            "wikipedia": "fr:Gare de Cité universitaire",
            "tags": {
                "railway": "station",
                "train": "yes",
                "name": "Cité Universitaire",
                "wikipedia": "fr:Gare de Cité universitaire",
            },
        }
        self.assertLess(importance_score(rer), 6)

    def test_airport_iata_ranks_above_local(self) -> None:
        lin = {
            "name": "Linate",
            "category": "aero",
            "lat": 45.45,
            "lon": 9.28,
            "_clat": 45.46,
            "_clon": 9.19,
            "iata": "LIN",
            "icao": "LIML",
            "operator": "SEA",
            "tags": {"aeroway": "aerodrome", "iata": "LIN", "icao": "LIML", "aerodrome:type": "international"},
        }
        campo = {
            "name": "Campo volo",
            "category": "aero",
            "lat": 45.50,
            "lon": 9.10,
            "_clat": 45.46,
            "_clon": 9.19,
            "tags": {"aeroway": "aerodrome", "name": "Campo volo"},
        }
        self.assertGreater(importance_score(lin), importance_score(campo))

    def test_dedup_same_station_node_and_way(self) -> None:
        node = {
            "id": "node/1",
            "osm_type": "node",
            "name": "Milano Centrale",
            "category": "rail",
            "lat": 45.4863,
            "lon": 9.2039,
            "uic": "8300083",
            "score": 20,
            "tags": {},
        }
        way = {
            "id": "way/2",
            "osm_type": "way",
            "name": "Stazione di Milano Centrale",
            "category": "rail",
            "lat": 45.4864,
            "lon": 9.2040,
            "uic": "8300083",
            "score": 18,
            "tags": {},
        }
        merged = _dedup_rows([node, way])
        self.assertEqual(len(merged), 1)

    def test_dedup_garibaldi_superficie_passante(self) -> None:
        a = {
            "id": "node/1",
            "osm_type": "node",
            "name": "Milano Porta Garibaldi (superficie)",
            "category": "rail",
            "lat": 45.4848,
            "lon": 9.1876,
            "score": 22,
            "tags": {},
        }
        b = {
            "id": "way/2",
            "osm_type": "way",
            "name": "Milano Porta Garibaldi (passante)",
            "category": "rail",
            "lat": 45.4849,
            "lon": 9.1877,
            "score": 18,
            "tags": {},
        }
        self.assertTrue(_should_merge(a, b))
        self.assertEqual(len(_dedup_rows([a, b])), 1)

    def test_merge_even_if_only_one_has_wikidata(self) -> None:
        a = {
            "id": "node/1",
            "name": "Milano Porta Garibaldi (superficie)",
            "category": "rail",
            "lat": 45.4848,
            "lon": 9.1876,
            "wikidata": "Q123",
            "score": 22,
            "tags": {},
        }
        b = {
            "id": "way/2",
            "name": "Milano Porta Garibaldi (passante)",
            "category": "rail",
            "lat": 45.4849,
            "lon": 9.1877,
            "score": 18,
            "tags": {},
        }
        self.assertTrue(_should_merge(a, b))

    def test_do_not_merge_different_stations(self) -> None:
        a = {
            "id": "node/1",
            "name": "Milano Centrale",
            "category": "rail",
            "lat": 45.486,
            "lon": 9.204,
            "score": 30,
            "tags": {},
        }
        b = {
            "id": "node/2",
            "name": "Milano Porta Garibaldi",
            "category": "rail",
            "lat": 45.485,
            "lon": 9.188,
            "score": 28,
            "tags": {},
        }
        self.assertFalse(_should_merge(a, b))
        self.assertEqual(len(_dedup_rows([a, b])), 2)

    def test_normalize_drops_runway(self) -> None:
        el = {
            "type": "way",
            "id": 9,
            "center": {"lat": 45.45, "lon": 9.28},
            "tags": {"aeroway": "runway", "name": "18/36"},
        }
        self.assertIsNone(normalize_element(el, category="aero"))

    def test_haversine_nearby(self) -> None:
        self.assertLess(_haversine_m(45.4863, 9.2039, 45.4864, 9.2040), 50)


class ExplorerIntentTest(unittest.TestCase):
    def test_parse_stations_near_duomo(self) -> None:
        from services.live.osm import parse_osm_intent

        intent = parse_osm_intent("stazioni vicino al Duomo")
        self.assertEqual(intent["category"], "rail")
        self.assertTrue(intent["near"])
        self.assertIn("Duomo", intent["query"])

    def test_parse_airports_milan(self) -> None:
        from services.live.osm import parse_osm_intent

        intent = parse_osm_intent("aeroporti vicino a Milano")
        self.assertEqual(intent["category"], "aero")
        self.assertEqual(intent["query"].lower(), "milano")

    def test_around_query_uses_around_not_turbo(self) -> None:
        ql = build_osm_query("food", BOX, 16, center=CENTER, around_m=400)
        self.assertIn("around:400,", ql)
        self.assertIn('node["amenity"="restaurant"]["name"]', ql)
        self.assertNotIn("{{", ql)


if __name__ == "__main__":
    unittest.main()
