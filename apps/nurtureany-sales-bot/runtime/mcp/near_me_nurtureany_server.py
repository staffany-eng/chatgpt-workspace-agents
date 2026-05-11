#!/usr/bin/env python3
"""Known-area near-me MCP adapter for NurtureAny Sales Bot.

This server keeps the "who can I say hi to nearby?" flow review-first and
read-only. It resolves a user location to a curated known area, refreshes live
restaurant candidates from Google Places, builds BigQuery SQL for curated
outlet matches and C360 customers, and merges those source outputs without
mutating HubSpot.

Canonical C360 joins include `staffany-warehouse.analytics.fct_deal_org_company`
and LEFT JOIN `staffany-warehouse.analytics.fct_company_org_mrr`.
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
    "places.location,places.googleMapsUri,places.businessStatus"
)
MAX_GOOGLE_PLACES_RESULTS = 8
MAX_C360_CUSTOMER_QUERY_RESULTS = 12
DEFAULT_NEAR_ME_RADIUS_M = 1000
DEFAULT_SNAP_DISTANCE_M = 1500
MAX_OUTLET_MATCH_RESULTS = 30
MAX_SEED_REVIEW_CANDIDATES_PER_AREA = 10
MAX_MERGED_CUSTOMERS_FOR_ANSWER = 6
MAX_MERGED_PROSPECTS_FOR_ANSWER = 3
MAX_MERGED_LIVE_CANDIDATES_FOR_ANSWER = 2
MAX_MERGED_OUTLETS_PER_ACCOUNT = 2
OUTLET_MATCHES_TABLE_ENV = "NURTUREANY_OUTLET_MATCHES_TABLE"
DEFAULT_OUTLET_MATCHES_TABLE = "staffany-warehouse.analytics.nurtureany_near_me_outlet_matches"
KNOWN_AREAS_FILE_ENV = "NURTUREANY_KNOWN_AREAS_FILE"
C360_DATASET_ENV = "NURTUREANY_C360_DATASET"
DEFAULT_C360_DATASET = "analytics"
SCOPE_SOURCE = "near_me_nurtureany"
C360_CUSTOMER_RANK_CATEGORIES = {
    "confirmed_outlet_current_customer",
    "c360_current_customer",
    "c360_current_customer_without_stored_outlet",
}
CLOSED_GOOGLE_BUSINESS_STATUS = {
    "closedpermanently",
    "closedtemporarily",
    "permanentlyclosed",
    "temporarilyclosed",
}
ADDRESS_TOKEN_REPLACEMENTS = {
    "pl": "place",
    "rd": "road",
    "st": "street",
    "ave": "avenue",
    "dr": "drive",
    "ctr": "centre",
}
ROAD_TYPE_TOKENS = {
    "avenue",
    "boulevard",
    "central",
    "close",
    "crescent",
    "drive",
    "link",
    "lane",
    "place",
    "quay",
    "road",
    "street",
    "terrace",
    "view",
    "walk",
    "way",
}
NAME_TOKEN_STOPWORDS = {
    "and",
    "at",
    "by",
    "the",
    "a",
    "an",
    "singapore",
    "sg",
    "place",
    "plaza",
    "mall",
    "centre",
    "center",
    "central",
    "road",
    "street",
    "st",
    "quay",
    "boat",
    "raffles",
    "bugis",
    "junction",
    "suntec",
    "orchard",
    "ion",
    "vivocity",
    "vivo",
    "marina",
    "bay",
    "mbfc",
    "westgate",
    "jem",
    "tampines",
    "jurong",
    "causeway",
    "woodlands",
    "northpoint",
    "yishun",
    "chinatown",
    "telok",
    "ayer",
    "tanjong",
    "pagar",
    "shenton",
    "clarke",
    "changi",
    "jewel",
    "airport",
    "paya",
    "lebar",
    "quarter",
    "guoco",
    "customs",
    "house",
    "building",
    "tower",
    "level",
    "bldg",
    "restaurant",
    "restaurants",
    "cafe",
    "coffee",
    "bar",
    "kitchen",
    "grill",
    "food",
    "foods",
    "pte",
    "ltd",
    "llp",
    "limited",
    "private",
    "trading",
    "holdings",
    "international",
}
SECTION_ROLE_WORDS = {
    "boh",
    "foh",
    "bar",
    "kitchen",
    "service",
    "ops",
    "operations",
    "staffie",
}
SECTION_NOISE_NAMES = {
    "boh",
    "foh",
    "bar",
    "kitchen",
    "service",
    "hq",
    "office",
    "central kitchen",
    "roadshow",
    "staffie",
    "staffie foh",
    "events",
}
LOCATION_LABEL_RULES = [
    ("one raffles place", "One Raffles Place"),
    ("one raffles", "One Raffles Place"),
    ("republic plaza", "RP"),
    ("the arcade", "The Arcade"),
    ("lau pa sat", "Lau Pa Sat"),
    ("telok ayer festival market", "Lau Pa Sat"),
    ("customs house", "Customs House"),
    ("boat quay", "Boat Quay"),
    ("battery road", "Battery Road"),
    ("collyer quay", "Collyer Quay"),
    ("raffles place", "Raffles Place"),
    ("marina bay financial centre", "MBFC"),
    ("mbfc", "MBFC"),
    ("vivocity", "VivoCity"),
    ("vivo city", "VivoCity"),
    ("suntec city", "Suntec City"),
    ("guoco tower", "Guoco Tower"),
    ("tanjong pagar", "Tanjong Pagar"),
    ("plq", "PLQ"),
    ("paya lebar quarter", "PLQ"),
]
KNOWN_ACCOUNT_OUTLET_ALIASES = {
    "insurgence hq": {"chimis", "chimi s especial", "chimis especial"},
    "rumi rangkayo": {"nasi lemak ayam taliwang"},
    "stripes australia": {"dimbulah"},
    "jm coffee": {"compose coffee"},
    "byd by 1826": {"byd boat quay 1826", "1826"},
    "lixin fishball": {"lixin", "lixin teochew fishball"},
    "1 group": {"sol luna", "sol and luna", "monti", "1 pavilion"},
    "godiva": {"godiva"},
    "surrey hills grocer": {"surrey hills", "bao bao"},
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
    "customer360_route_key",
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
        "address_scope_terms": [
            "raffles",
            "collyer",
            "battery road",
            "boat quay",
            "lau pa sat",
            "telok ayer festival market",
            "customs house",
            "republic plaza",
            "one raffles",
            "the arcade",
            "market street",
            "malacca street",
            "phillip street",
            "cecil street",
            "robinson road",
            "clifford",
            "finlayson",
            "ocean financial centre",
            "capitaspring",
        ],
    },
    {
        "area_id": "sg_chinatown",
        "area_name": "Chinatown / Telok Ayer",
        "country": "Singapore",
        "latitude": 1.2847,
        "longitude": 103.8438,
        "radius_m": 800,
        "aliases": ["chinatown", "telok ayer", "amoy street", "club street"],
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
        "area_id": "sg_suntec_city",
        "area_name": "Suntec City",
        "country": "Singapore",
        "latitude": 1.2931,
        "longitude": 103.8573,
        "radius_m": 800,
        "aliases": ["suntec", "suntec city", "marina centre", "city hall"],
    },
    {
        "area_id": "sg_tanjong_pagar",
        "area_name": "Tanjong Pagar / Shenton",
        "country": "Singapore",
        "latitude": 1.2767,
        "longitude": 103.8459,
        "radius_m": 900,
        "aliases": ["tanjong pagar", "shenton", "shenton way", "anson", "maxwell"],
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
        "area_id": "sg_boat_quay_clarke_quay",
        "area_name": "Boat Quay / Clarke Quay",
        "country": "Singapore",
        "latitude": 1.2906,
        "longitude": 103.8466,
        "radius_m": 800,
        "aliases": ["boat quay", "clarke quay", "singapore river", "robertson quay"],
    },
    {
        "area_id": "sg_marina_bay",
        "area_name": "Marina Bay / MBFC",
        "country": "Singapore",
        "latitude": 1.2799,
        "longitude": 103.8547,
        "radius_m": 800,
        "aliases": ["marina bay", "mbfc", "marina bay financial centre", "downtown"],
    },
    {
        "area_id": "sg_westgate_jem",
        "area_name": "Westgate / JEM",
        "country": "Singapore",
        "latitude": 1.3331,
        "longitude": 103.7435,
        "radius_m": 800,
        "aliases": ["westgate", "jem", "jurong east", "jurong lake district"],
    },
    {
        "area_id": "sg_tampines_mall",
        "area_name": "Tampines Mall",
        "country": "Singapore",
        "latitude": 1.3525,
        "longitude": 103.9447,
        "radius_m": 750,
        "aliases": ["tampines mall", "tampines", "tampines central"],
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
        "area_id": "sg_paya_lebar_quarter",
        "area_name": "Paya Lebar Quarter",
        "country": "Singapore",
        "latitude": 1.3176,
        "longitude": 103.8923,
        "radius_m": 800,
        "aliases": ["paya lebar", "paya lebar quarter", "plq", "paya lebar central"],
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
        "area_id": "sg_northpoint_yishun",
        "area_name": "Northpoint City / Yishun",
        "country": "Singapore",
        "latitude": 1.4297,
        "longitude": 103.8358,
        "radius_m": 800,
        "aliases": ["northpoint", "northpoint city", "yishun"],
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
        "area_id": "sg_nex",
        "area_name": "NEX",
        "country": "Singapore",
        "latitude": 1.3508,
        "longitude": 103.8723,
        "radius_m": 750,
        "aliases": ["nex", "serangoon", "nex serangoon"],
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


def _env_value(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if not value or value in {f"${{{name}}}", f"${name}"}:
        return default
    return value


def _known_area_source_path() -> str:
    raw = _env_value(KNOWN_AREAS_FILE_ENV)
    if raw:
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
    if area.get("address_scope_terms"):
        payload["address_scope_terms"] = [
            str(term).strip().lower()
            for term in area.get("address_scope_terms", [])
            if str(term or "").strip()
        ]
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


def _normal_address(value: Any) -> str:
    tokens = [
        ADDRESS_TOKEN_REPLACEMENTS.get(token, token)
        for token in _normal_text(value).split()
    ]
    return " ".join(tokens)


def _address_without_units(value: Any) -> str:
    raw = str(value or "").lower()
    raw = re.sub(r"#\s*[a-z]?\d+[a-z]?\s*[-/]\s*[\w/-]+", " ", raw)
    raw = re.sub(r"\b[bl]\d{1,2}\s*[-/]\s*\w+\b", " ", raw)
    return _normal_address(raw)


def _postal_codes(value: Any) -> set[str]:
    return set(re.findall(r"\b\d{6}\b", str(value or "")))


def _numbered_street_anchor(value: Any) -> str:
    text = re.sub(r"\b\d{6}\b", " ", _address_without_units(value))
    tokens = text.split()
    for index, token in enumerate(tokens):
        if not re.fullmatch(r"\d{1,4}[a-z]?", token):
            continue
        following: list[str] = []
        for word in tokens[index + 1 :]:
            if word in {"singapore"} or re.fullmatch(r"\d+", word):
                break
            following.append(word)
            if word in ROAD_TYPE_TOKENS or len(following) >= 4:
                break
        if following:
            return " ".join([token, *following])
    return ""


def _address_has_same_building_or_street(left: Any, right: Any) -> bool:
    left_normalized = _normal_address(left)
    right_normalized = _normal_address(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized or left_normalized in right_normalized or right_normalized in left_normalized:
        return True

    left_postals = _postal_codes(left)
    right_postals = _postal_codes(right)
    if left_postals and right_postals:
        return bool(left_postals & right_postals)

    left_anchor = _numbered_street_anchor(left)
    right_anchor = _numbered_street_anchor(right)
    if left_anchor and right_anchor:
        return left_anchor == right_anchor

    return False


def _meaningful_name_tokens(value: Any) -> set[str]:
    tokens = set()
    for token in _normal_text(value).split():
        if token in NAME_TOKEN_STOPWORDS:
            continue
        if len(token) < 3 and not token.isdigit():
            continue
        tokens.add(token)
    return tokens


def _names_are_compatible(left: Any, right: Any) -> bool:
    left_compact = _compact_text(left)
    right_compact = _compact_text(right)
    if not left_compact or not right_compact:
        return False
    if left_compact == right_compact:
        return True
    if len(left_compact) >= 6 and left_compact in right_compact:
        return True
    if len(right_compact) >= 6 and right_compact in left_compact:
        return True

    common = _meaningful_name_tokens(left) & _meaningful_name_tokens(right)
    if len(common) >= 2:
        return True
    return any(token.isdigit() and len(token) >= 4 for token in common) or any(
        len(token) >= 5 and not token.isdigit()
        for token in common
    )


def _has_known_account_outlet_alias(account_name: Any, outlet_name: Any) -> bool:
    account_normalized = _normal_text(account_name)
    outlet_normalized = _normal_text(outlet_name)
    if not account_normalized or not outlet_normalized:
        return False
    for account_alias, outlet_aliases in KNOWN_ACCOUNT_OUTLET_ALIASES.items():
        if account_alias not in account_normalized and account_normalized not in account_alias:
            continue
        if any(alias in outlet_normalized for alias in outlet_aliases):
            return True
    return False


def _needs_account_outlet_brand_review(item: dict[str, Any], outlet: dict[str, Any]) -> bool:
    source = outlet.get("ground_outlet_name_source") or item.get("ground_outlet_name_source") or ""
    if not str(source).startswith("section_name"):
        return False
    if "c360_bigquery" not in (item.get("source_flags") or []):
        return False
    outlet_name = outlet.get("outlet_name") or ""
    account_name = item.get("company_name") or ""
    if not outlet_name or not account_name:
        return False
    return not (
        _names_are_compatible(outlet_name, account_name)
        or _has_known_account_outlet_alias(account_name, outlet_name)
    )


def _clean_section_outlet_name(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    changed = True
    while changed:
        original = text
        text = re.sub(r"^(?:BOH|FOH|BAR|KITCHEN|SERVICE|OPS|OPERATIONS|STAFFIE)\s*[-:]\s*", "", text, flags=re.I)
        text = re.sub(r"^(?:BOH|FOH|BAR|KITCHEN|SERVICE|OPS|OPERATIONS|STAFFIE)\s+", "", text, flags=re.I)
        text = re.sub(r"\s*[-:]\s*(?:BOH|FOH|BAR|KITCHEN|SERVICE|OPS|OPERATIONS|STAFFIE)\s*$", "", text, flags=re.I)
        text = re.sub(r"\s+", " ", text).strip(" -:")
        changed = text != original
    return text


def _section_name_is_noise(value: Any) -> bool:
    normalized = _normal_text(value)
    if not normalized:
        return True
    if normalized in SECTION_NOISE_NAMES:
        return True
    tokens = set(normalized.split())
    if tokens and tokens <= SECTION_ROLE_WORDS:
        return True
    return False


def _location_label_from_text(*values: Any) -> str:
    haystack = _normal_address(" ".join(str(value or "") for value in values))
    if not haystack:
        return ""
    for term, label in LOCATION_LABEL_RULES:
        if _normal_address(term) in haystack:
            return label
    anchor = _numbered_street_anchor(haystack)
    if anchor:
        words = anchor.split()
        if len(words) > 1:
            return " ".join(word.title() for word in words[1:])
    return ""


def _looks_like_legal_entity(value: Any) -> bool:
    tokens = _normal_text(value).split()
    return any(token in {"pte", "ltd", "llp", "limited", "private"} for token in tokens)


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
    token = _env_value("GOOGLE_PLACES_API_KEY") or _env_value("GOOGLE_MAPS_API_KEY")
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
    token = _env_value("GOOGLE_PLACES_API_KEY") or _env_value("GOOGLE_MAPS_API_KEY")
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


def _google_business_status(place: dict[str, Any]) -> str:
    return str(
        place.get("business_status")
        or place.get("businessStatus")
        or place.get("google_business_status")
        or ""
    ).strip()


def _place_is_closed(place: dict[str, Any]) -> bool:
    normalized_status = _normal_text(_google_business_status(place)).replace(" ", "")
    return normalized_status in CLOSED_GOOGLE_BUSINESS_STATUS


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
        "google_business_status": _google_business_status(place),
        "distance_m": round(distance_m) if distance_m is not None else None,
        "match_status": "candidate",
        "account_status": "unknown",
        "source": "google_places_live",
        "confidence": "needs-check",
        "store_policy": "live_candidate_only_until_review_approval",
    }


def _outlet_matches_table() -> str:
    table = _env_value(OUTLET_MATCHES_TABLE_ENV, DEFAULT_OUTLET_MATCHES_TABLE)
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+", table):
        raise NearMeError(f"Invalid {OUTLET_MATCHES_TABLE_ENV}; expected project.dataset.table.")
    return table


def _c360_dataset() -> str:
    dataset = _env_value(C360_DATASET_ENV, DEFAULT_C360_DATASET)
    if not re.fullmatch(r"[A-Za-z0-9_]+", dataset):
        raise NearMeError(f"Invalid {C360_DATASET_ENV}; expected BigQuery dataset id.")
    return dataset


def _analytics_table(table_name: str, dataset: str | None = None) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", table_name):
        raise NearMeError("Invalid analytics table name.")
    return f"`staffany-warehouse.{dataset or _c360_dataset()}.{table_name}`"


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


def _area_address_scope_terms(area: dict[str, Any]) -> list[str]:
    seen = set()
    terms = []
    for raw in area.get("address_scope_terms") or []:
        term = _normal_address(raw)
        if term and term not in seen:
            seen.add(term)
            terms.append(term)
    return terms


def _sql_string_array(values: list[str]) -> str:
    cleaned = []
    seen = set()
    for value in values:
        text = _normal_address(value)
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
    if not cleaned:
        return "ARRAY<STRING>[]"
    return "[" + ", ".join(_sql_literal(value) for value in cleaned) + "]"


def _row_matches_area_address_scope(area: dict[str, Any], row: dict[str, Any]) -> bool:
    terms = _area_address_scope_terms(area)
    if not terms:
        return True
    haystack = _normal_address(
        " ".join(
            str(row.get(key) or "")
            for key in (
                "nearest_address",
                "section_address",
                "formatted_address",
                "address",
                "nearest_section_name",
                "nearest_section",
                "section_name",
            )
        )
    )
    if not haystack:
        return True
    return any(term in haystack for term in terms)


def _near_me_outlet_matches_sql(area: dict[str, Any], limit: int = MAX_OUTLET_MATCH_RESULTS) -> str:
    lat = float(area["latitude"])
    lng = float(area["longitude"])
    radius_m = _bounded_int(area.get("radius_m"), DEFAULT_NEAR_ME_RADIUS_M, 3000, 100)
    area_id = _sql_literal(area["area_id"])
    area_name = _sql_literal(area["area_name"])
    table = _outlet_matches_table()
    c360_dataset = _c360_dataset()
    customer_knowledge_latest_table = _analytics_table("customer_knowledge_latest", c360_dataset)
    customer_wiki_backfill_accounts_table = _analytics_table("customer_wiki_backfill_accounts", c360_dataset)
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
customer_latest_route_candidates AS (
  SELECT
    hubspot_company_id,
    customer_slug
  FROM {customer_knowledge_latest_table}
  WHERE customer_slug IS NOT NULL
  GROUP BY hubspot_company_id, customer_slug
),
customer_latest_routes AS (
  SELECT
    hubspot_company_id,
    customer_slug
  FROM customer_latest_route_candidates
  QUALIFY COUNT(*) OVER (PARTITION BY hubspot_company_id) = 1
),
customer_backfill_route_candidates AS (
  SELECT
    hubspot_company_id,
    customer_slug,
    REGEXP_REPLACE(
      REGEXP_REPLACE(LOWER(COALESCE(company_name, '')), r'\\b(pte|ltd|private limited|limited)\\b', ''),
      r'[^a-z0-9]+',
      ''
    ) AS company_name_key
  FROM {customer_wiki_backfill_accounts_table}
  WHERE customer_slug IS NOT NULL
  GROUP BY hubspot_company_id, customer_slug, company_name_key
),
customer_backfill_routes AS (
  SELECT
    hubspot_company_id,
    customer_slug
  FROM (
    SELECT DISTINCT
      hubspot_company_id,
      customer_slug
    FROM customer_backfill_route_candidates
  )
  QUALIFY COUNT(*) OVER (PARTITION BY hubspot_company_id) = 1
),
customer_route_by_name AS (
  SELECT
    company_name_key,
    customer_slug
  FROM (
    SELECT DISTINCT
      company_name_key,
      customer_slug
    FROM customer_backfill_route_candidates
    WHERE company_name_key != ''
  )
  QUALIFY COUNT(*) OVER (PARTITION BY company_name_key) = 1
),
scored AS (
  SELECT
    matches.*,
    COALESCE(customer_latest.customer_slug, customer_backfill.customer_slug, customer_route_by_name.customer_slug) AS customer360_route_key,
    CASE
      WHEN matches.latitude IS NULL OR matches.longitude IS NULL THEN NULL
      ELSE ST_DISTANCE(
        ST_GEOGPOINT(matches.longitude, matches.latitude),
        ST_GEOGPOINT(params.anchor_lng, params.anchor_lat)
      )
    END AS distance_m
  FROM matches
  CROSS JOIN params
  LEFT JOIN customer_latest_routes customer_latest
    ON customer_latest.hubspot_company_id = matches.hubspot_company_id
  LEFT JOIN customer_backfill_routes customer_backfill
    ON customer_backfill.hubspot_company_id = matches.hubspot_company_id
  LEFT JOIN customer_route_by_name
    ON customer_route_by_name.company_name_key = REGEXP_REPLACE(
      REGEXP_REPLACE(LOWER(COALESCE(matches.hubspot_company_name, '')), r'\\b(pte|ltd|private limited|limited)\\b', ''),
      r'[^a-z0-9]+',
      ''
    )
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
  customer360_route_key,
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


def _near_me_c360_sql(area: dict[str, Any], *, include_nearby_sections: bool = False) -> str:
    lat = float(area["latitude"])
    lng = float(area["longitude"])
    radius_m = _bounded_int(area.get("radius_m"), DEFAULT_NEAR_ME_RADIUS_M, 3000, 100)
    area_id = _sql_literal(area["area_id"])
    area_name = _sql_literal(area["area_name"])
    address_scope_terms = _sql_string_array(_area_address_scope_terms(area))
    c360_dataset = _c360_dataset()
    dim_sections_table = _analytics_table("dim_sections", c360_dataset)
    dim_org_section_table = _analytics_table("dim_org_section", c360_dataset)
    fct_deal_org_company_table = _analytics_table("fct_deal_org_company", c360_dataset)
    fct_company_org_mrr_table = _analytics_table("fct_company_org_mrr", c360_dataset)
    customer_knowledge_latest_table = _analytics_table("customer_knowledge_latest", c360_dataset)
    customer_wiki_backfill_accounts_table = _analytics_table("customer_wiki_backfill_accounts", c360_dataset)
    section_rollup_ctes = ""
    section_rollup_join = ""
    nearby_sections_select = ""
    if include_nearby_sections:
        section_rollup_ctes = """,
section_rollup_base AS (
  SELECT DISTINCT
    organisation_id,
    nearest_section_id AS section_id,
    nearest_section_name AS section_name,
    nearest_address AS section_address,
    nearest_latitude AS latitude,
    nearest_longitude AS longitude,
    ROUND(distance_m) AS distance_m
  FROM customer_sections
),
section_rollup AS (
  SELECT
    organisation_id,
    ARRAY_AGG(
      STRUCT(
        section_id,
        section_name,
        section_address,
        latitude,
        longitude,
        distance_m
      )
      ORDER BY distance_m, section_name
      LIMIT 20
    ) AS nearby_sections
  FROM section_rollup_base
  GROUP BY organisation_id
)"""
        section_rollup_join = """LEFT JOIN section_rollup
  ON section_rollup.organisation_id = ranked.organisation_id"""
        nearby_sections_select = ",\n  section_rollup.nearby_sections"
    return f"""-- NurtureAny known-area near-me C360 customer query.
-- Run only through staffany_bigquery.execute_sql_readonly.
-- Uses geofence rows from kraken_rds.Locations, not person GPS.
-- C360 dataset: staffany-warehouse.{c360_dataset}.
WITH params AS (
  SELECT
    {area_id} AS area_id,
    {area_name} AS area_name,
    {lat:.7f} AS anchor_lat,
    {lng:.7f} AS anchor_lng,
    {radius_m} AS radius_m,
    {address_scope_terms} AS address_scope_terms
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
  CROSS JOIN params p
  JOIN {dim_sections_table} ds
    ON CAST(ds.sectionId AS STRING) = nl.section_id
  WHERE COALESCE(ds.isarchived, FALSE) = FALSE
    AND (
      ARRAY_LENGTH(p.address_scope_terms) = 0
      OR EXISTS (
        SELECT 1
        FROM UNNEST(p.address_scope_terms) AS address_scope_term
        WHERE LOWER(COALESCE(ds.sectionAddress, '')) LIKE CONCAT('%', address_scope_term, '%')
           OR LOWER(COALESCE(ds.sectionName, '')) LIKE CONCAT('%', address_scope_term, '%')
      )
    )
),
org_sections AS (
  SELECT
    CAST(organisationId AS STRING) AS organisation_id,
    organisationName AS organisation_name,
    CAST(sectionId AS STRING) AS section_id,
    sectionName AS dim_section_name
  FROM {dim_org_section_table}
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
customer_latest_route_candidates AS (
  SELECT
    hubspot_company_id,
    customer_slug
  FROM {customer_knowledge_latest_table}
  WHERE customer_slug IS NOT NULL
  GROUP BY hubspot_company_id, customer_slug
),
customer_latest_routes AS (
  SELECT
    hubspot_company_id,
    customer_slug
  FROM customer_latest_route_candidates
  QUALIFY COUNT(*) OVER (PARTITION BY hubspot_company_id) = 1
),
customer_backfill_route_candidates AS (
  SELECT
    hubspot_company_id,
    customer_slug,
    REGEXP_REPLACE(
      REGEXP_REPLACE(LOWER(COALESCE(company_name, '')), r'\\b(pte|ltd|private limited|limited)\\b', ''),
      r'[^a-z0-9]+',
      ''
    ) AS company_name_key
  FROM {customer_wiki_backfill_accounts_table}
  WHERE customer_slug IS NOT NULL
  GROUP BY hubspot_company_id, customer_slug, company_name_key
),
customer_backfill_routes AS (
  SELECT
    hubspot_company_id,
    customer_slug
  FROM (
    SELECT DISTINCT
      hubspot_company_id,
      customer_slug
    FROM customer_backfill_route_candidates
  )
  QUALIFY COUNT(*) OVER (PARTITION BY hubspot_company_id) = 1
),
customer_route_by_name AS (
  SELECT
    company_name_key,
    customer_slug
  FROM (
    SELECT DISTINCT
      company_name_key,
      customer_slug
    FROM customer_backfill_route_candidates
    WHERE company_name_key != ''
  )
  QUALIFY COUNT(*) OVER (PARTITION BY company_name_key) = 1
),
customer_sections AS (
  SELECT
    js.area_id,
    js.area_name,
    js.organisation_id,
    c360.organisation_name,
    c360.company_id AS hubspot_company_id,
    c360.company_name AS c360_company_name,
    COALESCE(customer_latest.customer_slug, customer_backfill.customer_slug, customer_route_by_name.customer_slug) AS customer360_route_key,
    c360.hubspot_link,
    c360.company_usage_status AS usage_status,
    c360.company_usage_next_step AS usage_next_step,
    c360.company_low_usage_reason AS low_usage_reason,
    c360.deal_id,
    c360.deal_name,
    c360.deal_pipeline,
    c360.deal_stage,
    SAFE_CAST(c360.deal_start_date AS DATE) AS deal_start_date,
    SAFE_CAST(c360.deal_end_date AS DATE) AS deal_end_date,
    c360.deal_psm,
    CASE
      WHEN c360.deal_end_date IS NULL OR SAFE_CAST(c360.deal_end_date AS DATE) >= CURRENT_DATE()
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
  JOIN {fct_deal_org_company_table} c360
    ON CAST(c360.organisation_id AS STRING) = js.organisation_id
  LEFT JOIN {fct_company_org_mrr_table} mrr
    ON CAST(mrr.organisation_id AS STRING) = c360.organisation_id
   AND mrr.company_id = c360.company_id
  LEFT JOIN customer_latest_routes customer_latest
    ON customer_latest.hubspot_company_id = c360.company_id
  LEFT JOIN customer_backfill_routes customer_backfill
    ON customer_backfill.hubspot_company_id = c360.company_id
  LEFT JOIN customer_route_by_name
    ON customer_route_by_name.company_name_key = REGEXP_REPLACE(
      REGEXP_REPLACE(LOWER(COALESCE(c360.company_name, '')), r'\\b(pte|ltd|private limited|limited)\\b', ''),
      r'[^a-z0-9]+',
      ''
    )
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
{section_rollup_ctes}
SELECT
  ranked.area_id,
  ranked.area_name,
  ranked.organisation_id,
  ranked.organisation_name,
  ranked.hubspot_company_id,
  ranked.c360_company_name,
  ranked.customer360_route_key,
  ranked.usage_status,
  ranked.deal_stage,
  ranked.deal_end_date,
  ranked.selected_deal_status,
  ranked.company_mrr,
  ranked.nearest_section_name,
  ranked.nearest_address,
  ROUND(ranked.distance_m) AS nearest_distance_m,
  ranked.nearby_section_count{nearby_sections_select}
FROM ranked
{section_rollup_join}
WHERE ranked.row_rank = 1
ORDER BY
  CASE ranked.selected_deal_status
    WHEN 'current_or_open_selected_deal' THEN 0
    ELSE 1
  END,
  nearest_distance_m
LIMIT {MAX_C360_CUSTOMER_QUERY_RESULTS}"""


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
    if _place_is_closed(place):
        return False
    place_name = place.get("outlet_name") or place.get("name")
    outlet_name = outlet.get("outlet_name") or outlet.get("name")
    if not _names_are_compatible(place_name, outlet_name):
        return False

    place_address = place.get("formatted_address") or place.get("address")
    outlet_address = outlet.get("formatted_address") or outlet.get("address") or outlet.get("nearest_address")
    if place_address and outlet_address:
        return _address_has_same_building_or_street(place_address, outlet_address)

    return _compact_text(place_name) == _compact_text(outlet_name)


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
        "nearest_latitude": row.get("nearest_latitude") or row.get("latitude") or "",
        "nearest_longitude": row.get("nearest_longitude") or row.get("longitude") or "",
        "nearest_section_id": row.get("nearest_section_id") or row.get("section_id") or "",
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
    business_status = _google_business_status(place)
    rank_notes = ["Google Places live candidate, review needed; not a confirmed account."]
    if _place_is_closed(place):
        rank_notes.append("Google Places marks this place closed; verify before walk-in.")
    return {
        "source_flags": ["google_places_live"],
        "outlet_locations": [
            {
                "outlet_name": place.get("outlet_name") or place.get("name") or "",
                "google_place_id": place.get("google_place_id") or "",
                "google_maps_uri": place.get("google_maps_uri") or "",
                "formatted_address": place.get("formatted_address") or "",
                "google_business_status": business_status,
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
        "google_business_status": business_status,
        "rank_notes": rank_notes,
        "store_policy": "live_candidate_only_until_review_approval",
    }


def _merge_hubspot_prospect_item(row: dict[str, Any]) -> dict[str, Any]:
    account_status = "customer" if _is_customer_status(row.get("account_status") or row.get("type")) else "prospect"
    outlet_name = row.get("outlet_name") or row.get("place_name") or ""
    outlet = {
        "outlet_name": outlet_name,
        "google_place_id": row.get("google_place_id") or "",
        "google_maps_uri": row.get("google_maps_uri") or "",
        "formatted_address": row.get("formatted_address") or row.get("address") or "",
        "match_status": "candidate",
        "confidence": row.get("confidence") or "needs-check",
    }
    return {
        "source_flags": ["hubspot_target_prospect"],
        "outlet_locations": [outlet] if any(outlet.values()) else [],
        "hubspot_company_id": row.get("hubspot_company_id") or row.get("company_id") or row.get("id") or "",
        "customer360_route_key": row.get("customer360_route_key") or row.get("customer_slug") or "",
        "company_name": row.get("hubspot_company_name") or row.get("company_name") or outlet_name,
        "hubspot_owner_id": row.get("hubspot_owner_id") or "",
        "organisation_id": row.get("organisation_id") or "",
        "account_status": account_status,
        "match_status": "candidate",
        "confidence": row.get("confidence") or "needs-check",
        "nearest_distance_m": _distance(row),
        "google_place_id": row.get("google_place_id") or "",
        "rank_notes": ["HubSpot target prospect candidate; requires reviewed outlet/place match before storage."],
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
    if _place_is_closed(incoming):
        target["confidence"] = "needs-check"
        note = "Google Places marks this place closed; verify before walk-in."
        if note not in target["rank_notes"]:
            target["rank_notes"].append(note)


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
    if candidate and any(flag in item.get("source_flags", []) for flag in ("bigquery_outlet_match", "hubspot_target_prospect")):
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


def _compact_outlet_for_answer(outlet: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "outlet_name": outlet.get("outlet_name") or outlet.get("name") or "",
        "formatted_address": outlet.get("formatted_address") or outlet.get("address") or "",
        "google_maps_uri": outlet.get("google_maps_uri") or "",
        "match_status": outlet.get("match_status") or "",
        "confidence": outlet.get("confidence") or "",
        "google_business_status": outlet.get("google_business_status") or "",
    }
    return {key: value for key, value in compact.items() if value not in (None, "", [])}


def _compact_near_me_result_for_answer(item: dict[str, Any]) -> dict[str, Any]:
    outlets = item.get("outlet_locations") if isinstance(item.get("outlet_locations"), list) else []
    compact_outlets = [
        _compact_outlet_for_answer(outlet)
        for outlet in outlets[:MAX_MERGED_OUTLETS_PER_ACCOUNT]
        if isinstance(outlet, dict)
    ]
    answer_item = {
        "rank": item.get("rank"),
        "company_name": item.get("company_name") or "",
        "account_status": item.get("account_status") or "",
        "rank_category": item.get("rank_category") or "",
        "nearest_distance_m": item.get("nearest_distance_m"),
        "nearest_section": item.get("nearest_section") or "",
        "nearest_address": item.get("nearest_address") or "",
        "nearby_section_count": item.get("nearby_section_count") or "",
        "c360_url": item.get("c360_url") or "",
        "usage_status": item.get("usage_status") or "",
        "deal_stage": item.get("deal_stage") or "",
        "deal_end_date": item.get("deal_end_date") or "",
        "selected_deal_status": item.get("selected_deal_status") or "",
        "match_status": item.get("match_status") or "",
        "confidence": item.get("confidence") or "",
        "source_flags": item.get("source_flags") or [],
        "rank_notes": (item.get("rank_notes") or [])[:3],
        "outlet_locations": compact_outlets,
        "outlet_count": len(outlets),
        "store_policy": item.get("store_policy") or "",
    }
    return {key: value for key, value in answer_item.items() if value not in (None, "", [])}


def _compact_near_me_results_for_answer(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return [_compact_near_me_result_for_answer(item) for item in items[:limit]]


def _area_for_answer(area: dict[str, Any]) -> dict[str, Any]:
    return {
        key: area.get(key)
        for key in ("area_id", "area_name", "country", "radius_m", "snap_status")
        if area.get(key) not in (None, "", [])
    }


def _slack_safe_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text.replace("|", "/").replace("<", "").replace(">", "")


def _slack_link(label: Any, url: Any) -> str:
    safe_label = _slack_safe_text(label)
    safe_url = str(url or "").strip()
    if safe_label and safe_url:
        return f"<{safe_url}|{safe_label}>"
    return safe_label or safe_url


def _distance_label(value: Any) -> str:
    distance = _float_value(value)
    if distance is None:
        return ""
    if distance >= 1000:
        return f"{distance / 1000:.1f}km"
    return f"{round(distance)}m"


def _primary_place_label(item: dict[str, Any]) -> str:
    outlet = _first_outlet(item)
    outlet_name = _slack_safe_text(outlet.get("outlet_name") if outlet else "")
    if outlet_name:
        return outlet_name
    return _slack_safe_text(item.get("nearest_section") or item.get("nearest_address") or "")


def _deal_label(item: dict[str, Any]) -> str:
    deal_end_date = str(item.get("deal_end_date") or "").strip()
    if not deal_end_date:
        return ""
    if _is_past_deal(item):
        return f"past deal ended {deal_end_date[:10]}"
    return f"deal to {deal_end_date[:10]}"


def _account_answer_line(index: int, item: dict[str, Any], *, link_c360: bool = False) -> str:
    company_name = _slack_safe_text(item.get("company_name") or "Unknown account")
    label = _slack_link(company_name, item.get("c360_url")) if link_c360 else company_name
    place = _primary_place_label(item)
    distance = _distance_label(item.get("nearest_distance_m"))
    usage = _slack_safe_text(item.get("usage_status"))
    deal = _deal_label(item)
    notes = []
    if place and _compact_text(place) != _compact_text(company_name):
        notes.append(place)
    if distance:
        notes.append(distance)
    if usage:
        notes.append(usage)
    if deal:
        notes.append(deal)
    if item.get("confidence") == "needs-check":
        notes.append("needs check")
    suffix = f" - {' | '.join(notes)}" if notes else ""
    return f"{index}. {label}{suffix}"


def _candidate_answer_line(item: dict[str, Any]) -> str:
    outlet = _first_outlet(item)
    name = _slack_safe_text(item.get("company_name") or outlet.get("outlet_name") or "Unknown place")
    label = _slack_link(name, outlet.get("google_maps_uri"))
    distance = _distance_label(item.get("nearest_distance_m"))
    address = _slack_safe_text(outlet.get("formatted_address"))
    details = [value for value in (distance, address, "review needed") if value]
    return f"- {label}" + (f" - {' | '.join(details)}" if details else "")


def _near_me_slack_answer(
    area: dict[str, Any],
    customers: list[dict[str, Any]],
    prospects: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    counts: dict[str, int],
    truncated: dict[str, bool],
    confidence: str,
) -> str:
    area_name = _slack_safe_text(area.get("area_name") or "this known area")
    lines = [f"You're near {area_name}.", ""]

    if customers:
        lines.append("Customers to say hi to first:")
        for index, item in enumerate(customers, start=1):
            lines.append(_account_answer_line(index, item, link_c360=True))
    else:
        lines.append("Customers nearby: none found from C360/outlet matches.")

    if prospects:
        lines.extend(["", "Prospects nearby:"])
        for index, item in enumerate(prospects, start=1):
            lines.append(_account_answer_line(index, item))

    if candidates:
        lines.extend(["", "Google live candidates (not confirmed in CRM):"])
        for item in candidates:
            lines.append(_candidate_answer_line(item))

    more = []
    if truncated.get("customers_nearby"):
        more.append(f"{counts['customers_nearby'] - counts['returned_customers']} more customers")
    if truncated.get("prospects_nearby"):
        more.append(f"{counts['prospects_nearby'] - counts['returned_prospects']} more prospects")
    if truncated.get("live_candidates"):
        more.append(f"{counts['live_candidates'] - counts['returned_live_candidates']} more Google candidates")
    if more:
        lines.extend(["", "More available: " + ", ".join(more) + ". Ask to expand."])

    lines.extend(
        [
            "",
            "Source: curated outlet matches + C360 current customers + Google Places live refresh.",
            f"Confidence: {confidence}. Google-only rows are review needed, not confirmed accounts.",
        ]
    )
    return "\n".join(lines)


def _first_outlet(item: dict[str, Any]) -> dict[str, Any]:
    outlets = item.get("outlet_locations") if isinstance(item.get("outlet_locations"), list) else []
    for outlet in outlets:
        if isinstance(outlet, dict) and outlet.get("google_place_id") and not _place_is_closed(outlet):
            return outlet
    for outlet in outlets:
        if isinstance(outlet, dict) and outlet.get("outlet_name") and not _place_is_closed(outlet):
            return outlet
    for outlet in outlets:
        if isinstance(outlet, dict):
            return outlet
    return {}


def _review_candidate_key(item: dict[str, Any]) -> str:
    outlet = _first_outlet(item)
    place_id = str(outlet.get("google_place_id") or item.get("google_place_id") or "").strip()
    account = str(item.get("hubspot_company_id") or item.get("organisation_id") or "").strip()
    outlet_name = _compact_text(outlet.get("outlet_name") or "")
    address = outlet.get("formatted_address") or item.get("nearest_address") or ""
    address_key = next(iter(_postal_codes(address)), "") or _numbered_street_anchor(address) or _compact_text(address)
    if place_id:
        return f"place:{place_id}"
    if outlet_name:
        return f"outlet:{account}:{address_key}:{outlet_name}"
    return account or _compact_text(item.get("company_name") or outlet.get("outlet_name"))


def _review_candidate_evidence(item: dict[str, Any]) -> list[str]:
    evidence = []
    source_flags = ", ".join(item.get("source_flags") or [])
    if source_flags:
        evidence.append(f"sources={source_flags}")
    if item.get("nearest_distance_m") not in (None, "", 999999):
        evidence.append(f"distance_m={round(float(item['nearest_distance_m']))}")
    if item.get("nearest_section"):
        evidence.append(f"nearest_section={item['nearest_section']}")
    if item.get("nearest_address"):
        evidence.append(f"nearest_address={item['nearest_address']}")
    if item.get("deal_stage"):
        evidence.append(f"deal_stage={item['deal_stage']}")
    if item.get("selected_deal_status"):
        evidence.append(f"selected_deal_status={item['selected_deal_status']}")
    if item.get("ground_outlet_name_source"):
        evidence.append(f"ground_outlet_name_source={item['ground_outlet_name_source']}")
    return evidence


def _bq_record_to_dict(value: Any, field_names: list[str]) -> dict[str, Any]:
    if isinstance(value, dict) and any(key in value for key in field_names):
        return value
    record = value.get("v") if isinstance(value, dict) and "v" in value else value
    if isinstance(record, dict) and "f" in record:
        cells = record.get("f") or []
        return {
            field_name: cells[index].get("v") if index < len(cells) and isinstance(cells[index], dict) else None
            for index, field_name in enumerate(field_names)
        }
    if isinstance(value, dict) and "f" in value:
        cells = value.get("f") or []
        return {
            field_name: cells[index].get("v") if index < len(cells) and isinstance(cells[index], dict) else None
            for index, field_name in enumerate(field_names)
        }
    return {}


def _nearby_sections_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sections = row.get("nearby_sections") or row.get("section_candidates") or []
    if isinstance(raw_sections, str):
        try:
            parsed = json.loads(raw_sections)
        except json.JSONDecodeError:
            parsed = []
        raw_sections = parsed
    if not isinstance(raw_sections, list):
        return []

    field_names = ["section_id", "section_name", "section_address", "latitude", "longitude", "distance_m"]
    sections = []
    for raw in raw_sections:
        section = _bq_record_to_dict(raw, field_names)
        if not section:
            continue
        sections.append(
            {
                "section_id": section.get("section_id") or section.get("nearest_section_id") or "",
                "section_name": section.get("section_name") or section.get("nearest_section_name") or "",
                "section_address": section.get("section_address") or section.get("nearest_address") or "",
                "latitude": section.get("latitude") or section.get("nearest_latitude") or "",
                "longitude": section.get("longitude") or section.get("nearest_longitude") or "",
                "distance_m": section.get("distance_m") or section.get("nearest_distance_m") or "",
            }
        )
    return sections


def _proposed_ground_outlet_name_from_c360(row: dict[str, Any]) -> tuple[str, str]:
    existing = _clean_text_value(row.get("outlet_name") or row.get("place_name"))
    if existing and " @ " in existing:
        return existing, "reviewed_outlet_name"

    account_name = row.get("c360_company_name") or row.get("company_name") or row.get("organisation_name") or ""
    section_name = _clean_section_outlet_name(row.get("nearest_section_name") or row.get("nearest_section") or "")
    section_address = row.get("nearest_address") or row.get("section_address") or row.get("formatted_address") or ""
    if section_name and " @ " in section_name and not _section_name_is_noise(section_name):
        if _names_are_compatible(section_name, account_name) or _has_known_account_outlet_alias(account_name, section_name):
            return section_name, "section_name"
        return section_name, "section_name_account_conflict"

    location = _location_label_from_text(section_name, section_address, row.get("area_name"))
    if not location or not section_name or _section_name_is_noise(section_name):
        return "", ""
    if not (_names_are_compatible(section_name, account_name) or _has_known_account_outlet_alias(account_name, section_name)):
        return f"{section_name} @ {location}", "section_name_account_conflict"

    section_tokens = _meaningful_name_tokens(section_name)
    account_tokens = _meaningful_name_tokens(account_name)
    if section_tokens and section_tokens <= account_tokens and account_name and not _looks_like_legal_entity(account_name):
        brand = _clean_text_value(account_name, 160)
    else:
        brand = section_name
    if not brand or " @ " in brand:
        return brand, "section_name"
    return f"{brand} @ {location}", "section_name_plus_location"


def _clean_text_value(value: Any, maximum: int = 240) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:maximum]


def _expanded_c360_seed_rows(area: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
    sections = _nearby_sections_from_row(row)
    expanded = []
    for section in sections:
        next_row = dict(row)
        next_row["nearest_section_id"] = section.get("section_id") or ""
        next_row["nearest_section_name"] = section.get("section_name") or ""
        next_row["nearest_address"] = section.get("section_address") or ""
        next_row["nearest_latitude"] = section.get("latitude") or ""
        next_row["nearest_longitude"] = section.get("longitude") or ""
        next_row["nearest_distance_m"] = section.get("distance_m") or row.get("nearest_distance_m") or ""
        proposed_name, source = _proposed_ground_outlet_name_from_c360(next_row)
        if proposed_name:
            next_row["outlet_name"] = proposed_name
            next_row["ground_outlet_name_source"] = source
        if _row_matches_area_address_scope(area, next_row):
            expanded.append(next_row)

    if expanded:
        proposed = [candidate for candidate in expanded if str(candidate.get("outlet_name") or "").strip()]
        return proposed or expanded
    if _row_matches_area_address_scope(area, row):
        return [row]
    return []


def _merge_c360_seed_item(row: dict[str, Any]) -> dict[str, Any]:
    item = _merge_c360_item(row)
    if row.get("ground_outlet_name_source") and row.get("outlet_name"):
        proposed_name = _clean_text_value(row.get("outlet_name"))
        source = str(row.get("ground_outlet_name_source") or "")
    else:
        proposed_name, source = _proposed_ground_outlet_name_from_c360(row)
    if proposed_name:
        item["outlet_locations"] = [
            {
                "outlet_name": proposed_name,
                "google_place_id": row.get("google_place_id") or "",
                "google_maps_uri": row.get("google_maps_uri") or "",
                "formatted_address": row.get("formatted_address") or row.get("nearest_address") or "",
                "latitude": row.get("nearest_latitude") or row.get("latitude") or "",
                "longitude": row.get("nearest_longitude") or row.get("longitude") or "",
                "section_id": row.get("nearest_section_id") or row.get("section_id") or "",
                "match_status": "candidate",
                "confidence": item.get("confidence") or "needs-check",
                "ground_outlet_name_source": source,
            }
        ]
        item["ground_outlet_name_source"] = source
        note = "Ground outlet name proposed from C360 section; reviewer must confirm before write."
        if note not in item["rank_notes"]:
            item["rank_notes"].append(note)
    return item


def _seed_review_group_key(item: dict[str, Any]) -> str:
    outlet = _first_outlet(item)
    place_id = str(outlet.get("google_place_id") or item.get("google_place_id") or "").strip()
    account = str(item.get("hubspot_company_id") or item.get("organisation_id") or "").strip()
    outlet_name = _compact_text(outlet.get("outlet_name") or "")
    address = outlet.get("formatted_address") or item.get("nearest_address") or ""
    address_key = next(iter(_postal_codes(address)), "") or _numbered_street_anchor(address) or _compact_text(address)
    if place_id:
        return f"place:{place_id}"
    if outlet_name:
        return f"outlet:{account}:{address_key}:{outlet_name}"
    return _account_key(item)


def _seed_review_candidate(area: dict[str, Any], item: dict[str, Any], rank: int) -> dict[str, Any]:
    outlet = _first_outlet(item)
    account_status = "customer" if _is_customer_status(item.get("account_status")) else item.get("account_status") or "unknown"
    has_account_link = bool(str(item.get("hubspot_company_id") or "").strip() or str(item.get("organisation_id") or "").strip())
    has_ground_outlet_name = bool(str(outlet.get("outlet_name") or "").strip())
    google_closed = _place_is_closed(outlet)
    brand_review_needed = _needs_account_outlet_brand_review(item, outlet)
    eligible = bool(
        has_account_link
        and has_ground_outlet_name
        and account_status in {"customer", "prospect"}
        and not google_closed
        and not brand_review_needed
    )
    if google_closed:
        review_action = "verify_closed_or_relocated_place_before_approval"
    elif brand_review_needed:
        review_action = "verify_account_outlet_brand_before_approval"
    elif not has_ground_outlet_name and has_account_link:
        review_action = "add_ground_outlet_name_before_approval"
    elif eligible:
        review_action = "approve_confirmed_match"
    else:
        review_action = "link_account_before_approval"
    data_quality_flags = []
    if brand_review_needed:
        data_quality_flags.append("section_outlet_name_conflicts_with_account_name")
    candidate = {
        "rank": rank,
        "area_id": area["area_id"],
        "area_name": area["area_name"],
        "outlet_name": outlet.get("outlet_name") or "",
        "account_name": item.get("company_name") or "",
        "ground_outlet_name_status": (
            "needs_account_outlet_brand_review"
            if brand_review_needed
            else "reviewed_or_place_name_present"
            if has_ground_outlet_name
            else "needs_ground_outlet_name"
        ),
        "formatted_address": outlet.get("formatted_address") or item.get("nearest_address") or "",
        "google_place_id": outlet.get("google_place_id") or item.get("google_place_id") or "",
        "google_maps_uri": outlet.get("google_maps_uri") or "",
        "google_business_status": outlet.get("google_business_status") or item.get("google_business_status") or "",
        "latitude": outlet.get("latitude") or item.get("nearest_latitude") or "",
        "longitude": outlet.get("longitude") or item.get("nearest_longitude") or "",
        "hubspot_company_id": item.get("hubspot_company_id") or "",
        "hubspot_company_name": item.get("company_name") or "",
        "hubspot_owner_id": item.get("hubspot_owner_id") or "",
        "organisation_id": item.get("organisation_id") or "",
        "account_status": account_status,
        "match_status": "candidate",
        "confidence": item.get("confidence") or "needs-check",
        "source_flags": item.get("source_flags") or [],
        "evidence": _review_candidate_evidence(item),
        "ground_outlet_name_source": outlet.get("ground_outlet_name_source") or item.get("ground_outlet_name_source") or "",
        "data_quality_flags": data_quality_flags,
        "eligible_for_bigquery_write": eligible,
        "review_action_required": review_action,
        "approved_row_template": {
            "area_id": area["area_id"],
            "area_name": area["area_name"],
            "outlet_name": outlet.get("outlet_name") or "",
            "google_place_id": outlet.get("google_place_id") or item.get("google_place_id") or "",
            "formatted_address": outlet.get("formatted_address") or item.get("nearest_address") or "",
            "latitude": outlet.get("latitude") or item.get("nearest_latitude") or "",
            "longitude": outlet.get("longitude") or item.get("nearest_longitude") or "",
            "google_maps_uri": outlet.get("google_maps_uri") or "",
            "google_business_status": outlet.get("google_business_status") or item.get("google_business_status") or "",
            "hubspot_company_id": item.get("hubspot_company_id") or "",
            "hubspot_company_name": item.get("company_name") or "",
            "hubspot_owner_id": item.get("hubspot_owner_id") or "",
            "organisation_id": item.get("organisation_id") or "",
            "account_status": account_status,
            "match_status": "confirmed",
            "confidence": "verified",
            "source": "workflow",
        }
        if eligible
        else {},
    }
    return candidate


def _rank_seed_review_items(
    area: dict[str, Any],
    google_places: list[dict[str, Any]] | None,
    c360_customer_rows: list[dict[str, Any]] | None,
    hubspot_prospect_rows: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    for row in c360_customer_rows or []:
        if not isinstance(row, dict):
            continue
        for expanded_row in _expanded_c360_seed_rows(area, row):
            item = _merge_c360_seed_item(expanded_row)
            key = _seed_review_group_key(item)
            if key in groups:
                _absorb(groups[key], item)
            else:
                groups[key] = item

    for row in hubspot_prospect_rows or []:
        if not isinstance(row, dict):
            continue
        item = _merge_hubspot_prospect_item(row)
        key = _seed_review_group_key(item)
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
    return ranked


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
    include_nearby_sections: bool = False,
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

    sql = _near_me_c360_sql(area, include_nearby_sections=include_nearby_sections)
    return {
        "answer": {
            "known_area": area,
            "c360_dataset": _c360_dataset(),
            "execute_with": "staffany_bigquery.execute_sql_readonly",
            "sql": sql,
            "expected_output": (
                "One compact row per organisation_id with nearest section, distance, HubSpot company, "
                "C360 usage/deal context, and optional MRR."
                if not include_nearby_sections
                else "One row per organisation_id with nearest section plus nearby_sections for seed review."
            ),
        },
        "source": "C360 BigQuery SQL builder",
        "scope": {
            **scope,
            "location_source": location_source,
            "c360_dataset": _c360_dataset(),
            "include_nearby_sections": include_nearby_sections,
        },
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
def prepare_near_me_seed_review_candidates(
    slack_user_email: str,
    area_id: str,
    google_places: list[dict[str, Any]] | None = None,
    c360_customer_rows: list[dict[str, Any]] | None = None,
    hubspot_prospect_rows: list[dict[str, Any]] | None = None,
    candidate_limit: int = MAX_SEED_REVIEW_CANDIDATES_PER_AREA,
) -> dict[str, Any]:
    """Prepare capped Slack review candidates for near-me outlet-match seeding."""

    capped_limit = _bounded_int(
        candidate_limit,
        MAX_SEED_REVIEW_CANDIDATES_PER_AREA,
        MAX_SEED_REVIEW_CANDIDATES_PER_AREA,
    )
    scope = _scope(
        slack_user_email,
        {
            "area_id": area_id,
            "candidate_limit": capped_limit,
            "google_place_count": len(google_places or []),
            "c360_customer_row_count": len(c360_customer_rows or []),
            "hubspot_prospect_row_count": len(hubspot_prospect_rows or []),
        },
    )
    try:
        area = _area_public(_known_area_by_id(area_id))
    except NearMeError as error:
        return _blocked(str(error), scope, "Near-me seed review")

    ranked = _rank_seed_review_items(area, google_places, c360_customer_rows, hubspot_prospect_rows)
    deduped = []
    seen = set()
    for item in ranked:
        key = _review_candidate_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= capped_limit:
            break

    candidates = [_seed_review_candidate(area, item, rank) for rank, item in enumerate(deduped, start=1)]
    return {
        "answer": {
            "known_area": area,
            "review_candidates": candidates,
            "candidate_count": len(candidates),
            "candidate_limit": capped_limit,
            "slack_review_policy": {
                "surface": "message_thread",
                "approvers": "configured managers and admins with Singapore scope",
                "write_path": "restricted_bigquery_writer_job",
                "approval_state": "Slack thread until commit",
            },
            "store_policy": "Only approved confirmed rows with a HubSpot Company or StaffAny organisation link may be written.",
        },
        "source": "Google Places candidates + C360 customers + HubSpot target prospects",
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Review-only. Google-only rows are not eligible for BigQuery write until linked to a customer or prospect account.",
    }


@mcp.tool()
def merge_near_me_sources(
    slack_user_email: str,
    known_area: dict[str, Any],
    outlet_matches: list[dict[str, Any]] | None = None,
    outlet_locations: list[dict[str, Any]] | None = None,
    c360_customer_rows: list[dict[str, Any]] | None = None,
    google_places: list[dict[str, Any]] | None = None,
    include_debug_rows: bool = False,
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
            "c360_customer_rows_provided": c360_customer_rows is not None,
            "google_place_count": len(google_places or []),
        },
    )
    if c360_customer_rows is None:
        return _blocked(
            "C360 current-customer rows are required before merging near-me results. "
            "Run build_near_me_c360_customer_query through staffany_bigquery.execute_sql_readonly, "
            "then call merge_near_me_sources again with c360_customer_rows, even if the result is an empty list.",
            scope,
            "Known Area Near-Me merge validation",
        ) | {
            "next_required_steps": [
                "build_near_me_c360_customer_query",
                "staffany_bigquery.execute_sql_readonly",
                "merge_near_me_sources with c360_customer_rows",
            ],
            "runtime_validation": {
                "can_answer": False,
                "missing_required_source": "C360 current-customer BigQuery rows",
            },
        }
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
        if not _row_matches_area_address_scope(area, row):
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
    customer_limit = MAX_MERGED_CUSTOMERS_FOR_ANSWER
    prospect_limit = MAX_MERGED_PROSPECTS_FOR_ANSWER
    live_candidate_limit = MAX_MERGED_LIVE_CANDIDATES_FOR_ANSWER
    customers_answer = _compact_near_me_results_for_answer(customers, customer_limit)
    prospects_answer = _compact_near_me_results_for_answer(prospects, prospect_limit)
    candidates_answer = _compact_near_me_results_for_answer(candidates, live_candidate_limit)
    truncated = {
        "customers_nearby": len(customers) > len(customers_answer),
        "prospects_nearby": len(prospects) > len(prospects_answer),
        "live_candidates": len(candidates) > len(candidates_answer),
    }
    if any(truncated.values()):
        caveats.append("Only top near-me results are returned; ask to expand for the rest.")
    counts = {
        "customers_nearby": len(customers),
        "prospects_nearby": len(prospects),
        "live_candidates": len(candidates),
        "all_results": len(ranked),
        "returned_customers": len(customers_answer),
        "returned_prospects": len(prospects_answer),
        "returned_live_candidates": len(candidates_answer),
    }
    result_confidence = "needs-check" if candidates or has_missing_c360_links else "verified"
    slack_answer = _near_me_slack_answer(
        area,
        customers_answer,
        prospects_answer,
        candidates_answer,
        counts,
        truncated,
        result_confidence,
    )
    runtime_validation = {
        "can_answer": True,
        "final_answer_must_use_merge_output": True,
        "required_sources": {
            "outlet_matches": selected_outlet_matches is not None,
            "c360_customer_rows": c360_customer_rows is not None,
            "google_places": google_places is not None,
        },
    }

    answer = {
        "known_area": _area_for_answer(area),
        "slack_answer": slack_answer,
        "counts": counts,
        "truncated": truncated,
        "rendering_instructions": [
            "For normal Slack near-me answers, copy answer.slack_answer verbatim.",
            "Use only this merged answer payload for the Slack final answer.",
            "Do not answer from raw BigQuery or Google Places rows directly.",
        ],
        "runtime_validation": runtime_validation,
    }
    if include_debug_rows:
        answer.update(
            {
                "customers_nearby": customers_answer,
                "prospects_nearby": prospects_answer,
                "live_candidates": candidates_answer,
                "ranking_order": [
                    "confirmed_outlet_current_customer",
                    "c360_current_customer_without_stored_outlet",
                    "confirmed_outlet_prospect",
                    "candidate_outlet_match",
                    "google_places_live_candidate",
                ],
            }
        )

    return {
        "answer": answer,
        "source": "BigQuery outlet_matches + C360 BigQuery + Google Places",
        "scope": {**scope, "include_debug_rows": include_debug_rows},
        "runtime_validation": runtime_validation,
        "confidence": result_confidence,
        "caveat": " ".join(caveats) if caveats else "No HubSpot write-back or Google candidate storage happened.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
