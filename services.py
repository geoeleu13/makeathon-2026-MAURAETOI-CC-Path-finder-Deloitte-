"""
External API layer for Pathfinder — Deloitte competition toolset.
All location handling is dynamic; no hardcoded regions.
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Callable, Union

import requests
from dotenv import load_dotenv

load_dotenv()

# API keys (set in .env)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY", "")

# Endpoints
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENROUTESERVICE_DIRECTIONS_URL = (
    "https://api.openrouteservice.org/v2/directions/foot-hiking/geojson"
)
INATURALIST_OBSERVATIONS_URL = "https://api.inaturalist.org/v1/observations"
# NASA SRTM 30 m via OpenTopoData (public SRTM mirror)
OPENTOPO_SRTM_URL = "https://api.opentopodata.org/v1/srtm30m"

USER_AGENT = "Pathfinder-TrailCompanion/1.0"

_SAC_TO_DIFFICULTY = {
    "hiking": "easy",
    "mountain_hiking": "moderate",
    "demanding_mountain_hiking": "hard",
    "alpine_hiking": "expert",
    "demanding_alpine_hiking": "expert",
    "difficult_alpine_hiking": "expert",
}

_DIFFICULTY_ALIASES = {
    "easy": {"easy", "beginner", "εύκολο", "ευκολο"},
    "moderate": {"moderate", "medium", "μέτριο", "μετριο"},
    "hard": {"hard", "difficult", "δύσκολο", "δυσκολο"},
    "expert": {"expert", "extreme", "εξπερτ"},
}


# ── Tool registry (for AI / orchestration) ─────────────────────────────────────

PATHFINDER_TOOLS: dict[str, dict[str, Any]] = {
    "get_weather": {
        "description": "Current weather at coordinates (OpenWeatherMap).",
        "params": ["lat", "lon"],
    },
    "get_trails_overpass": {
        "description": "Hiking trails and outdoor POIs in a bounding box (OSM Overpass).",
        "params": ["bbox"],
    },
    "get_route": {
        "description": "Foot-hiking route between two points (OpenRouteService).",
        "params": ["start_coords", "end_coords"],
    },
    "get_biodiversity": {
        "description": "Recent flora/fauna observations near coordinates (iNaturalist).",
        "params": ["lat", "lon"],
    },
    "get_elevation": {
        "description": "Terrain elevation from NASA SRTM 30 m (via OpenTopoData).",
        "params": ["lat", "lon"],
    },
    "get_real_time_conditions": {
        "description": "Trail closures, barriers, construction near a location (Overpass).",
        "params": ["location"],
    },
    "calculate_sustainability_score": {
        "description": "Score 0–100 for crowd avoidance and low environmental impact.",
        "params": ["trail_data"],
    },
}


def _headers(*, json_content: bool = False) -> dict[str, str]:
    h = {"User-Agent": USER_AGENT}
    if json_content:
        h["Content-Type"] = "application/json"
    return h


def _ors_headers() -> dict[str, str]:
    h = _headers(json_content=True)
    if OPENROUTESERVICE_API_KEY:
        h["Authorization"] = OPENROUTESERVICE_API_KEY
    return h


def _normalize_difficulty(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().lower()
    for level, aliases in _DIFFICULTY_ALIASES.items():
        if key in aliases:
            return level
    return key if key in _DIFFICULTY_ALIASES else None


def _parse_lat_lon_string(value: str) -> tuple[float, float] | None:
    parts = re.split(r"[,;\s]+", value.strip())
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def parse_coords(
    coords: Union[str, dict[str, float], tuple[float, float], list[float]],
) -> tuple[float, float] | None:
    """Normalize (lat, lon) from string, dict, or sequence."""
    if isinstance(coords, str):
        return _parse_lat_lon_string(coords)
    if isinstance(coords, dict):
        if "lat" in coords and "lon" in coords:
            return float(coords["lat"]), float(coords["lon"])
        if "latitude" in coords and "longitude" in coords:
            return float(coords["latitude"]), float(coords["longitude"])
    if isinstance(coords, (tuple, list)) and len(coords) >= 2:
        return float(coords[0]), float(coords[1])
    return None


def _normalize_bbox(bbox: dict[str, float]) -> dict[str, float] | None:
    required = ("south", "west", "north", "east")
    if not all(k in bbox for k in required):
        return None
    south, west, north, east = (
        float(bbox["south"]),
        float(bbox["west"]),
        float(bbox["north"]),
        float(bbox["east"]),
    )
    if south >= north or west >= east:
        return None
    return {"south": south, "west": west, "north": north, "east": east}


def _bbox_str(bbox: dict[str, float]) -> str:
    return f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"


def _bbox_around_point(lat: float, lon: float, radius_km: float) -> dict[str, float]:
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * max(0.3, abs(math.cos(math.radians(lat)))))
    return {
        "south": lat - lat_delta,
        "north": lat + lat_delta,
        "west": lon - lon_delta,
        "east": lon + lon_delta,
    }


def geocode_location(
    location_name: str,
    *,
    country: str = "gr",
) -> dict[str, Any] | None:
    """Resolve a place name to coordinates via Nominatim."""
    if not location_name or not location_name.strip():
        return None

    params = {
        "q": location_name.strip(),
        "format": "json",
        "limit": 1,
        "countrycodes": country.lower(),
    }
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException:
        return None

    if not results:
        return None

    hit = results[0]
    bbox = hit.get("boundingbox")
    return {
        "name": hit.get("display_name", location_name),
        "lat": float(hit["lat"]),
        "lon": float(hit["lon"]),
        "bbox": {
            "south": float(bbox[0]),
            "north": float(bbox[1]),
            "west": float(bbox[2]),
            "east": float(bbox[3]),
        }
        if bbox and len(bbox) == 4
        else None,
    }


def resolve_bbox_or_location(
    bbox_or_location: Union[str, dict[str, float], tuple[float, float]],
    *,
    radius_km: float = 12.0,
) -> dict[str, float] | None:
    if isinstance(bbox_or_location, dict):
        normalized = _normalize_bbox(bbox_or_location)
        if normalized:
            return normalized
        if "lat" in bbox_or_location and "lon" in bbox_or_location:
            return _bbox_around_point(
                float(bbox_or_location["lat"]),
                float(bbox_or_location["lon"]),
                float(bbox_or_location.get("radius_km", radius_km)),
            )

    if isinstance(bbox_or_location, (tuple, list)) and len(bbox_or_location) >= 2:
        return _bbox_around_point(
            float(bbox_or_location[0]),
            float(bbox_or_location[1]),
            radius_km,
        )

    if isinstance(bbox_or_location, str):
        coords = _parse_lat_lon_string(bbox_or_location)
        if coords:
            return _bbox_around_point(coords[0], coords[1], radius_km)
        geo = geocode_location(bbox_or_location)
        if not geo:
            return None
        if geo.get("bbox"):
            return geo["bbox"]
        return _bbox_around_point(geo["lat"], geo["lon"], radius_km)

    return None


def resolve_location(location: Union[str, dict[str, Any]]) -> dict[str, Any] | None:
    if isinstance(location, dict) and "lat" in location and "lon" in location:
        lat, lon = float(location["lat"]), float(location["lon"])
        return {
            "name": location.get("name", f"{lat}, {lon}"),
            "lat": lat,
            "lon": lon,
            "bbox": location.get("bbox") or _bbox_around_point(lat, lon, 12.0),
        }
    if isinstance(location, str):
        coords = _parse_lat_lon_string(location)
        if coords:
            lat, lon = coords
            return {
                "name": location,
                "lat": lat,
                "lon": lon,
                "bbox": _bbox_around_point(lat, lon, 12.0),
            }
        return geocode_location(location)
    return None


# ── Deloitte API tools ─────────────────────────────────────────────────────────


def get_weather(lat: float, lon: float) -> dict[str, Any]:
    """Current weather from OpenWeatherMap."""
    if not OPENWEATHER_API_KEY:
        return {
            "ok": False,
            "error": "OPENWEATHER_API_KEY is not set in .env",
            "lat": lat,
            "lon": lon,
        }

    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "el",
    }
    try:
        resp = requests.get(OPENWEATHER_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "lat": lat, "lon": lon}

    main = data.get("main", {})
    wind = data.get("wind", {})
    weather_list = data.get("weather") or [{}]

    return {
        "ok": True,
        "source": "openweathermap",
        "lat": lat,
        "lon": lon,
        "location": data.get("name"),
        "description": weather_list[0].get("description"),
        "icon": weather_list[0].get("icon"),
        "temp_c": main.get("temp"),
        "feels_like_c": main.get("feels_like"),
        "humidity_pct": main.get("humidity"),
        "wind_speed_ms": wind.get("speed"),
        "wind_deg": wind.get("deg"),
        "visibility_m": data.get("visibility"),
    }


def get_trails_overpass(
    bbox: dict[str, float],
    *,
    limit_trails: int = 25,
    limit_pois: int = 20,
) -> dict[str, Any]:
    """
    Hiking trails and outdoor POIs from OpenStreetMap via Overpass API.
    bbox: {south, west, north, east}
    """
    normalized = _normalize_bbox(bbox)
    if not normalized:
        return {
            "ok": False,
            "error": "Invalid bbox. Required keys: south, west, north, east.",
            "trails": [],
            "pois": [],
        }

    bbox_s = _bbox_str(normalized)
    query = f"""
    [out:json][timeout:35];
    (
      way["highway"~"^(path|footway|track)$"]["name"]({bbox_s});
      way["route"="hiking"]["name"]({bbox_s});
      relation["route"="hiking"]({bbox_s});
      node["tourism"="viewpoint"]["name"]({bbox_s});
      node["natural"="peak"]["name"]({bbox_s});
      node["amenity"="drinking_water"]({bbox_s});
      node["tourism"~"^(wilderness_hut|alpine_hut)$"]({bbox_s});
      node["information"="map"]({bbox_s});
      node["historic"="archaeological_site"]["name"]({bbox_s});
      node["tourism"="attraction"]({bbox_s});
      node["amenity"~"^(restaurant|cafe|fast_food)$"]({bbox_s});
    );
    out tags center 50;
    """

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers=_headers(),
            timeout=50,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": str(exc),
            "bbox": normalized,
            "trails": [],
            "pois": [],
        }

    trails: list[dict[str, Any]] = []
    pois: list[dict[str, Any]] = []
    poi_keys = {
        "tourism",
        "natural",
        "amenity",
        "historic",
        "information",
    }

    for el in elements:
        tags = el.get("tags") or {}
        center = el.get("center") or {}
        lat = center.get("lat") or el.get("lat")
        lon = center.get("lon") or el.get("lon")
        name = tags.get("name") or tags.get("ref")

        is_trail = (
            tags.get("route") == "hiking"
            or tags.get("highway") in ("path", "footway", "track")
        )
        is_poi = any(k in tags for k in poi_keys) and not is_trail

        if is_trail:
            sac = tags.get("sac_scale", "")
            trails.append(
                {
                    "id": el.get("id"),
                    "type": el.get("type"),
                    "name": name or f"Trail {el.get('type')}/{el.get('id')}",
                    "difficulty": _SAC_TO_DIFFICULTY.get(sac, "unknown"),
                    "surface": tags.get("surface"),
                    "sac_scale": sac or None,
                    "length_km": tags.get("distance"),
                    "tracktype": tags.get("tracktype"),
                    "trail_visibility": tags.get("trail_visibility"),
                    "access": tags.get("access"),
                    "lat": lat,
                    "lon": lon,
                    "tags": {
                        k: v
                        for k, v in tags.items()
                        if k
                        in (
                            "surface",
                            "sac_scale",
                            "tracktype",
                            "trail_visibility",
                            "access",
                            "operator",
                            "boundary",
                            "protect_class",
                            "leisure",
                        )
                    },
                }
            )
        elif is_poi or (name and el.get("type") == "node"):
            pois.append(
                {
                    "id": el.get("id"),
                    "name": name or "Unnamed POI",
                    "category": (
                        tags.get("tourism")
                        or tags.get("natural")
                        or tags.get("amenity")
                        or tags.get("historic")
                        or tags.get("information")
                    ),
                    "ele_m": tags.get("ele"),
                    "lat": lat,
                    "lon": lon,
                }
            )

    return {
        "ok": True,
        "source": "openstreetmap_overpass",
        "bbox": normalized,
        "trail_count": min(len(trails), limit_trails),
        "poi_count": min(len(pois), limit_pois),
        "trails": trails[:limit_trails],
        "pois": pois[:limit_pois],
    }


def get_route(
    start_coords: Union[str, dict[str, float], tuple[float, float], list[float]],
    end_coords: Union[str, dict[str, float], tuple[float, float], list[float]],
    *,
    profile: str = "foot-hiking",
) -> dict[str, Any]:
    """
    Hiking route between two points via OpenRouteService.
    Coordinates: (lat, lon) — converted to [lon, lat] for ORS.
    """
    start = parse_coords(start_coords)
    end = parse_coords(end_coords)
    if not start or not end:
        return {
            "ok": False,
            "error": "Invalid start_coords or end_coords. Use (lat, lon), dict, or 'lat,lon'.",
        }

    if not OPENROUTESERVICE_API_KEY:
        return {
            "ok": False,
            "error": "OPENROUTESERVICE_API_KEY is not set in .env",
            "start": {"lat": start[0], "lon": start[1]},
            "end": {"lat": end[0], "lon": end[1]},
        }

    start_lat, start_lon = start
    end_lat, end_lon = end
    body = {
        "coordinates": [
            [start_lon, start_lat],
            [end_lon, end_lat],
        ]
    }

    try:
        resp = requests.post(
            OPENROUTESERVICE_DIRECTIONS_URL,
            json=body,
            headers=_ors_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": str(exc),
            "start": {"lat": start_lat, "lon": start_lon},
            "end": {"lat": end_lat, "lon": end_lon},
        }

    features = data.get("features") or []
    if not features:
        return {
            "ok": False,
            "error": "No route returned.",
            "start": {"lat": start_lat, "lon": start_lon},
            "end": {"lat": end_lat, "lon": end_lon},
        }

    props = features[0].get("properties", {}) or {}
    summary = props.get("summary", {}) or {}
    segments = props.get("segments", []) or []
    steps = []
    for seg in segments[:1]:
        for step in (seg.get("steps") or [])[:12]:
            steps.append(
                {
                    "instruction": step.get("instruction"),
                    "distance_m": step.get("distance"),
                    "duration_s": step.get("duration"),
                }
            )

    geometry = features[0].get("geometry", {})
    return {
        "ok": True,
        "source": "openrouteservice",
        "profile": profile,
        "start": {"lat": start_lat, "lon": start_lon},
        "end": {"lat": end_lat, "lon": end_lon},
        "distance_m": summary.get("distance"),
        "duration_s": summary.get("duration"),
        "ascent_m": summary.get("ascent"),
        "descent_m": summary.get("descent"),
        "steps": steps,
        "geometry_type": geometry.get("type"),
        "coordinate_count": len(geometry.get("coordinates") or []),
    }


def get_biodiversity(
    lat: float,
    lon: float,
    *,
    radius_km: float = 5.0,
    per_page: int = 15,
) -> dict[str, Any]:
    """Flora / fauna observations near coordinates via iNaturalist API."""
    params = {
        "lat": lat,
        "lng": lon,
        "radius": radius_km,
        "per_page": per_page,
        "order": "desc",
        "order_by": "observed_on",
        "locale": "el",
    }
    try:
        resp = requests.get(
            INATURALIST_OBSERVATIONS_URL,
            params=params,
            headers=_headers(),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "lat": lat, "lon": lon, "observations": []}

    observations: list[dict[str, Any]] = []
    for obs in data.get("results") or []:
        taxon = obs.get("taxon") or {}
        observations.append(
            {
                "id": obs.get("id"),
                "species": taxon.get("preferred_common_name") or taxon.get("name"),
                "scientific_name": taxon.get("name"),
                "iconic_taxon": taxon.get("iconic_taxon_name"),
                "observed_on": obs.get("observed_on"),
                "quality_grade": obs.get("quality_grade"),
                "lat": (obs.get("location") or ",").split(",")[0] if obs.get("location") else None,
                "url": f"https://www.inaturalist.org/observations/{obs.get('id')}",
            }
        )

    taxa_summary: dict[str, int] = {}
    for o in observations:
        key = o.get("iconic_taxon") or "Unknown"
        taxa_summary[key] = taxa_summary.get(key, 0) + 1

    return {
        "ok": True,
        "source": "inaturalist",
        "lat": lat,
        "lon": lon,
        "radius_km": radius_km,
        "total_results": data.get("total_results", len(observations)),
        "taxa_summary": taxa_summary,
        "observations": observations,
        "sustainability_note": (
            "Observe wildlife from a distance; do not disturb habitats. "
            "Follow Leave No Trace principles."
        ),
    }


def get_elevation(lat: float, lon: float) -> dict[str, Any]:
    """
    Elevation at coordinates using NASA SRTM 30 m (OpenTopoData public API).
    """
    params = {"locations": f"{lat},{lon}"}
    try:
        resp = requests.get(OPENTOPO_SRTM_URL, params=params, headers=_headers(), timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "lat": lat, "lon": lon}

    results = data.get("results") or []
    if not results:
        return {"ok": False, "error": "No elevation data returned.", "lat": lat, "lon": lon}

    point = results[0]
    elevation = point.get("elevation")
    if elevation is None:
        return {
            "ok": False,
            "error": point.get("error") or "Elevation unavailable for this point.",
            "lat": lat,
            "lon": lon,
        }

    return {
        "ok": True,
        "source": "nasa_srtm30m_opentopodata",
        "dataset": data.get("elevation_dataset", "srtm30m"),
        "lat": lat,
        "lon": lon,
        "elevation_m": round(float(elevation), 1),
        "resolution_m": 30,
    }


def get_real_time_conditions(
    location: Union[str, dict[str, Any]],
    *,
    radius_km: float = 15.0,
) -> dict[str, Any]:
    """Trail access issues, barriers, and construction near a location (Overpass)."""
    resolved = resolve_location(location)
    if not resolved:
        return {
            "ok": False,
            "error": "Could not resolve location.",
            "closures": [],
            "barriers": [],
            "events": [],
        }

    bbox = resolved.get("bbox") or _bbox_around_point(
        resolved["lat"], resolved["lon"], radius_km
    )
    bbox_s = _bbox_str(bbox)

    query = f"""
    [out:json][timeout:30];
    (
      way["highway"~"^(path|footway|track)$"]["access"~"^(no|private)$"]({bbox_s});
      way["highway"~"^(path|footway|track)$"]["construction"]({bbox_s});
      node["barrier"]({bbox_s});
      way["barrier"]({bbox_s});
    );
    out tags center 30;
    """

    closures: list[dict[str, Any]] = []
    barriers: list[dict[str, Any]] = []

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers=_headers(),
            timeout=45,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": str(exc),
            "location": resolved,
            "closures": [],
            "barriers": [],
            "events": _fetch_events_placeholder(resolved),
        }

    for el in elements:
        tags = el.get("tags") or {}
        center = el.get("center") or {}
        item = {
            "id": el.get("id"),
            "type": el.get("type"),
            "name": tags.get("name"),
            "access": tags.get("access"),
            "construction": tags.get("construction"),
            "barrier": tags.get("barrier"),
            "note": tags.get("note") or tags.get("description"),
            "lat": center.get("lat") or el.get("lat"),
            "lon": center.get("lon") or el.get("lon"),
        }
        if tags.get("access") in ("no", "private") or tags.get("construction"):
            closures.append(item)
        elif tags.get("barrier"):
            barriers.append(item)

    return {
        "ok": True,
        "location": resolved,
        "summary": {
            "closed_or_restricted": len(closures),
            "barriers": len(barriers),
        },
        "closures": closures,
        "barriers": barriers,
        "events": _fetch_events_placeholder(resolved),
    }


def _fetch_events_placeholder(resolved: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "source": "placeholder",
            "message": (
                f"No live events API configured for «{resolved.get('name', 'area')}». "
                "Integrate a regional events feed when available."
            ),
        }
    ]


# ── Sustainability scoring ─────────────────────────────────────────────────────

_HOTSPOT_TOURISM = frozenset(
    {
        "attraction",
        "viewpoint",
        "museum",
        "theme_park",
        "hotel",
        "guest_house",
        "picnic_site",
    }
)
_HOTSPOT_AMENITY = frozenset({"restaurant", "cafe", "fast_food", "bar"})
_ECO_SURFACES = frozenset(
    {
        "ground",
        "dirt",
        "grass",
        "gravel",
        "pebblestone",
        "rock",
        "sand",
        "unpaved",
        "compacted",
        "fine_gravel",
    }
)
_HIGH_IMPACT_SURFACES = frozenset({"asphalt", "paved", "concrete", "paving_stones"})

_DIFFICULTY_DURATION_HOURS = {
    "easy": 2.0,
    "moderate": 3.5,
    "hard": 5.0,
    "expert": 7.0,
    "unknown": 3.0,
}

_DIFFICULTY_LABEL_EL = {
    "easy": "Εύκολη",
    "moderate": "Μέτρια",
    "hard": "Δύσκολη",
    "expert": "Εξπερτ",
    "unknown": "Μη καταχωρημένη",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def _is_tourist_hotspot(poi: dict[str, Any]) -> bool:
    cat = (poi.get("category") or "").lower()
    tourism = (poi.get("tourism") or "").lower()
    amenity = (poi.get("amenity") or "").lower()
    if cat in _HOTSPOT_TOURISM or tourism in _HOTSPOT_TOURISM:
        return True
    if cat in _HOTSPOT_AMENITY or amenity in _HOTSPOT_AMENITY:
        return True
    if cat in ("archaeological_site", "information") or poi.get("historic"):
        return True
    return False


def calculate_sustainability_score(trail_data: dict[str, Any]) -> dict[str, Any]:
    """
    Score 0–100 for crowd avoidance (50 pts) and low environmental impact (50 pts).
    trail_data: {trail, pois?, biodiversity?, conditions?, route?, elevation_m?}
    """
    trail = trail_data.get("trail") or trail_data
    pois = trail_data.get("pois") or []
    biodiversity = trail_data.get("biodiversity") or {}
    conditions = trail_data.get("conditions") or {}
    tags = trail.get("tags") or {}

    trail_lat = trail.get("lat")
    trail_lon = trail.get("lon")

    # ── Crowd avoidance (max 50) ─────────────────────────────────────────────
    hotspot_penalty = 0.0
    if trail_lat is not None and trail_lon is not None:
        for poi in pois:
            if not _is_tourist_hotspot(poi):
                continue
            plat, plon = poi.get("lat"), poi.get("lon")
            if plat is None or plon is None:
                continue
            dist_km = _haversine_km(float(trail_lat), float(trail_lon), float(plat), float(plon))
            if dist_km <= 5.0:
                proximity = max(0.0, 1.0 - dist_km / 5.0)
                hotspot_penalty += 6.0 * proximity

    crowd_score = max(0.0, min(50.0, 50.0 - hotspot_penalty))

    # ── Nature impact / protection (max 50) ────────────────────────────────────
    impact_score = 25.0
    surface = (trail.get("surface") or tags.get("surface") or "").lower()
    if surface in _ECO_SURFACES:
        impact_score += 12.0
    elif surface in _HIGH_IMPACT_SURFACES:
        impact_score -= 10.0
    elif surface:
        impact_score += 4.0

    visibility = (trail.get("trail_visibility") or tags.get("trail_visibility") or "").lower()
    if visibility in ("excellent", "good"):
        impact_score += 4.0
    elif visibility in ("bad", "horrible"):
        impact_score -= 5.0

    access = (trail.get("access") or tags.get("access") or "").lower()
    if access in ("private", "no"):
        impact_score -= 15.0
    elif access in ("permissive", "yes", "public"):
        impact_score += 3.0

    if tags.get("boundary") or tags.get("protect_class"):
        impact_score += 8.0

    closures = conditions.get("closures") or []
    if trail_lat is not None and trail_lon is not None:
        for item in closures:
            clat, clon = item.get("lat"), item.get("lon")
            if clat is None or clon is None:
                continue
            if _haversine_km(float(trail_lat), float(trail_lon), float(clat), float(clon)) < 2.0:
                impact_score -= 6.0
                break

    obs_count = len(biodiversity.get("observations") or [])
    total_bio = biodiversity.get("total_results") or obs_count
    if total_bio > 80:
        impact_score -= 6.0
    elif 5 <= total_bio <= 40:
        impact_score += 5.0

    difficulty = trail.get("difficulty") or "unknown"
    if difficulty in ("moderate", "hard"):
        impact_score += 3.0

    impact_score = max(0.0, min(50.0, impact_score))

    total = int(round(crowd_score + impact_score))
    total = max(0, min(100, total))

    if total >= 80:
        label = "Excellent"
    elif total >= 65:
        label = "Good"
    elif total >= 50:
        label = "Moderate"
    else:
        label = "Low"

    return {
        "score": total,
        "crowd_score": round(crowd_score, 1),
        "impact_score": round(impact_score, 1),
        "label": label,
        "factors": {
            "crowd_avoidance": "Away from tourist hotspots"
            if crowd_score >= 35
            else "Near busy tourist areas",
            "nature_impact": "Lower environmental impact"
            if impact_score >= 35
            else "Higher environmental impact",
        },
    }


def _parse_length_km(trail: dict[str, Any]) -> float | None:
    raw = trail.get("length_km")
    if raw is None:
        return None
    try:
        val = float(str(raw).replace("km", "").strip())
        return val if val > 0 else None
    except (TypeError, ValueError):
        return None


def estimate_trail_duration(
    trail: dict[str, Any],
    route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estimate hiking duration (Naismith-style or ORS route)."""
    if route and route.get("ok") and route.get("duration_s"):
        seconds = int(route["duration_s"])
        hours, rem = divmod(seconds, 3600)
        minutes = rem // 60
        return {
            "hours": hours + minutes / 60,
            "label": f"{hours}ω {minutes}λ" if hours else f"{minutes} λεπτά",
            "source": "openrouteservice",
        }

    length_km = _parse_length_km(trail)
    difficulty = trail.get("difficulty") or "unknown"
    if length_km:
        hours = length_km / 4.0 + 0.5
    else:
        hours = _DIFFICULTY_DURATION_HOURS.get(difficulty, 3.0)

    total_min = int(hours * 60)
    h, m = divmod(total_min, 60)
    return {
        "hours": hours,
        "label": f"{h}ω {m}λ" if h else f"{m} λεπτά",
        "source": "estimate",
    }


def describe_trail_terrain(
    trail: dict[str, Any],
    elevation: dict[str, Any] | None = None,
) -> str:
    """Human-readable terrain from OSM surface / SAC / elevation."""
    parts: list[str] = []
    surface = trail.get("surface")
    if surface:
        parts.append(surface.replace("_", " ").title())
    sac = trail.get("sac_scale")
    if sac:
        parts.append(f"SAC {sac.replace('_', ' ')}")
    track = trail.get("tracktype")
    if track:
        parts.append(f"Track: {track}")
    if elevation and elevation.get("ok"):
        parts.append(f"~{elevation.get('elevation_m')} m υψ.")
    if not parts:
        diff = trail.get("difficulty") or "unknown"
        defaults = {
            "easy": "Ήπιο μονοπάτι / πεδιάδα",
            "moderate": "Ορεινό μονοπάτι",
            "hard": "Ανωφερές / βραχώδες",
            "expert": "Αλπικό / απαιτητικό",
            "unknown": "Ποικίλο έδαφος",
        }
        return defaults.get(diff, "Ποικίλο έδαφος")
    return " · ".join(parts)


def enrich_trail_recommendation(
    trail: dict[str, Any],
    *,
    pois: list[dict[str, Any]],
    biodiversity: dict[str, Any],
    conditions: dict[str, Any],
    route: dict[str, Any] | None,
    elevation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach display fields and sustainability score to a trail."""
    score_payload = calculate_sustainability_score(
        {
            "trail": trail,
            "pois": pois,
            "biodiversity": biodiversity,
            "conditions": conditions,
            "route": route,
        }
    )
    duration = estimate_trail_duration(trail, route)
    difficulty = trail.get("difficulty") or "unknown"
    return {
        **trail,
        "difficulty_label": _DIFFICULTY_LABEL_EL.get(difficulty, difficulty),
        "duration": duration,
        "terrain": describe_trail_terrain(trail, elevation),
        "sustainability": score_payload,
    }


def build_recommended_trails(
    context: dict[str, Any],
    *,
    max_trails: int = 3,
) -> list[dict[str, Any]]:
    """Rank trails by sustainability score for UI cards."""
    tools = context.get("tools") or {}
    trails_block = tools.get("get_trails_overpass") or {}
    trails = list(trails_block.get("trails") or [])
    if not trails:
        return []

    pois = trails_block.get("pois") or []
    biodiversity = tools.get("get_biodiversity") or {}
    conditions = tools.get("get_real_time_conditions") or {}
    route = tools.get("get_route")
    elevation = tools.get("get_elevation")

    enriched: list[dict[str, Any]] = []
    for trail in trails:
        if not trail.get("name"):
            continue
        use_route = route if enriched == [] and route and route.get("ok") else None
        card = enrich_trail_recommendation(
            trail,
            pois=pois,
            biodiversity=biodiversity,
            conditions=conditions,
            route=use_route,
            elevation=elevation,
        )
        enriched.append(card)

    enriched.sort(
        key=lambda t: t.get("sustainability", {}).get("score", 0),
        reverse=True,
    )
    return enriched[:max_trails]


# ── Backward-compatible wrapper ────────────────────────────────────────────────


def get_trails(
    bbox_or_location: Union[str, dict[str, float], tuple[float, float]],
    difficulty: str | None = None,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    """Wrapper: resolves location → bbox → get_trails_overpass (+ difficulty filter)."""
    bbox = resolve_bbox_or_location(bbox_or_location)
    if not bbox:
        return {
            "ok": False,
            "error": "Could not resolve location or bounding box.",
            "trails": [],
        }

    result = get_trails_overpass(bbox, limit_trails=limit)
    if not result.get("ok"):
        return {**result, "trails": [], "difficulty_filter": None}

    target = _normalize_difficulty(difficulty)
    trails = result.get("trails") or []
    if target:
        trails = [t for t in trails if t.get("difficulty") in (target, "unknown")]

    return {
        "ok": True,
        "bbox": bbox,
        "count": len(trails),
        "difficulty_filter": target,
        "trails": trails,
        "pois": result.get("pois", []),
    }


# ── AI orchestration ───────────────────────────────────────────────────────────


def run_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    """Dispatch a single Pathfinder tool by name (for AI agents)."""
    dispatch: dict[str, Callable[..., dict[str, Any]]] = {
        "get_weather": get_weather,
        "get_trails_overpass": get_trails_overpass,
        "get_route": get_route,
        "get_biodiversity": get_biodiversity,
        "get_elevation": get_elevation,
        "get_real_time_conditions": get_real_time_conditions,
        "get_trails": get_trails,
        "calculate_sustainability_score": calculate_sustainability_score,
    }
    fn = dispatch.get(name)
    if not fn:
        return {"ok": False, "error": f"Unknown tool: {name}"}
    return fn(**kwargs)


def build_itinerary_context(
    location: str,
    *,
    difficulty: str | None = None,
    end_coords: Union[str, dict[str, float], tuple[float, float], list[float], None] = None,
    biodiversity_radius_km: float = 5.0,
) -> dict[str, Any]:
    """
    Aggregate all Deloitte APIs for sustainable itinerary generation by the AI.
    """
    resolved = resolve_location(location)
    if not resolved:
        return {"ok": False, "error": f"Unknown location: {location}"}

    lat, lon = resolved["lat"], resolved["lon"]
    bbox = resolved.get("bbox") or _bbox_around_point(lat, lon, 12.0)

    trails_data = get_trails_overpass(bbox)
    trails = trails_data.get("trails") or []
    target = _normalize_difficulty(difficulty)
    if target:
        trails = [t for t in trails if t.get("difficulty") in (target, "unknown")]

    route: dict[str, Any] | None = None
    if end_coords:
        route = get_route((lat, lon), end_coords)
    elif trails:
        first = next((t for t in trails if t.get("lat") and t.get("lon")), None)
        if first:
            route = get_route((lat, lon), (first["lat"], first["lon"]))

    tools_used = {
        "get_weather": get_weather(lat, lon),
        "get_trails_overpass": {**trails_data, "trails": trails[:25]},
        "get_elevation": get_elevation(lat, lon),
        "get_biodiversity": get_biodiversity(lat, lon, radius_km=biodiversity_radius_km),
        "get_real_time_conditions": get_real_time_conditions(resolved),
        "get_route": route,
    }

    draft_context = {
        "ok": True,
        "location": resolved,
        "difficulty_filter": target,
        "tools": tools_used,
    }
    recommended = build_recommended_trails(draft_context, max_trails=3)

    return {
        **draft_context,
        "recommended_trails": recommended,
        "tool_catalog": PATHFINDER_TOOLS,
        "sustainability_guidelines": [
            "Leave No Trace: pack out all waste.",
            "Stay on marked trails; respect closed sections.",
            "Keep distance from wildlife; iNaturalist sightings are for observation only.",
            "Check weather and elevation before long ascents.",
            "Prefer existing OSM trails over off-trail shortcuts.",
        ],
    }


def build_trail_context(
    location: str,
    *,
    difficulty: str | None = None,
) -> dict[str, Any]:
    """Alias for build_itinerary_context (backward compatible)."""
    return build_itinerary_context(location, difficulty=difficulty)
