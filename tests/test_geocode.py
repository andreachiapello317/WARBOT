"""Geocoding: Photon senza lang=it, città prima della provincia."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from services.live.geocode import PhotonGeocoder, collapse_hits, place_kind


def _hit(name: str, *, osm_value: str, lat: float, lon: float, place_type: str = "") -> dict:
    return {
        "name": name,
        "display": f"{name}, Italia",
        "lat": lat,
        "lon": lon,
        "osm_value": osm_value,
        "place_type": place_type,
        "bbox": (lat - 0.05, lon - 0.05, lat + 0.05, lon + 0.05),
        "source": "test",
    }


class CollapseHitsTest(unittest.TestCase):
    def test_cuneo_keeps_city_drops_county_and_station(self) -> None:
        county = _hit("Cuneo", osm_value="administrative", lat=44.458, lon=7.558, place_type="county")
        city = _hit("Cuneo", osm_value="city", lat=44.390, lon=7.548, place_type="city")
        station = _hit("Cuneo", osm_value="station", lat=44.388, lon=7.536, place_type="house")
        hamlet = _hit("Cuneo", osm_value="hamlet", lat=44.126, lon=8.163, place_type="district")
        kept = collapse_hits([county, city, station, hamlet])
        self.assertEqual(len(kept), 1)
        self.assertEqual(place_kind(kept[0]), "city")
        self.assertAlmostEqual(kept[0]["lat"], 44.390, places=3)

    def test_keeps_distinct_names(self) -> None:
        city = _hit("Cuneo", osm_value="city", lat=44.39, lon=7.55)
        other = _hit("Boves", osm_value="town", lat=44.33, lon=7.55)
        kept = collapse_hits([city, other])
        names = {h["name"] for h in kept}
        self.assertEqual(names, {"Cuneo", "Boves"})


class PhotonUrlTest(unittest.TestCase):
    def test_photon_url_omits_lang_it(self) -> None:
        captured: dict = {}

        def fake_json(url: str, timeout: int = 8):
            captured["url"] = url
            return {"features": []}

        with patch("services.live.geocode._get_json", side_effect=fake_json):
            PhotonGeocoder().search("Cuneo")
        self.assertIn("q=Cuneo", captured["url"])
        self.assertNotIn("lang=", captured["url"])


if __name__ == "__main__":
    unittest.main()
