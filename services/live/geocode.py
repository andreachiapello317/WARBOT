"""Geocoder OSM sostituibile, con cache. Non martellare Nominatim pubblico."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

USER_AGENT = "WARBOT/1.0 (OSM WORLD; geocoder cache; not bulk)"
PHOTON_URL = "https://photon.komoot.io/api/"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CACHE_TTL = 6 * 3600
NOMINATIM_GAP = 1.1

# south, west, north, east
BBox = tuple[float, float, float, float]

_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_nom_lock = threading.Lock()
_nom_last = 0.0


class Geocoder(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        """Restituisce luoghi: name, country, lat, lon, bbox, display."""


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 18) -> Any:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _bbox_from_point(lat: float, lon: float, span: float = 0.35) -> BBox:
    return (lat - span, lon - span, lat + span, lon + span)


def _usable_bbox(lat: float, lon: float, bbox: BBox | None) -> tuple[BBox, str]:
    if not bbox:
        return _bbox_from_point(lat, lon), ""
    south, west, north, east = bbox
    if south >= north or west >= east:
        return _bbox_from_point(lat, lon), ""
    if (north - south) > 1.2 or (east - west) > 1.2:
        return _bbox_from_point(lat, lon, 0.4), "area intorno al centro (il riquadro intero è troppo largo per Overpass)"
    return bbox, ""


def _place(
    *,
    name: str,
    country: str,
    lat: float,
    lon: float,
    bbox: BBox | None,
    source: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    box, note = _usable_bbox(lat, lon, bbox)
    display = f"{name}, {country}" if country and country.lower() not in name.lower() else name
    row = {
        "name": name,
        "country": country,
        "display": display,
        "lat": lat,
        "lon": lon,
        "bbox": box,
        "bbox_note": note,
        "source": source,
    }
    if extra:
        row.update(extra)
    return row


class PhotonGeocoder:
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        url = PHOTON_URL + "?" + urllib.parse.urlencode({"q": query, "limit": str(limit), "lang": "it"})
        payload = _get_json(url)
        hits: list[dict[str, Any]] = []
        for feat in payload.get("features") or []:
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            props = feat.get("properties") or {}
            name = str(props.get("name") or props.get("city") or query).strip()
            country = str(props.get("country") or props.get("countrycode") or "").strip()
            extent = props.get("extent")
            bbox = None
            if isinstance(extent, list) and len(extent) == 4:
                west, south, east, north = (float(v) for v in extent)
                bbox = (south, west, north, east)
            hits.append(
                _place(
                    name=name,
                    country=country,
                    lat=lat,
                    lon=lon,
                    bbox=bbox,
                    source="photon",
                    extra={"osm_key": str(props.get("osm_key") or ""), "osm_value": str(props.get("osm_value") or "")},
                )
            )
        return hits


class NominatimGeocoder:
    """Backend Nominatim-compatibile. Default: istanza pubblica, 1 req/s, solo cache miss."""

    def __init__(self, base_url: str = NOMINATIM_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        global _nom_last
        with _nom_lock:
            wait = NOMINATIM_GAP - (time.time() - _nom_last)
            if wait > 0:
                time.sleep(wait)
            _nom_last = time.time()
        url = self.base_url + "?" + urllib.parse.urlencode(
            {"q": query, "format": "jsonv2", "addressdetails": "1", "limit": str(limit)}
        )
        payload = _get_json(url)
        hits: list[dict[str, Any]] = []
        if not isinstance(payload, list):
            return hits
        for row in payload:
            try:
                lat, lon = float(row["lat"]), float(row["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            addr = row.get("address") or {}
            name = str(row.get("name") or addr.get("city") or addr.get("town") or query).strip()
            country = str(addr.get("country") or "").strip()
            bbox = None
            raw_bb = row.get("boundingbox")
            if isinstance(raw_bb, list) and len(raw_bb) == 4:
                south, north, west, east = (float(v) for v in raw_bb)
                bbox = (south, west, north, east)
            hits.append(
                _place(
                    name=name or str(row.get("display_name") or query).split(",")[0],
                    country=country,
                    lat=lat,
                    lon=lon,
                    bbox=bbox,
                    source="nominatim",
                    extra={
                        "display_raw": str(row.get("display_name") or ""),
                        "osm_value": str(row.get("addresstype") or row.get("type") or ""),
                    },
                )
            )
        return hits


def _backend() -> str:
    return (os.getenv("OSM_GEOCODER") or "photon").strip().lower()


def _run_backend(name: str, query: str, limit: int) -> list[dict[str, Any]]:
    custom = (os.getenv("OSM_GEOCODER_URL") or "").strip()
    if name == "nominatim" or custom:
        url = custom or NOMINATIM_URL
        return NominatimGeocoder(url).search(query, limit=limit)
    return PhotonGeocoder().search(query, limit=limit)


def geocode(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Cerca un luogo per nome. Cache lunga; Nominatim solo se Photon è vuoto o è il backend scelto."""
    q = " ".join((query or "").split())
    if len(q) < 2:
        return {"ok": False, "error": "scrivi almeno due lettere", "hits": [], "query": q}
    key = f"{_backend()}|{q.lower()}|{limit}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return {"ok": True, "hits": hit[1], "query": q, "cached": True}

    primary = _backend()
    fallback = "nominatim" if primary != "nominatim" else "photon"
    rows: list[dict[str, Any]] = []
    error = ""
    try:
        rows = _run_backend(primary, q, limit)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, KeyError) as exc:
        error = str(exc)
    if not rows:
        try:
            rows = _run_backend(fallback, q, limit)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, KeyError) as exc:
            error = error or str(exc)
    if not rows:
        return {"ok": False, "error": error or "nessun luogo trovato", "hits": [], "query": q}

    def _rank(hit: dict[str, Any]) -> tuple:
        kind = str(hit.get("osm_value") or "").lower()
        prefer = {"city": 0, "town": 1, "municipality": 2, "village": 3, "suburb": 4, "administrative": 5}
        return (prefer.get(kind, 8), hit.get("name") or "")

    rows.sort(key=_rank)
    _CACHE[key] = (now, rows)
    return {"ok": True, "hits": rows, "query": q, "cached": False}
