# map_servers/osm_server.py

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests
from agents import function_tool

from .base import ServerParams

logger = logging.getLogger(__name__)

USER_AGENT = "map-agents-assignment/1.0 (student-project)"
NOMINATIM_PARAMS = ServerParams(
    name="osm_nominatim",
    base_url="https://nominatim.openstreetmap.org",
    description="OpenStreetMap Nominatim geocoding service.",
    commands={
        "geocode": "/search",
        "reverse_geocode": "/reverse",
    },
)

OVERPASS_PARAMS = ServerParams(
    name="osm_overpass",
    base_url="https://overpass-api.de/api",
    description="Overpass API for querying OpenStreetMap POI data.",
    commands={
        "search_poi": "/interpreter",
    },
)


def _nominatim_headers() -> Dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }


# ------------------------
# Pure implementation APIs
# ------------------------

def osm_geocode_impl(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Forward geocoding using OpenStreetMap Nominatim.

    Args:
        query: Free-text address or place name, e.g. "Berlin, Germany".
        limit: Maximum number of results to return (1-10).

    Returns:
        A list of geocoding results, each with:
        - lat, lon (floats)
        - display_name (string)
        - type (OSM feature type)
        - importance (float score)
    """
    limit = max(1, min(limit, 10))

    url = NOMINATIM_PARAMS.base_url + NOMINATIM_PARAMS.commands["geocode"]
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": limit,
        "addressdetails": 1,
    }

    logger.debug("Calling Nominatim search: %s %s", url, params)
    resp = requests.get(url, params=params, headers=_nominatim_headers(), timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results: List[Dict[str, Any]] = []
    for item in data:
        try:
            results.append(
                {
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                    "display_name": item.get("display_name"),
                    "type": item.get("type"),
                    "importance": item.get("importance"),
                }
            )
        except (KeyError, ValueError, TypeError):
            logger.exception("Failed to parse Nominatim result item: %s", item)

    return results


def osm_reverse_geocode_impl(lat: float, lon: float, zoom: int = 18) -> Dict[str, Any]:
    """
    Reverse geocoding using OpenStreetMap Nominatim.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        zoom: Detail level (3=country, 18=building). 16+ focuses on road/house.

    Returns:
        A dict with:
        - lat, lon
        - display_name
        - address (structured address dict if available)
    """
    zoom = max(3, min(zoom, 18))

    url = NOMINATIM_PARAMS.base_url + NOMINATIM_PARAMS.commands["reverse_geocode"]
    params = {
        "lat": lat,
        "lon": lon,
        "zoom": zoom,
        "format": "jsonv2",
        "addressdetails": 1,
    }

    logger.debug("Calling Nominatim reverse: %s %s", url, params)
    resp = requests.get(url, params=params, headers=_nominatim_headers(), timeout=10)
    resp.raise_for_status()
    data = resp.json()

    return {
        "lat": float(data.get("lat", lat)),
        "lon": float(data.get("lon", lon)),
        "display_name": data.get("display_name"),
        "address": data.get("address", {}),
    }


def osm_search_poi_impl(
    lat: float,
    lon: float,
    radius_m: int = 500,
    key: str = "amenity",
    value: str = "restaurant",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search points of interest (POI) around a coordinate using Overpass API.

    Args:
        lat: Center latitude in decimal degrees.
        lon: Center longitude in decimal degrees.
        radius_m: Search radius in meters.
        key: OSM tag key, e.g. "amenity".
        value: OSM tag value, e.g. "restaurant".
        limit: Max number of POIs to return.

    Returns:
        A list of POIs with:
        - id
        - osm_type (node/way/relation)
        - lat, lon
        - tags (raw OSM tags dict)
    """
    radius_m = max(50, min(radius_m, 5000))
    limit = max(1, min(limit, 50))

    # Overpass QL query using `around` filter.
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node["{key}"="{value}"](around:{radius_m},{lat},{lon});
      way["{key}"="{value}"](around:{radius_m},{lat},{lon});
      relation["{key}"="{value}"](around:{radius_m},{lat},{lon});
    );
    out center {limit};
    """

    url = OVERPASS_PARAMS.base_url + OVERPASS_PARAMS.commands["search_poi"]
    logger.debug("Calling Overpass API: %s", url)

    resp = requests.post(
        url,
        data={"data": overpass_query},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    elements = data.get("elements", [])[:limit]

    results: List[Dict[str, Any]] = []
    for el in elements:
        el_type = el.get("type")
        lat_el = None
        lon_el = None

        if "lat" in el and "lon" in el:
            lat_el = el["lat"]
            lon_el = el["lon"]
        elif "center" in el and isinstance(el["center"], dict):
            lat_el = el["center"].get("lat")
            lon_el = el["center"].get("lon")

        if lat_el is None or lon_el is None:
            continue

        results.append(
            {
                "id": el.get("id"),
                "osm_type": el_type,
                "lat": float(lat_el),
                "lon": float(lon_el),
                "tags": el.get("tags", {}),
            }
        )

    return results


# ------------------------
# Tool-wrapped APIs
# ------------------------

@function_tool
def osm_geocode(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Tool wrapper for osm_geocode_impl."""
    return osm_geocode_impl(query=query, limit=limit)


@function_tool
def osm_reverse_geocode(lat: float, lon: float, zoom: int = 18) -> Dict[str, Any]:
    """Tool wrapper for osm_reverse_geocode_impl."""
    return osm_reverse_geocode_impl(lat=lat, lon=lon, zoom=zoom)


@function_tool
def osm_search_poi(
    lat: float,
    lon: float,
    radius_m: int = 500,
    key: str = "amenity",
    value: str = "restaurant",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Tool wrapper for osm_search_poi_impl."""
    return osm_search_poi_impl(
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        key=key,
        value=value,
        limit=limit,
    )
