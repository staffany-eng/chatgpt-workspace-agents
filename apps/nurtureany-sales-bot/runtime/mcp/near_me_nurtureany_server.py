#!/usr/bin/env python3
"""Known-area near-me MCP adapter for NurtureAny Sales Bot.

This server keeps the "who can I say hi to nearby?" flow review-first and
read-only. It resolves a user location to a curated known area, refreshes live
restaurant candidates from Google Places, builds BigQuery SQL for curated
outlet matches and C360 customers, and merges those source outputs without
mutating HubSpot.
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.c360 import (
    c360_company_url_template as _shared_c360_company_url_template,
    c360_org_url_template as _shared_c360_org_url_template,
    c360_route_key_map as _shared_c360_route_key_map,
    customer360_route_key as _shared_customer360_route_key,
    encode_url_value as _shared_encode_url_value,
    render_c360_url as _shared_render_c360_url,
)
from nurtureany_common.responses import blocked_response


GOOGLE_PLACES_BASE_URL = "https://places.googleapis.com"
GOOGLE_PLACES_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
GOOGLE_PLACES_TIMEOUT_SECONDS = 15
GOOGLE_PLACES_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.location,places.googleMapsUri"
)
MAX_GOOGLE_PLACES_RESULTS = 20
DEFAULT_NEAR_ME_RADIUS_M = 1000
DEFAULT_SNAP_DISTANCE_M = 1500
MAX_OUTLET_MATCH_RESULTS = 100
OUTLET_MATCHES_TABLE_ENV = "NURTUREANY_OUTLET_MATCHES_TABLE"
DEFAULT_OUTLET_MATCHES_TABLE = "staffany-warehouse.analytics.nurtureany_near_me_outlet_matches"
KNOWN_AREAS_FILE_ENV = "NURTUREANY_KNOWN_AREAS_FILE"
C360_COMPANY_URL_TEMPLATE_ENV = "NURTUREANY_C360_COMPANY_URL_TEMPLATE"
C360_ORG_URL_TEMPLATE_ENV = "NURTUREANY_C360_ORG_URL_TEMPLATE"
C360_ROUTE_KEY_BY_COMPANY_ID_ENV = "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID"
DEFAULT_C360_COMPANY_URL_TEMPLATE = "https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}"
DEFAULT_C360_ORG_URL_TEMPLATE = (
    "https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}/orgs/{organisation_id}"
)
DEFAULT_C360_ROUTE_KEY_BY_COMPANY_ID = {
    # Customer 360's canonical Fei Siong route is slug-keyed. The numeric
    # HubSpot route is accepted by the app but renders fallback demo orgs.
    "1991281569": "fei-siong-group",
}
SCOPE_SOURCE = "near_me_nurtureany"
C360_CUSTOMER_RANK_CATEGORIES = {
    "confirmed_outlet_current_customer",
    "c360_current_customer",
    "c360_current_customer_without_stored_outlet",
}

OUTLET_MATCH_COLUMNS = [
    "area_id",
    "area_name",
    "outlet_name",
    "google_place_id",
    "formatted_address",
    "latitude",
    "longitude",
    "google_maps_uri",
    "hubspot_company_id",
    "hubspot_company_name",
    "hubspot_owner_id",
    "organisation_id",
    "match_status",
    "account_status",
    "confidence",
    "source",
    "last_checked_at",
]

DEFAULT_KNOWN_AREAS = [
    {
        "area_id": "sg_raffles_place",
        "area_name": "Raffles Place",
        "country": "Singapore",
        "latitude": 1.283933,
        "longitude": 103.851959,
        "radius_m": 1000,
        "aliases": ["raffles place", "raffles mrt", "cbd", "central business district"],
    },
    {
        "area_id": "sg_vivocity",
        "area_name": "VivoCity",
        "country": "Singapore",
        "latitude": 1.2644,
        "longitude": 103.8223,
        "radius_m": 750,
        "aliases": ["vivocity", "vivo city", "harbourfront", "harbourfront centre"],
    },
    {
        "area_id": "sg_plaza_singapura",
        "area_name": "Plaza Singapura",
        "country": "Singapore",
        "latitude": 1.3007,
        "longitude": 103.8450,
        "radius_m": 700,
        "aliases": ["plaza singapura", "dhoby ghaut", "ps"],
    },
    {
        "area_id": "sg_jewel_changi",
        "area_name": "Jewel Changi Airport",
        "country": "Singapore",
        "latitude": 1.3602,
        "longitude": 103.9898,
        "radius_m": 900,
        "aliases": ["jewel changi", "changi airport", "jewel"],
    },
    {
        "area_id": "sg_suntec_city",
        "area_name": "Suntec City",
        "country": "Singapore",
        "latitude": 1.2931,
        "longitude": 103.8573,
        "radius_m": 800,
        "aliases": ["suntec", "suntec city", "city hall"],
    },
    {
        "area_id": "sg_ion_orchard",
        "area_name": "ION Orchard",
        "country": "Singapore",
        "latitude": 1.3040,
        "longitude": 103.8320,
        "radius_m": 800,
        "aliases": ["ion orchard", "orchard", "orchard road"],
    },
    {
        "area_id": "sg_bugis_junction",
        "area_name": "Bugis Junction",
        "country": "Singapore",
        "latitude": 1.2993,
        "longitude": 103.8558,
        "radius_m": 700,
        "aliases": ["bugis", "bugis junction"],
    },
    {
        "area_id": "sg_nex",
        "area_name": "NEX",
        "country": "Singapore",
        "latitude": 1.3508,
        "longitude": 103.8723,
        "radius_m": 750,
        "aliases": ["nex", "serangoon", "nex serangoon"],
    },
    {
        "area_id": "sg_tampines_mall",
        "area_name": "Tampines Mall",
        "country": "Singapore",
        "latitude": 1.3525,
        "longitude": 103.9447,
        "radius_m": 750,
        "aliases": ["tampines mall", "tampines"],
    },
    {
        "area_id": "sg_jurong_point",
        "area_name": "Jurong Point",
        "country": "Singapore",
        "latitude": 1.3397,
        "longitude": 103.7067,
        "radius_m": 800,
        "aliases": ["jurong point", "boon lay"],
    },
    {
        "area_id": "sg_westgate_jem",
        "area_name": "Westgate / JEM",
        "country": "Singapore",
        "latitude": 1.3331,
        "longitude": 103.7435,
        "radius_m": 800,
        "aliases": ["westgate", "jem", "jurong east"],
    },
    {
        "area_id": "sg_causeway_point",
        "area_name": "Causeway Point",
        "country": "Singapore",
        "latitude": 1.4361,
        "longitude": 103.7862,
        "radius_m": 750,
        "aliases": ["causeway point", "woodlands"],
    },
]


mcp = FastMCP(
    "near_me_nurtureany",
    instructions=(
        "Known-area near-me tools for NurtureAny. Snap user locations to curated "
        "known areas, refresh Google Places live candidates, build BigQuery outlet "
        "match and C360 customer SQL, and merge results without mutating HubSpot."
    ),
)


class NearMeError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _scope(slack_user_email: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {
        "caller_email": (slack_user_email or "").strip().lower(),
        "read_only": True,
        "scope_source": SCOPE_SOURCE,
    }
    if extra:
        scope.update(extra)
    return scope


def _blocked(message: str, scope: dict[str, Any] | None = None, source: str = "Known Area Near-Me") -> dict[str, Any]:
    return blocked_response(message, source, scope)


def _bounded_int(value: Any, default: int, maximum: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _float_value(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _known_area_source_path() -> str:
    raw = os.environ.get(KNOWN_AREAS_FILE_ENV, "").strip()
    if raw and not (raw.startswith("${") and raw.endswith("}")):
        return str(Path(raw).expanduser())
    return ""


def _load_known_areas() -> list[dict[str, Any]]:
    path = _known_area_source_path()
    if not path:
        return [dict(area) for area in DEFAULT_KNOWN_AREAS]

    try:
        payload = json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise NearMeError(f"Invalid {KNOWN_AREAS_FILE_ENV}: {path}") from error

    areas = payload.get("known_areas") if isinstance(payload, dict) else payload
    if not isinstance(areas, list):
        raise NearMeError(f"{KNOWN_AREAS_FILE_ENV} must be a JSON list or object with known_areas.")

    cleaned = []
    for item in areas:
        if not isinstance(item, dict):
            continue
        area_id = str(item.get("area_id") or "").strip()
        area_name = str(item.get("area_name") or item.get("name") or "").strip()
        lat = _float_value(item.get("latitude"))
        lng = _float_value(item.get("longitude"))
        if area_id and area_name and lat is not None and lng is not None:
            next_item = dict(item)
            next_item["area_id"] = area_id
            next_item["area_name"] = area_name
            next_item["latitude"] = lat
            next_item["longitude"] = lng
            next_item["radius_m"] = _bounded_int(item.get("radius_m"), DEFAULT_NEAR_ME_RADIUS_M, 3000, 100)
            cleaned.append(next_item)
    if not cleaned:
        raise NearMeError(f"{KNOWN_AREAS_FILE_ENV} has no valid known areas.")
    return cleaned


def _area_public(area: dict[str, Any], distance_m: float | None = None, snap_status: str = "matched") -> dict[str, Any]:
    payload = {
        "area_id": area["area_id"],
        "area_name": area["area_name"],
        "country": area.get("country") or "Singapore",
        "latitude": area["latitude"],
        "longitude": area["longitude"],
        "radius_m": _bounded_int(area.get("radius_m"), DEFAULT_NEAR_ME_RADIUS_M, 3000, 100),
        "snap_status": snap_status,
    }
    if distance_m is not None:
        payload["distance_m"] = round(distance_m)
    source_path = _known_area_source_path()
    payload["source"] = source_path or "default_curated_known_areas"
    return payload


def _normal_text(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _compact_text(value: Any) -> str:
    return _normal_text(value).replace(" ", "")


def _coordinates_from_text(text: str) -> tuple[float, float] | None:
    if not text:
        return None
    patterns = [
        r"@(?P<lat>-?\d{1,3}(?:\.\d+)?),(?P<lng>-?\d{1,3}(?:\.\d+)?)",
        r"(?:q|query|ll)=\s*(?P<lat>-?\d{1,3}(?:\.\d+)?),\s*(?P<lng>-?\d{1,3}(?:\.\d+)?)",
        r"(?P<lat>-?\d{1,3}\.\d+)\s*,\s*(?P<lng>-?\d{1,3}\.\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        lat = _float_value(match.group("lat"))
        lng = _float_value(match.group("lng"))
        if lat is None or lng is None:
            continue
        if abs(lat) > 90 and abs(lng) <= 90:
            lat, lng = lng, lat
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
    return None


def _area_from_alias(location_text: str, areas: list[dict[str, Any]]) -> dict[str, Any] | None:
    words = _normal_text(location_text)
    if not words:
        return None
    for area in areas:
        candidates = [area.get("area_id"), area.get("area_name"), *(area.get("aliases") or [])]
        for candidate in candidates:
            normalized = _normal_text(candidate)
            if normalized and normalized in words:
                return area
    return None


def _resolve_coordinates(
    location_text: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    areas: list[dict[str, Any]] | None = None,
) -> tuple[float, float, str, dict[str, Any] | None]:
    lat = _float_value(latitude)
    lng = _float_value(longitude)
    if lat is not None and lng is not None:
        if abs(lat) > 90 and abs(lng) <= 90:
            lat, lng = lng, lat
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng, "explicit_lat_lng", None

    parsed = _coordinates_from_text(location_text)
    if parsed:
        return parsed[0], parsed[1], "parsed_location_text", None

    area = _area_from_alias(location_text, areas or _load_known_areas())
    if area:
        return float(area["latitude"]), float(area["longitude"]), "known_area_alias", area

    raise NearMeError("Provide a Google Maps link, shared lat/lng, or known area name.")


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _known_area_by_id(area_id: str, areas: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    normalized = str(area_id or "").strip().lower()
    for area in areas or _load_known_areas():
        if str(area.get("area_id") or "").strip().lower() == normalized:
            return area
    raise NearMeError(f"Unknown known_area: {area_id}")


def _snap_known_area(lat: float, lng: float, areas: list[dict[str, Any]], max_distance_m: int) -> dict[str, Any]:
    ranked = sorted(
        (
            (_haversine_m(lat, lng, float(area["latitude"]), float(area["longitude"])), area)
            for area in areas
        ),
        key=lambda item: item[0],
    )
    if not ranked:
        raise NearMeError("No known areas are configured.")
    distance_m, area = ranked[0]
    snap_status = "matched" if distance_m <= max_distance_m else "nearest_outside_threshold"
    return _area_public(area, distance_m, snap_status)


def _google_places_key() -> str:
    token = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip() or os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not token:
        raise NearMeError("Missing GOOGLE_PLACES_API_KEY.")
    return token


def _request_google_places(body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{GOOGLE_PLACES_BASE_URL}/v1/places:searchNearby",
        data=data,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": GOOGLE_PLACES_USER_AGENT,
            "x-goog-api-key": _google_places_key(),
            "x-goog-fieldmask": GOOGLE_PLACES_FIELD_MASK,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_PLACES_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise NearMeError(f"Google Places API failed: {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise NearMeError(f"Google Places API request timed out or failed: {reason}") from error


def _safe_detail(detail: str) -> str:
    token = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip() or os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    safe = detail.replace(token, "[REDACTED_GOOGLE_PLACES_API_KEY]") if token else detail
    return safe.replace("\n", " ")[:300]


def _place_name(place: dict[str, Any]) -> str:
    display_name = place.get("displayName")
    if isinstance(display_name, dict):
        return str(display_name.get("text") or "").strip()
    return str(display_name or place.get("name") or "").strip()


def _place_location(place: dict[str, Any]) -> tuple[float | None, float | None]:
    location = place.get("location") if isinstance(place.get("location"), dict) else {}
    return _float_value(location.get("latitude")), _float_value(location.get("longitude"))


def _google_place_candidate(place: dict[str, Any], area: dict[str, Any], rank: int) -> dict[str, Any]:
    lat, lng = _place_location(place)
    distance_m = None
    if lat is not None and lng is not None:
        distance_m = _haversine_m(float(area["latitude"]), float(area["longitude"]), lat, lng)
    return {
        "rank": rank,
        "area_id": area["area_id"],
        "area_name": area["area_name"],
        "google_place_id": str(place.get("id") or "").strip(),
        "outlet_name": _place_name(place),
        "formatted_address": str(place.get("formattedAddress") or "").strip(),
        "latitude": lat,
        "longitude": lng,
        "google_maps_uri": str(place.get("googleMapsUri") or "").strip(),
        "distance_m": round(distance_m) if distance_m is not None else None,
        "match_status": "candidate",
        "account_status": "unknown",
        "source": "google_places_live",
        "confidence": "needs-check",
        "store_policy": "live_candidate_only_until_review_approval",
    }


def _outlet_matches_table() -> str:
    table = os.environ.get(OUTLET_MATCHES_TABLE_ENV, "").strip() or DEFAULT_OUTLET_MATCHES_TABLE
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+", table):
        raise NearMeError(f"Invalid {OUTLET_MATCHES_TABLE_ENV}; expected project.dataset.table.")
    return table


def _c360_company_url_template() -> str:
    return _shared_c360_company_url_template()


def _c360_org_url_template() -> str:
    return _shared_c360_org_url_template()


def _c360_route_key_map() -> dict[str, str]:
    return _shared_c360_route_key_map()


def _customer360_route_key(
    hubspot_company_id: Any,
    company_name: Any = "",
    customer360_route_key: Any = "",
) -> str:
    return _shared_customer360_route_key(hubspot_company_id, company_name, customer360_route_key)


def _encode_url_value(value: Any) -> str:
    return _shared_encode_url_value(value)


def _render_c360_url(
    hubspot_company_id: Any,
    organisation_id: Any = "",
    customer360_route_key: Any = "",
    company_name: Any = "",
) -> str:
    return _shared_render_c360_url(
        hubspot_company_id,
        organisation_id,
        customer360_route_key_value=customer360_route_key,
        company_name=company_name,
    )


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _near_me_outlet_matches_sql(area: dict[str, Any], limit: int = MAX_OUTLET_MATCH_RESULTS) -> str:
    lat = float(area["latitude"])
    lng = float(area["longitude"])
    radius_m = _bounded_int(area.get("radius_m"), DEFAULT_NEAR_ME_RADIUS_M, 3000, 100)
    area_id = _sql_literal(area["area_id"])
    area_name = _sql_literal(area["area_name"])
    table = _outlet_matches_table()
    capped_limit = _bounded_int(limit, MAX_OUTLET_MATCH_RESULTS, MAX_OUTLET_MATCH_RESULTS)
    return f"""-- NurtureAny known-area near-me curated outlet matches.
-- Run only through staffany_bigquery.execute_sql_readonly.
-- BigQuery outlet_matches is the memory layer; HubSpot custom objects are not required.
WITH params AS (
  SELECT
    {area_id} AS area_id,
    {area_name} AS area_name,
    {lat:.7f} AS anchor_lat,
    {lng:.7f} AS anchor_lng,
    {radius_m} AS radius_m
),
matches AS (
  SELECT
    outlet_match_id,
    area_id,
    area_name,
    outlet_name,
    google_place_id,
    formatted_address,
    SAFE_CAST(latitude AS FLOAT64) AS latitude,
    SAFE_CAST(longitude AS FLOAT64) AS longitude,
    google_maps_uri,
    hubspot_company_id,
    hubspot_company_name,
    hubspot_owner_id,
    organisation_id,
    LOWER(COALESCE(match_status, 'candidate')) AS match_status,
    LOWER(COALESCE(account_status, 'unknown')) AS account_status,
    COALESCE(confidence, 'needs-check') AS confidence,
    COALESCE(source, 'bigquery_outlet_matches') AS source,
    last_checked_at,
    updated_at
  FROM `{table}`
  WHERE area_id = (SELECT area_id FROM params)
    AND LOWER(COALESCE(match_status, 'candidate')) != 'rejected'
),
scored AS (
  SELECT
    matches.*,
    CASE
      WHEN matches.latitude IS NULL OR matches.longitude IS NULL THEN NULL
      ELSE ST_DISTANCE(
        ST_GEOGPOINT(matches.longitude, matches.latitude),
        ST_GEOGPOINT(params.anchor_lng, params.anchor_lat)
      )
    END AS distance_m
  FROM matches
  CROSS JOIN params
  WHERE (
      matches.latitude IS NULL
      OR matches.longitude IS NULL
      OR (
        matches.latitude BETWEEN -90 AND 90
        AND matches.longitude BETWEEN -180 AND 180
        AND ST_DWITHIN(
          ST_GEOGPOINT(matches.longitude, matches.latitude),
          ST_GEOGPOINT(params.anchor_lng, params.anchor_lat),
          params.radius_m
        )
      )
    )
)
SELECT
  outlet_match_id,
  area_id,
  area_name,
  outlet_name,
  google_place_id,
  formatted_address,
  latitude,
  longitude,
  google_maps_uri,
  hubspot_company_id,
  hubspot_company_name,
  hubspot_owner_id,
  organisation_id,
  match_status,
  account_status,
  confidence,
  source,
  last_checked_at,
  updated_at,
  ROUND(distance_m) AS distance_m
FROM scored
ORDER BY
  CASE match_status WHEN 'confirmed' THEN 0 ELSE 1 END,
  distance_m,
  outlet_name
LIMIT {capped_limit}"""


def _near_me_c360_sql(area: dict[str, Any]) -> str:
    lat = float(area["latitude"])
    lng = float(area["longitude"])
    radius_m = _bounded_int(area.get("radius_m"), DEFAULT_NEAR_ME_RADIUS_M, 3000, 100)
    area_id = _sql_literal(area["area_id"])
    area_name = _sql_literal(area["area_name"])
    return f"""-- NurtureAny known-area near-me C360 customer query.
-- Run only through staffany_bigquery.execute_sql_readonly.
-- Uses geofence rows from kraken_rds.Locations, not person GPS.
WITH params AS (
  SELECT
    {area_id} AS area_id,
    {area_name} AS area_name,
    {lat:.7f} AS anchor_lat,
    {lng:.7f} AS anchor_lng,
    {radius_m} AS radius_m
),
locations AS (
  SELECT
    CAST(sectionid AS STRING) AS section_id,
    SAFE_CAST(latitude AS FLOAT64) AS raw_latitude,
    SAFE_CAST(longitude AS FLOAT64) AS raw_longitude
  FROM `staffany-warehouse.kraken_rds.Locations`
  WHERE latitude IS NOT NULL
    AND longitude IS NOT NULL
),
normalized_locations AS (
  SELECT
    section_id,
    CASE
      WHEN ABS(raw_latitude) > 90 AND ABS(raw_longitude) <= 90 THEN raw_longitude
      ELSE raw_latitude
    END AS latitude,
    CASE
      WHEN ABS(raw_latitude) > 90 AND ABS(raw_longitude) <= 90 THEN raw_latitude
      ELSE raw_longitude
    END AS longitude
  FROM locations
),
nearby_locations AS (
  SELECT
    p.area_id,
    p.area_name,
    nl.section_id,
    nl.latitude,
    nl.longitude,
    ST_DISTANCE(
      ST_GEOGPOINT(nl.longitude, nl.latitude),
      ST_GEOGPOINT(p.anchor_lng, p.anchor_lat)
    ) AS distance_m
  FROM normalized_locations nl
  CROSS JOIN params p
  WHERE nl.latitude BETWEEN -90 AND 90
    AND nl.longitude BETWEEN -180 AND 180
    AND ST_DWITHIN(
      ST_GEOGPOINT(nl.longitude, nl.latitude),
      ST_GEOGPOINT(p.anchor_lng, p.anchor_lat),
      p.radius_m
    )
),
active_sections AS (
  SELECT
    nl.area_id,
    nl.area_name,
    nl.section_id,
    CAST(ds.organisationId AS STRING) AS section_organisation_id,
    ds.sectionName AS section_name,
    ds.sectionAddress AS section_address,
    nl.latitude,
    nl.longitude,
    nl.distance_m
  FROM nearby_locations nl
  JOIN `staffany-warehouse.analytics.dim_sections` ds
    ON CAST(ds.sectionId AS STRING) = nl.section_id
  WHERE COALESCE(ds.isarchived, FALSE) = FALSE
),
org_sections AS (
  SELECT
    CAST(organisationId AS STRING) AS organisation_id,
    organisationName AS organisation_name,
    CAST(sectionId AS STRING) AS section_id,
    sectionName AS dim_section_name
  FROM `staffany-warehouse.analytics.dim_org_section`
),
joined_sections AS (
  SELECT
    active_sections.*,
    COALESCE(org_sections.organisation_id, active_sections.section_organisation_id) AS organisation_id,
    org_sections.organisation_name,
    COALESCE(active_sections.section_name, org_sections.dim_section_name) AS nearest_section_name
  FROM active_sections
  LEFT JOIN org_sections
    ON org_sections.section_id = active_sections.section_id
),
customer_sections AS (
  SELECT
    js.area_id,
    js.area_name,
    js.organisation_id,
    c360.organisation_name,
    c360.company_id AS hubspot_company_id,
    c360.company_name AS c360_company_name,
    c360.hubspot_link,
    c360.company_usage_status AS usage_status,
    c360.company_usage_next_step AS usage_next_step,
    c360.company_low_usage_reason AS low_usage_reason,
    c360.deal_id,
    c360.deal_name,
    c360.deal_pipeline,
    c360.deal_stage,
    c360.deal_start_date,
    c360.deal_end_date,
    c360.deal_psm,
    CASE
      WHEN c360.deal_end_date IS NULL OR c360.deal_end_date >= CURRENT_DATE()
        THEN 'current_or_open_selected_deal'
      ELSE 'past_selected_deal'
    END AS selected_deal_status,
    mrr.companyMRR AS company_mrr,
    js.section_id AS nearest_section_id,
    js.nearest_section_name,
    js.section_address AS nearest_address,
    js.latitude AS nearest_latitude,
    js.longitude AS nearest_longitude,
    js.distance_m
  FROM joined_sections js
  JOIN `staffany-warehouse.analytics.fct_deal_org_company` c360
    ON CAST(c360.organisation_id AS STRING) = js.organisation_id
  LEFT JOIN `staffany-warehouse.analytics.fct_company_org_mrr` mrr
    ON CAST(mrr.organisation_id AS STRING) = c360.organisation_id
   AND mrr.company_id = c360.company_id
),
ranked AS (
  SELECT
    *,
    COUNT(DISTINCT nearest_section_id) OVER (PARTITION BY organisation_id) AS nearby_section_count,
    ROW_NUMBER() OVER (
      PARTITION BY organisation_id
      ORDER BY
        CASE selected_deal_status
          WHEN 'current_or_open_selected_deal' THEN 0
          ELSE 1
        END,
        distance_m
    ) AS row_rank
  FROM customer_sections
)
SELECT
  area_id,
  area_name,
  organisation_id,
  organisation_name,
  hubspot_company_id,
  c360_company_name,
  hubspot_link,
  usage_status,
  usage_next_step,
  low_usage_reason,
  deal_id,
  deal_name,
  deal_pipeline,
  deal_stage,
  deal_start_date,
  deal_end_date,
  deal_psm,
  selected_deal_status,
  company_mrr,
  nearest_section_id,
  nearest_section_name,
  nearest_address,
  ROUND(distance_m) AS nearest_distance_m,
  nearby_section_count
FROM ranked
WHERE row_rank = 1
ORDER BY
  CASE selected_deal_status
    WHEN 'current_or_open_selected_deal' THEN 0
    ELSE 1
  END,
  nearest_distance_m
LIMIT 50"""


def _is_confirmed(value: Any) -> bool:
    return _normal_text(value) == "confirmed"


def _is_candidate(value: Any) -> bool:
    return _normal_text(value) in {"candidate", "possible", "needs check", "needscheck"}


def _is_customer_status(value: Any) -> bool:
    text = _normal_text(value)
    return any(token in text.split() for token in ("customer", "live", "current", "won")) or "current customer" in text


def _is_past_deal(row: dict[str, Any]) -> bool:
    status = _normal_text(row.get("selected_deal_status") or row.get("deal_status") or "")
    if "past" in status:
        return True
    end_date = str(row.get("deal_end_date") or "").strip()
    if not end_date:
        return False
    try:
        parsed = date.fromisoformat(end_date[:10])
    except ValueError:
        return False
    return parsed < date.today()


def _distance(item: dict[str, Any]) -> int | float:
    value = _float_value(
        item.get("nearest_distance_m")
        if item.get("nearest_distance_m") is not None
        else item.get("distance_m")
    )
    return value if value is not None else 999999


def _result_key(item: dict[str, Any]) -> str:
    place_id = str(item.get("google_place_id") or "").strip()
    company_id = str(item.get("hubspot_company_id") or "").strip()
    organisation_id = str(item.get("organisation_id") or "").strip()
    name = _compact_text(item.get("outlet_name") or item.get("c360_company_name") or item.get("company_name"))
    if place_id:
        return f"place:{place_id}"
    if company_id:
        return f"company:{company_id}"
    if organisation_id:
        return f"org:{organisation_id}"
    return f"name:{name}"


def _account_key(item: dict[str, Any]) -> str:
    company_id = str(item.get("hubspot_company_id") or "").strip()
    organisation_id = str(item.get("organisation_id") or "").strip()
    place_id = str(item.get("google_place_id") or "").strip()
    if company_id:
        return f"company:{company_id}"
    if organisation_id:
        return f"org:{organisation_id}"
    if place_id:
        return f"place:{place_id}"
    return f"name:{_compact_text(item.get('outlet_name') or item.get('c360_company_name') or item.get('company_name'))}"


def _strong_name_address_match(place: dict[str, Any], outlet: dict[str, Any]) -> bool:
    place_name = _compact_text(place.get("outlet_name") or place.get("name"))
    outlet_name = _compact_text(outlet.get("outlet_name") or outlet.get("name"))
    if not place_name or not outlet_name:
        return False
    name_match = place_name == outlet_name or place_name in outlet_name or outlet_name in place_name
    place_address = _normal_text(place.get("formatted_address") or place.get("address"))
    outlet_address = _normal_text(outlet.get("formatted_address") or outlet.get("address") or outlet.get("nearest_address"))
    address_match = bool(place_address and outlet_address and (place_address in outlet_address or outlet_address in place_address))
    return name_match and (address_match or len(place_name) >= 8)


def _merge_outlet_match_item(outlet: dict[str, Any]) -> dict[str, Any]:
    company = outlet.get("company") if isinstance(outlet.get("company"), dict) else {}
    return {
        "source_flags": ["bigquery_outlet_match"],
        "outlet_locations": [
            {
                "outlet_match_id": outlet.get("outlet_match_id") or outlet.get("outlet_location_id") or outlet.get("id") or "",
                "outlet_name": outlet.get("outlet_name") or outlet.get("name") or "",
                "google_place_id": outlet.get("google_place_id") or "",
                "formatted_address": outlet.get("formatted_address") or outlet.get("address") or "",
                "google_maps_uri": outlet.get("google_maps_uri") or "",
                "match_status": outlet.get("match_status") or "candidate",
                "confidence": outlet.get("confidence") or "needs-check",
                "last_checked_at": outlet.get("last_checked_at") or "",
            }
        ],
        "hubspot_company_id": outlet.get("hubspot_company_id") or company.get("hubspot_company_id") or "",
        "customer360_route_key": (
            outlet.get("customer360_route_key")
            or outlet.get("customer_slug")
            or outlet.get("customer_route_key")
            or company.get("customer360_route_key")
            or company.get("customer_slug")
            or ""
        ),
        "company_name": (
            company.get("company_name")
            or outlet.get("hubspot_company_name")
            or outlet.get("company_name")
            or outlet.get("outlet_name")
            or ""
        ),
        "hubspot_owner_id": company.get("hubspot_owner_id") or outlet.get("hubspot_owner_id") or "",
        "organisation_id": outlet.get("organisation_id") or "",
        "account_status": outlet.get("account_status") or company.get("nurtureany_status") or "",
        "match_status": outlet.get("match_status") or "candidate",
        "confidence": outlet.get("confidence") or "needs-check",
        "nearest_distance_m": _distance(outlet),
        "google_place_id": outlet.get("google_place_id") or "",
        "rank_notes": [],
    }


def _merge_c360_item(row: dict[str, Any]) -> dict[str, Any]:
    past = _is_past_deal(row)
    caveats = ["Past selected deal; verify relationship before walk-in."] if past else []
    return {
        "source_flags": ["c360_bigquery"],
        "outlet_locations": [],
        "hubspot_company_id": row.get("hubspot_company_id") or row.get("company_id") or "",
        "customer360_route_key": (
            row.get("customer360_route_key")
            or row.get("customer_slug")
            or row.get("customer_route_key")
            or row.get("company_slug")
            or ""
        ),
        "company_name": row.get("c360_company_name") or row.get("company_name") or "",
        "organisation_id": row.get("organisation_id") or row.get("organisationid") or "",
        "account_status": "customer",
        "match_status": "c360_current_customer",
        "confidence": "verified" if not past else "needs-check",
        "nearest_distance_m": _distance(row),
        "nearest_section": row.get("nearest_section_name") or row.get("nearest_section") or "",
        "nearest_address": row.get("nearest_address") or "",
        "nearby_section_count": row.get("nearby_section_count") or 1,
        "usage_status": row.get("usage_status") or row.get("company_usage_status") or "",
        "deal_stage": row.get("deal_stage") or "",
        "deal_end_date": row.get("deal_end_date") or "",
        "selected_deal_status": row.get("selected_deal_status") or "",
        "company_mrr": row.get("company_mrr") or row.get("companyMRR") or "",
        "rank_notes": caveats,
    }


def _merge_google_item(place: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_flags": ["google_places_live"],
        "outlet_locations": [
            {
                "outlet_name": place.get("outlet_name") or place.get("name") or "",
                "google_place_id": place.get("google_place_id") or "",
                "google_maps_uri": place.get("google_maps_uri") or "",
                "formatted_address": place.get("formatted_address") or "",
                "match_status": "candidate",
                "confidence": "needs-check",
            }
        ],
        "company_name": place.get("outlet_name") or place.get("name") or "",
        "google_place_id": place.get("google_place_id") or "",
        "account_status": "unknown",
        "match_status": "candidate",
        "confidence": "needs-check",
        "nearest_distance_m": _distance(place),
        "rank_notes": ["Google Places live candidate, review needed; not a confirmed account."],
        "store_policy": "live_candidate_only_until_review_approval",
    }


def _absorb(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for flag in incoming.get("source_flags", []):
        if flag not in target["source_flags"]:
            target["source_flags"].append(flag)
    for outlet in incoming.get("outlet_locations", []):
        outlet_key = (
            outlet.get("google_place_id")
            or outlet.get("outlet_match_id")
            or outlet.get("outlet_location_id")
            or _compact_text(outlet.get("outlet_name"))
        )
        existing_keys = {
            item.get("google_place_id")
            or item.get("outlet_match_id")
            or item.get("outlet_location_id")
            or _compact_text(item.get("outlet_name"))
            for item in target["outlet_locations"]
        }
        if outlet_key not in existing_keys:
            target["outlet_locations"].append(outlet)
    for key, value in incoming.items():
        if key in {"source_flags", "outlet_locations", "rank_notes"}:
            continue
        if value not in (None, "") and target.get(key) in (None, ""):
            target[key] = value
    if _distance(incoming) < _distance(target):
        target["nearest_distance_m"] = _distance(incoming)
    for note in incoming.get("rank_notes", []):
        if note and note not in target["rank_notes"]:
            target["rank_notes"].append(note)
    if incoming.get("confidence") == "verified":
        target["confidence"] = "verified"
    if incoming.get("account_status") == "customer":
        target["account_status"] = "customer"


def _classification(item: dict[str, Any]) -> tuple[int, str]:
    confirmed = _is_confirmed(item.get("match_status"))
    candidate = _is_candidate(item.get("match_status"))
    customer = item.get("account_status") == "customer" or _is_customer_status(item.get("account_status"))
    has_c360 = "c360_bigquery" in item.get("source_flags", [])
    has_google_only = item.get("source_flags") == ["google_places_live"]
    if confirmed and customer:
        return 0, "confirmed_outlet_current_customer"
    if has_c360:
        return 1, "c360_current_customer_without_stored_outlet" if not item.get("outlet_locations") else "c360_current_customer"
    if confirmed:
        return 2, "confirmed_outlet_prospect"
    if candidate and "bigquery_outlet_match" in item.get("source_flags", []):
        return 3, "candidate_outlet_match"
    if has_google_only:
        return 4, "google_places_live_candidate"
    return 5, "needs_review"


def _rank_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in results:
        category_rank, category = _classification(item)
        item["rank_category"] = category
        item["_rank"] = (
            category_rank,
            1 if _is_past_deal(item) else 0,
            _distance(item),
            _normal_text(item.get("company_name")),
        )
    ranked = sorted(results, key=lambda item: item["_rank"])
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
        item.pop("_rank", None)
    return ranked


def _apply_c360_links(ranked: list[dict[str, Any]]) -> list[str]:
    caveats = []
    for item in ranked:
        if item.get("rank_category") not in C360_CUSTOMER_RANK_CATEGORIES:
            continue
        route_key = _customer360_route_key(
            item.get("hubspot_company_id"),
            item.get("company_name"),
            item.get("customer360_route_key"),
        )
        c360_url = _render_c360_url(
            item.get("hubspot_company_id"),
            item.get("organisation_id"),
            customer360_route_key=route_key,
            company_name=item.get("company_name"),
        )
        if c360_url:
            item["c360_url"] = c360_url
            item["customer360_route_key"] = route_key
            continue
        item["confidence"] = "needs-check"
        note = "C360 link missing because Customer 360 route key was unavailable."
        if note not in item.get("rank_notes", []):
            item.setdefault("rank_notes", []).append(note)
        if note not in caveats:
            caveats.append(note)
    return caveats


@mcp.tool()
def resolve_known_area_for_near_me(
    slack_user_email: str,
    location_text: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    max_snap_distance_m: int = DEFAULT_SNAP_DISTANCE_M,
) -> dict[str, Any]:
    """Resolve a Google Maps link, lat/lng, or area name to the nearest known area."""

    scope = _scope(slack_user_email, {"location_text_present": bool(location_text)})
    try:
        areas = _load_known_areas()
        lat, lng, location_source, alias_area = _resolve_coordinates(location_text, latitude, longitude, areas)
        if alias_area:
            area = _area_public(alias_area, 0, "matched_by_alias")
        else:
            area = _snap_known_area(lat, lng, areas, _bounded_int(max_snap_distance_m, DEFAULT_SNAP_DISTANCE_M, 5000, 100))
    except NearMeError as error:
        return _blocked(str(error), scope)

    confidence = "verified" if area["snap_status"] in {"matched", "matched_by_alias"} else "needs-check"
    caveat = ""
    if confidence == "needs-check":
        caveat = "Nearest known area is outside the default snap threshold; ask user to confirm before continuing."
    return {
        "answer": area,
        "source": "Known areas curated config",
        "scope": {**scope, "location_source": location_source, "input_latitude": lat, "input_longitude": lng},
        "confidence": confidence,
        "caveat": caveat,
    }


@mcp.tool()
def build_near_me_c360_customer_query(
    slack_user_email: str,
    area_id: str = "",
    location_text: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    """Build the bounded BigQuery SQL for nearby C360 live/customer orgs."""

    scope = _scope(slack_user_email)
    try:
        areas = _load_known_areas()
        if area_id:
            area = _area_public(_known_area_by_id(area_id, areas))
            location_source = "area_id"
        else:
            lat, lng, location_source, alias_area = _resolve_coordinates(location_text, latitude, longitude, areas)
            area = _area_public(alias_area, 0, "matched_by_alias") if alias_area else _snap_known_area(lat, lng, areas, DEFAULT_SNAP_DISTANCE_M)
    except NearMeError as error:
        return _blocked(str(error), scope, "C360 BigQuery")

    sql = _near_me_c360_sql(area)
    return {
        "answer": {
            "known_area": area,
            "execute_with": "staffany_bigquery.execute_sql_readonly",
            "sql": sql,
            "expected_output": "One row per organisation_id with nearest section, distance, HubSpot company, C360 usage/deal context, and optional MRR.",
        },
        "source": "C360 BigQuery SQL builder",
        "scope": {**scope, "location_source": location_source},
        "confidence": "verified",
        "caveat": "Run via read-only BigQuery MCP only. fct_company_org_mrr is optional MRR enrichment and not the customer filter.",
    }


@mcp.tool()
def refresh_google_places_for_known_area(
    slack_user_email: str,
    area_id: str,
    max_results: int = MAX_GOOGLE_PLACES_RESULTS,
) -> dict[str, Any]:
    """Run Google Places Nearby Search for restaurants around a known area."""

    scope = _scope(slack_user_email, {"area_id": area_id, "field_mask": GOOGLE_PLACES_FIELD_MASK})
    try:
        area = _area_public(_known_area_by_id(area_id))
        capped_results = _bounded_int(max_results, MAX_GOOGLE_PLACES_RESULTS, MAX_GOOGLE_PLACES_RESULTS)
        payload = {
            "includedTypes": ["restaurant"],
            "maxResultCount": capped_results,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": area["latitude"],
                        "longitude": area["longitude"],
                    },
                    "radius": float(area["radius_m"]),
                }
            },
        }
        _google_places_key()
        response = _request_google_places(payload)
    except NearMeError as error:
        return _blocked(str(error), scope, "Google Places")

    places = response.get("places") or []
    candidates = [
        _google_place_candidate(place, area, rank)
        for rank, place in enumerate(places[:capped_results], start=1)
        if isinstance(place, dict)
    ]
    return {
        "answer": {
            "known_area": area,
            "places": candidates,
            "request": {
                "endpoint": "POST /v1/places:searchNearby",
                "includedTypes": ["restaurant"],
                "field_mask": GOOGLE_PLACES_FIELD_MASK,
            },
            "store_policy": "Do not store every restaurant. Keep Google-only results as live candidates until review approval.",
        },
        "source": "Google Places Nearby Search",
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Google-only restaurants are live candidates, not confirmed accounts.",
    }


@mcp.tool()
def build_near_me_outlet_matches_query(
    slack_user_email: str,
    area_id: str,
    limit: int = MAX_OUTLET_MATCH_RESULTS,
) -> dict[str, Any]:
    """Build the bounded BigQuery SQL for curated outlet matches in a known area."""

    requested_limit = _bounded_int(limit, MAX_OUTLET_MATCH_RESULTS, MAX_OUTLET_MATCH_RESULTS)
    scope = _scope(slack_user_email, {"area_id": area_id, "columns": OUTLET_MATCH_COLUMNS})
    try:
        table = _outlet_matches_table()
        scope["outlet_matches_table"] = table
        area = _area_public(_known_area_by_id(area_id))
        sql = _near_me_outlet_matches_sql(area, requested_limit)
    except NearMeError as error:
        return _blocked(str(error), scope, "BigQuery outlet_matches")

    return {
        "answer": {
            "known_area": area,
            "execute_with": "staffany_bigquery.execute_sql_readonly",
            "sql": sql,
            "expected_output": "Curated outlet match rows for the known area, excluding rejected matches.",
        },
        "source": "BigQuery outlet_matches SQL builder",
        "scope": scope,
        "confidence": "verified",
        "caveat": "Run via read-only BigQuery MCP only. This reads the outlet memory table and does not mutate HubSpot.",
    }


@mcp.tool()
def merge_near_me_sources(
    slack_user_email: str,
    known_area: dict[str, Any],
    outlet_matches: list[dict[str, Any]] | None = None,
    outlet_locations: list[dict[str, Any]] | None = None,
    c360_customer_rows: list[dict[str, Any]] | None = None,
    google_places: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Merge BigQuery outlet matches, C360 customers, and Google Places candidates."""

    area = known_area or {}
    selected_outlet_matches = outlet_matches if outlet_matches is not None else outlet_locations
    scope = _scope(
        slack_user_email,
        {
            "area_id": area.get("area_id") or "",
            "area_name": area.get("area_name") or "",
            "outlet_match_count": len(selected_outlet_matches or []),
            "c360_customer_row_count": len(c360_customer_rows or []),
            "google_place_count": len(google_places or []),
        },
    )
    groups: dict[str, dict[str, Any]] = {}

    for outlet in selected_outlet_matches or []:
        if not isinstance(outlet, dict):
            continue
        item = _merge_outlet_match_item(outlet)
        key = _account_key(item)
        if key in groups:
            _absorb(groups[key], item)
        else:
            groups[key] = item

    for row in c360_customer_rows or []:
        if not isinstance(row, dict):
            continue
        item = _merge_c360_item(row)
        key = _account_key(item)
        if key in groups:
            _absorb(groups[key], item)
        else:
            groups[key] = item

    for place in google_places or []:
        if not isinstance(place, dict):
            continue
        matched_key = ""
        place_id = str(place.get("google_place_id") or "").strip()
        if place_id:
            for key, group in groups.items():
                outlet_place_ids = {
                    str(outlet.get("google_place_id") or "").strip()
                    for outlet in group.get("outlet_locations", [])
                }
                if place_id in outlet_place_ids or place_id == str(group.get("google_place_id") or "").strip():
                    matched_key = key
                    break
        if not matched_key:
            for key, group in groups.items():
                outlets = group.get("outlet_locations") or [group]
                if any(_strong_name_address_match(place, outlet) for outlet in outlets):
                    matched_key = key
                    break
        item = _merge_google_item(place)
        if matched_key:
            _absorb(groups[matched_key], item)
        else:
            groups[_result_key(item)] = item

    ranked = _rank_results(list(groups.values()))
    c360_link_caveats = _apply_c360_links(ranked)
    customers = [item for item in ranked if item["rank_category"] in {"confirmed_outlet_current_customer", "c360_current_customer", "c360_current_customer_without_stored_outlet"}]
    prospects = [item for item in ranked if item["rank_category"] in {"confirmed_outlet_prospect", "candidate_outlet_match"}]
    candidates = [item for item in ranked if item["rank_category"] == "google_places_live_candidate"]
    caveats = [*c360_link_caveats]
    if candidates:
        caveats.append("Google-only restaurants are candidates, not confirmed accounts.")
    if any("Past selected deal" in " ".join(item.get("rank_notes", [])) for item in ranked):
        caveats.append("Past selected deal rows remain visible with a caveat.")
    has_missing_c360_links = bool(c360_link_caveats)

    return {
        "answer": {
            "known_area": area,
            "customers_nearby": customers,
            "prospects_nearby": prospects,
            "live_candidates": candidates,
            "all_results": ranked,
        },
        "source": "BigQuery outlet_matches + C360 BigQuery + Google Places",
        "scope": scope,
        "confidence": "needs-check" if candidates or not c360_customer_rows or has_missing_c360_links else "verified",
        "caveat": " ".join(caveats) if caveats else "No HubSpot write-back or Google candidate storage happened.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
