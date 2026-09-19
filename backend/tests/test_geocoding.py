"""Tests for location resolution and the on-disk cache.

No test touches the network: every geocoder call goes through an injected
fake transport. The fixtures deliberately span several countries and both
hemispheres so nothing can quietly become city-specific.
"""
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from realdata.cache import (
    DiskCache,
    SOURCE_CACHE,
    SOURCE_CACHE_STALE,
    SOURCE_NETWORK,
    canonical_key,
)
from realdata.geocoding import (
    BoundingBox,
    GeocodingError,
    MAX_RADIUS_M,
    MIN_RADIUS_M,
    ResolvedLocation,
    clamp_radius,
    geocode_place,
    resolve_location,
)

# Recorded Nominatim-shaped responses. These are test fixtures, nothing in the
# implementation knows about any of these places.
FIXTURES = {
    "lucknow": {"lat": "26.8466937", "lon": "80.946166", "display_name": "Lucknow, Uttar Pradesh, India"},
    "delhi": {"lat": "28.6138954", "lon": "77.2090057", "display_name": "Delhi, India"},
    "noida": {"lat": "28.5707979", "lon": "77.3260135", "display_name": "Noida, Uttar Pradesh, India"},
    "mumbai": {"lat": "19.0759899", "lon": "72.8773928", "display_name": "Mumbai, Maharashtra, India"},
    "pune": {"lat": "18.5213738", "lon": "73.8545071", "display_name": "Pune, Maharashtra, India"},
    "bengaluru": {"lat": "12.9767936", "lon": "77.590082", "display_name": "Bengaluru, Karnataka, India"},
    "hyderabad": {"lat": "17.360589", "lon": "78.4740613", "display_name": "Hyderabad, Telangana, India"},
    "patna": {"lat": "25.6093239", "lon": "85.1235252", "display_name": "Patna, Bihar, India"},
    "kolkata": {"lat": "22.5726459", "lon": "88.3638953", "display_name": "Kolkata, West Bengal, India"},
    "london": {"lat": "51.4893335", "lon": "-0.1440551", "display_name": "London, England, UK"},
    "new york": {"lat": "40.7127281", "lon": "-74.0060152", "display_name": "New York, United States"},
    "buenos aires": {"lat": "-34.6075682", "lon": "-58.4370894", "display_name": "Buenos Aires, Argentina"},
}


class FakeTransport:
    """Stands in for the HTTP layer. Records calls so tests can assert that
    the network was (or was not) used."""

    def __init__(self, responses=None, fail=False):
        self.responses = responses if responses is not None else FIXTURES
        self.fail = fail
        self.calls = []

    def __call__(self, url, params, timeout_s):
        self.calls.append({"url": url, "params": params, "timeout": timeout_s})
        if self.fail:
            raise ConnectionError("simulated network failure")
        hit = self.responses.get(str(params["q"]).strip().lower())
        return [hit] if hit else []


@pytest.fixture
def cache(tmp_path):
    return DiskCache(root=tmp_path / "cache")


# ================================================================== bbox

@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_place_resolves_through_the_same_code_path(name, cache):
    """The point of the parametrisation: twelve very different places, one
    implementation, no branching on which city it is."""
    transport = FakeTransport()
    loc = geocode_place(name, radius_m=3000, cache=cache, fetch_json=transport)

    assert loc.query == name
    assert loc.latitude == pytest.approx(float(FIXTURES[name]["lat"]))
    assert loc.longitude == pytest.approx(float(FIXTURES[name]["lon"]))
    assert loc.display_name == FIXTURES[name]["display_name"]
    assert loc.resolver == "nominatim"
    assert loc.provenance == SOURCE_NETWORK
    # The box must actually contain the point it was built around.
    assert loc.bbox.min_lat < loc.latitude < loc.bbox.max_lat
    assert loc.bbox.min_lon < loc.longitude < loc.bbox.max_lon


def test_bbox_from_center_radius_is_centred_and_sized():
    box = BoundingBox.from_center_radius(26.8466937, 80.946166, 3000.0)
    center_lat, center_lon = box.center

    assert center_lat == pytest.approx(26.8466937, abs=1e-9)
    assert center_lon == pytest.approx(80.946166, abs=1e-9)
    # ~3 km north-south either side => ~0.0269 degrees of latitude.
    assert (box.max_lat - box.min_lat) / 2 == pytest.approx(3000 / 111320.0, rel=1e-6)


def test_longitude_span_widens_with_latitude():
    """A 3 km box is wider in degrees of longitude near the poles than at the
    equator. Getting this wrong would silently shrink northern extracts."""
    near_equator = BoundingBox.from_center_radius(1.0, 0.0, 3000.0)
    high_latitude = BoundingBox.from_center_radius(60.0, 0.0, 3000.0)

    equator_span = near_equator.max_lon - near_equator.min_lon
    high_span = high_latitude.max_lon - high_latitude.min_lon

    assert high_span > equator_span * 1.9
    # Latitude span is the same everywhere.
    assert (high_latitude.max_lat - high_latitude.min_lat) == pytest.approx(
        near_equator.max_lat - near_equator.min_lat)


def test_southern_hemisphere_and_negative_longitude_are_handled(cache):
    transport = FakeTransport()
    loc = geocode_place("buenos aires", radius_m=2000, cache=cache, fetch_json=transport)

    assert loc.latitude < 0 and loc.longitude < 0
    assert loc.bbox.min_lat < loc.latitude < loc.bbox.max_lat
    assert loc.bbox.min_lon < loc.longitude < loc.bbox.max_lon


def test_overpass_bbox_is_south_west_north_east():
    box = BoundingBox(min_lat=1.0, min_lon=2.0, max_lat=3.0, max_lon=4.0)
    assert box.to_overpass_bbox() == "1.0,2.0,3.0,4.0"


# ================================================================ radius

def test_radius_is_clamped_to_a_bounded_area():
    assert clamp_radius(None) == 3000.0
    assert clamp_radius(50) == MIN_RADIUS_M
    assert clamp_radius(10_000_000) == MAX_RADIUS_M
    assert clamp_radius(4200) == 4200.0


def test_configurable_area_size_changes_the_box(cache):
    transport = FakeTransport()
    small = geocode_place("pune", radius_m=1000, cache=cache, fetch_json=transport)
    large = geocode_place("pune", radius_m=8000, cache=cache, fetch_json=transport)

    small_span = small.bbox.max_lat - small.bbox.min_lat
    large_span = large.bbox.max_lat - large.bbox.min_lat
    assert large_span == pytest.approx(small_span * 8, rel=1e-6)


# ========================================================= input modes

def test_explicit_coordinates_need_no_network():
    transport = FakeTransport()
    loc = resolve_location(latitude=26.85, longitude=80.95, radius_m=2500,
                           fetch_json=transport)

    assert transport.calls == [], "coordinates must not trigger a geocode"
    assert loc.resolver == "coordinates"
    assert loc.provenance == "explicit"
    assert loc.latitude == 26.85


def test_explicit_bbox_needs_no_network():
    transport = FakeTransport()
    loc = resolve_location(bbox=(26.8, 80.9, 26.9, 81.0), fetch_json=transport)

    assert transport.calls == []
    assert loc.resolver == "bbox"
    assert loc.bbox.min_lat == 26.8 and loc.bbox.max_lon == 81.0
    assert loc.latitude == pytest.approx(26.85)


def test_bbox_takes_precedence_over_place(cache):
    transport = FakeTransport()
    loc = resolve_location(place="london", bbox=(1.0, 2.0, 3.0, 4.0),
                           cache=cache, fetch_json=transport)

    assert transport.calls == []
    assert loc.resolver == "bbox"
    assert loc.query == "london"  # the label is kept for display


def test_place_name_goes_through_the_geocoder(cache):
    transport = FakeTransport()
    loc = resolve_location(place="kolkata", radius_m=3000,
                           cache=cache, fetch_json=transport)

    assert len(transport.calls) == 1
    assert transport.calls[0]["params"]["q"] == "kolkata"
    assert loc.resolver == "nominatim"


def test_invalid_inputs_are_rejected():
    with pytest.raises(GeocodingError):
        resolve_location()
    with pytest.raises(GeocodingError):
        resolve_location(place="   ")
    with pytest.raises(GeocodingError):
        resolve_location(latitude=200.0, longitude=0.0)
    with pytest.raises(GeocodingError):
        resolve_location(bbox=(5.0, 2.0, 1.0, 4.0))


def test_unknown_place_raises(cache):
    transport = FakeTransport(responses={})
    with pytest.raises(GeocodingError, match="No location found"):
        geocode_place("nowhere-at-all", cache=cache, fetch_json=transport)


# ================================================================ caching

def test_second_lookup_is_served_from_cache(cache):
    transport = FakeTransport()

    first = geocode_place("hyderabad", cache=cache, fetch_json=transport)
    second = geocode_place("hyderabad", cache=cache, fetch_json=transport)

    assert len(transport.calls) == 1, "the second lookup must not hit the network"
    assert first.provenance == SOURCE_NETWORK
    assert second.provenance == SOURCE_CACHE
    assert second.latitude == first.latitude


def test_cache_lookup_is_case_insensitive(cache):
    transport = FakeTransport()
    geocode_place("Patna", cache=cache, fetch_json=transport)
    again = geocode_place("  patna  ", cache=cache, fetch_json=transport)

    assert len(transport.calls) == 1
    assert again.provenance == SOURCE_CACHE


def test_offline_falls_back_to_cache_and_says_so(cache):
    """The demo must survive a dead network - but it must never claim the
    stale answer was freshly fetched."""
    geocode_place("mumbai", cache=cache, fetch_json=FakeTransport())

    # Force the entry past its TTL, then take the network away.
    key = {"provider": "nominatim", "q": "mumbai"}
    path = cache.path_for("geocoding", key)
    raw = json.loads(path.read_text())
    raw["cached_at"] = time.time() - (400 * 24 * 60 * 60)
    path.write_text(json.dumps(raw))

    offline = FakeTransport(fail=True)
    loc = geocode_place("mumbai", cache=cache, fetch_json=offline)

    assert loc.provenance == SOURCE_CACHE_STALE
    assert loc.provenance != SOURCE_NETWORK
    assert loc.latitude == pytest.approx(19.0759899)


def test_offline_with_no_cache_raises(cache):
    with pytest.raises(GeocodingError, match="no cached result"):
        geocode_place("delhi", cache=cache, fetch_json=FakeTransport(fail=True))


# ========================================================== disk cache

def test_canonical_key_is_order_independent():
    assert canonical_key({"a": 1, "b": 2}) == canonical_key({"b": 2, "a": 1})
    assert canonical_key({"a": 1}) != canonical_key({"a": 2})


def test_cache_roundtrip_and_namespacing(cache):
    cache.set("osm", {"bbox": "1,2,3,4"}, {"nodes": 5})
    cache.set("weather", {"lat": 1.0}, {"temp": 30.0})

    assert cache.get("osm", {"bbox": "1,2,3,4"}).payload == {"nodes": 5}
    assert cache.get("weather", {"lat": 1.0}).payload == {"temp": 30.0}
    assert cache.get("osm", {"bbox": "9,9,9,9"}) is None

    assert cache.entries("osm") == 1
    cache.clear("osm")
    assert cache.entries("osm") == 0
    assert cache.entries("weather") == 1


def test_corrupt_cache_entry_is_ignored_not_fatal(cache):
    key = {"q": "anything"}
    path = cache.path_for("geocoding", key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not json")

    assert cache.get("geocoding", key) is None


def test_cache_entry_reports_staleness(cache):
    cache.set("osm", {"k": 1}, {"v": 2})
    entry = cache.get("osm", {"k": 1})

    assert entry.age_seconds < 5
    assert not entry.is_stale(ttl_seconds=3600)
    assert entry.is_stale(ttl_seconds=0.0001) or entry.age_seconds <= 0.0001


def test_cache_root_is_configurable(tmp_path):
    custom = DiskCache(root=tmp_path / "somewhere-else")
    custom.set("osm", {"a": 1}, {"b": 2})
    assert (tmp_path / "somewhere-else" / "osm").exists()


# ================================================ no hardcoded locations

def _executable_strings(module):
    """String literals that are actually code, with docstrings excluded.

    Checking raw text would flag the module docstring, which legitimately
    names a few places as examples. What must not exist is a place name in
    *executable* code, or a lookup table of coordinates.
    """
    import ast

    source = open(module.__file__, encoding="utf-8").read()
    tree = ast.parse(source)

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)

    return tree, [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    ]


@pytest.mark.parametrize("module_name", ["realdata.geocoding", "realdata.cache"])
def test_implementation_has_no_place_names_in_code(module_name):
    """Guard against a city-to-coordinate dictionary creeping back in."""
    import importlib

    module = importlib.import_module(module_name)
    _, strings = _executable_strings(module)
    blob = " ".join(strings).lower()

    for city in ("lucknow", "bengaluru", "mumbai", "hyderabad", "kolkata",
                 "patna", "delhi", "noida", "pune", "london", "new york"):
        assert city not in blob, f"'{city}' must not appear in executable code"


def test_implementation_has_no_coordinate_lookup_table():
    """No dict literal may map several string keys to numeric values - that
    is what a hardcoded city table looks like."""
    import ast
    import realdata.geocoding as geocoding_module

    tree, _ = _executable_strings(geocoding_module)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        string_keys = sum(
            1 for k in node.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        )
        numeric_values = sum(
            1 for v in node.values
            if isinstance(v, (ast.Tuple, ast.List))
            or (isinstance(v, ast.Constant) and isinstance(v.value, (int, float)))
        )
        assert not (string_keys >= 3 and numeric_values >= 3), (
            "a dict mapping names to coordinates looks like a hardcoded "
            "city table; resolve places through the geocoder instead"
        )


def test_resolved_location_serialises_with_full_provenance(cache):
    loc = geocode_place("london", radius_m=3000, cache=cache, fetch_json=FakeTransport())
    body = loc.to_dict()

    assert body["location"]["query"] == "london"
    assert body["location"]["provenance"] == SOURCE_NETWORK
    assert body["location"]["resolver"] == "nominatim"
    assert set(body["bbox"]) == {"min_lat", "min_lon", "max_lat", "max_lon"}
    assert body["radius_m"] == 3000.0
    assert body["retrieved_at"].endswith("+00:00")
