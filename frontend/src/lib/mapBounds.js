// Pure geographic-bounds helpers for the network map's viewport.
//
// Nothing here talks to Leaflet directly - it only works with plain
// [lat, lng] pairs and plain {minLat,maxLat,minLng,maxLng} boxes. That keeps
// the "what area should the map show" question testable and reviewable on
// its own, separate from the React/Leaflet lifecycle that consumes it.
//
// The one job this module has: given whatever real coordinates the active
// scenario currently has, compute a geographic box that actually contains
// them - never a fixed city, never a fixed zoom, never all of India when a
// scenario covers three streets in one neighbourhood.

// A point is only usable if it is a finite number inside the range real
// latitude/longitude values can take. Anything else (null, undefined, NaN,
// a swapped/garbage value from a bad upstream record) is dropped rather
// than silently coerced into 0 or fed into a bounding-box calculation that
// would then quietly cover half the globe.
export function isValidLatLng(lat, lng) {
  return (
    typeof lat === 'number' && Number.isFinite(lat) &&
    typeof lng === 'number' && Number.isFinite(lng) &&
    lat >= -90 && lat <= 90 &&
    lng >= -180 && lng <= 180
  );
}

// Accepts an array of [lat, lng] pairs (or {lat, lng} objects) and returns
// the tight bounding box around the valid ones, or null if none were valid.
// Invalid points are skipped, not zeroed - one bad record must never drag
// the box out to null island or across the equator.
export function computeBounds(points) {
  let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
  let count = 0;

  for (const p of points) {
    const lat = Array.isArray(p) ? p[0] : p?.lat;
    const lng = Array.isArray(p) ? p[1] : p?.lng;
    if (!isValidLatLng(lat, lng)) continue;
    count += 1;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
  }

  if (count === 0) return null;
  return { minLat, maxLat, minLng, maxLng };
}

// Merge any number of boxes (nulls are ignored) into one box that contains
// them all. Used to combine "the jobs and depot" with "the route geometry
// actually drawn", so a road that bulges outside the straight depot-to-stop
// box is still fully on screen after optimization.
export function mergeBounds(...boxes) {
  const valid = boxes.filter(Boolean);
  if (valid.length === 0) return null;
  return valid.reduce((acc, b) => ({
    minLat: Math.min(acc.minLat, b.minLat),
    maxLat: Math.max(acc.maxLat, b.maxLat),
    minLng: Math.min(acc.minLng, b.minLng),
    maxLng: Math.max(acc.maxLng, b.maxLng)
  }));
}

// A route's real OSM geometry is drawn straight from each edge's own way
// shape (see route_geometry.py), which is a lookup, not a computation - it
// legitimately reflects the actual road. But a way that only clips the
// corner of the network's query area is still returned by Overpass with its
// COMPLETE geometry, endpoint to endpoint, however far outside that area
// the rest of the way runs (a long highway is the common case). If the
// optimizer's route ever uses such a hop, that one edge's geometry can carry
// the auto-fit viewport out to wherever the real road happens to keep
// going - up to a national-highway's whole length away from the depot and
// every delivery stop - even though the scenario's own nodes are all
// tightly clustered.
//
// So route/edge geometry is allowed to expand the viewport past the
// scenario's own node bounds (`anchor` - depot + delivery stops, the actual
// selected area) only up to a bounded multiple of the anchor's own size,
// plus a small fixed floor so a genuinely tiny anchor (a dense micro-cluster
// a few metres across) still gets enough room to show a real road's normal
// curve. A road's ordinary bulge is always far under this; only the
// pathological "way exits the requested area entirely" case ever hits the
// cap. Nothing here depends on where the anchor actually is - the same
// factor and floor apply regardless of scenario location.
const ROUTE_BULGE_MAX_FACTOR = 3; // route/edge geometry may extend the
                                   // anchor's own span by up to 3x on a side
const ROUTE_BULGE_MIN_MARGIN_DEG = 0.02; // ~2km floor for a very small anchor

export function clampBoundsToAnchor(bounds, anchor, {
  maxExpansionFactor = ROUTE_BULGE_MAX_FACTOR,
  minMarginDeg = ROUTE_BULGE_MIN_MARGIN_DEG
} = {}) {
  if (!bounds) return null;
  if (!anchor) return bounds; // nothing to clamp against - let it through

  const anchorLatSpan = anchor.maxLat - anchor.minLat;
  const anchorLngSpan = anchor.maxLng - anchor.minLng;
  const latMargin = Math.max(anchorLatSpan * maxExpansionFactor, minMarginDeg);
  const lngMargin = Math.max(anchorLngSpan * maxExpansionFactor, minMarginDeg);

  const [minLat, maxLat] = clampAxis(bounds.minLat, bounds.maxLat, anchor.minLat, anchor.maxLat, latMargin);
  const [minLng, maxLng] = clampAxis(bounds.minLng, bounds.maxLng, anchor.minLng, anchor.maxLng, lngMargin);

  return { minLat, maxLat, minLng, maxLng };
}

// Intersects [boundsMin, boundsMax] with the allowed window
// [anchorMin - margin, anchorMax + margin] on one axis. A plain
// Math.max(min)/Math.min(max) pair can invert (min > max) whenever bounds
// sits entirely outside that window on this axis - e.g. a route whose
// geometry is *all* far from the scenario on this axis, not just bulging
// past one edge of it. That would hand fitBounds/padBoundsIfTooSmall an
// invalid box. So when the intersection would be empty, this falls back to
// the allowed window itself: still bounded to at most `margin` past the
// anchor on each side, still centred on the scenario's own area, and always
// a valid (min <= max) box, since anchorMin <= anchorMax by construction
// and margin >= 0.
function clampAxis(boundsMin, boundsMax, anchorMin, anchorMax, margin) {
  const allowedMin = anchorMin - margin;
  const allowedMax = anchorMax + margin;
  const clampedMin = Math.max(boundsMin, allowedMin);
  const clampedMax = Math.min(boundsMax, allowedMax);
  if (clampedMin > clampedMax) {
    return [allowedMin, allowedMax];
  }
  return [clampedMin, clampedMax];
}

// Every location in this app is real (synthetic-but-simulated, or actual
// OpenStreetMap data) - never literally on top of one another down to the
// centimetre unless the scenario really does put a stop at the depot. But
// "all stops within a few metres of each other" is a real, legitimate
// scenario shape (a dense micro-delivery cluster), and Leaflet's fitBounds
// on a near-zero-area box will happily zoom in to its maxZoom, which for a
// building-scale box means a nonsensical street-level crop. So: pad a too-
// small box out to a minimum span *before* handing it to fitBounds, and
// separately cap the zoom fitBounds is allowed to reach (see
// DEFAULT_FIT_OPTIONS below) - two independent guards against "zoomed into
// a single point", not one.
const MIN_SPAN_DEG = 0.006; // ~650m north-south at the equator - a small
                             // neighbourhood block, not a building.

export function padBoundsIfTooSmall(bounds, minSpanDeg = MIN_SPAN_DEG) {
  if (!bounds) return null;
  const { minLat, maxLat, minLng, maxLng } = bounds;
  const latSpan = maxLat - minLat;
  const lngSpan = maxLng - minLng;
  const latPad = latSpan < minSpanDeg ? (minSpanDeg - latSpan) / 2 : 0;
  const lngPad = lngSpan < minSpanDeg ? (minSpanDeg - lngSpan) / 2 : 0;
  return {
    minLat: minLat - latPad,
    maxLat: maxLat + latPad,
    minLng: minLng - lngPad,
    maxLng: maxLng + lngPad
  };
}

// Rough, Leaflet-independent zoom guess from a bounding box's span, used
// only to pick a reasonable *initial* MapContainer zoom before the map
// instance exists (so the very first paint is already close to right,
// instead of a fixed zoom=12 that is wrong for anything that isn't ~10km
// across). The real, precise fit still happens through Leaflet's own
// fitBounds once the map is mounted - this is a one-frame approximation,
// not the primary viewport strategy.
const ZOOM_BY_SPAN_DEG = [
  [20, 5], [8, 6], [4, 7], [2, 8], [1, 9],
  [0.5, 10], [0.25, 11], [0.12, 12], [0.06, 13],
  [0.03, 14], [0.012, 15], [0, 16]
];

export function estimateInitialZoom(bounds) {
  if (!bounds) return 12;
  const span = Math.max(bounds.maxLat - bounds.minLat, bounds.maxLng - bounds.minLng);
  for (const [threshold, zoom] of ZOOM_BY_SPAN_DEG) {
    if (span >= threshold) return zoom;
  }
  return 16;
}

export function boundsCenter(bounds) {
  if (!bounds) return null;
  return [(bounds.minLat + bounds.maxLat) / 2, (bounds.minLng + bounds.maxLng) / 2];
}

// Leaflet's own bounds type as a plain [[southWest], [northEast]] tuple -
// every react-leaflet fitBounds/flyToBounds call accepts this shape
// directly, so callers never need to import Leaflet just to build a box.
export function toLeafletBounds(bounds) {
  if (!bounds) return null;
  return [[bounds.minLat, bounds.minLng], [bounds.maxLat, bounds.maxLng]];
}

export const DEFAULT_FIT_OPTIONS = {
  paddingTopLeft: [24, 24],
  paddingBottomRight: [24, 24],
  maxZoom: 16
};
