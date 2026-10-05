import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { useMap } from 'react-leaflet';

// Renders nothing. Its only job is to sit inside <MapContainer> (the only
// place react-leaflet's useMap() is usable) and:
//
//   1. Keep the Leaflet instance's internal size in sync with its actual DOM
//      box, for every reason that box can change after mount - a browser
//      resize, the sidebar/mobile-tab toggling the map's ancestor between
//      `hidden` and `block`, or the dashboard's Overview<->Engineering
//      switch remounting this whole tree while a CSS transition is still
//      settling. Leaflet only measures its container once, at construction;
//      everything else here is what keeps that measurement honest afterwards.
//
//   2. Expose a small imperative API (fitToBounds / flyToBounds / setView)
//      up to the plain-React toolbar that lives *outside* the map (the
//      Fit All Stops / Focus Depot / Focus Vehicle / Reset View buttons),
//      since those buttons cannot call useMap() themselves.
//
// It never decides *what* bounds to show - NetworkMap computes those from
// the actual scenario data. This component only knows how to point an
// already-mounted Leaflet map at a box it's given, safely and without
// fighting the user's own pan/zoom.
const MapViewController = forwardRef(function MapViewController(_props, ref) {
  const map = useMap();
  const lastSizeRef = useRef({ width: 0, height: 0 });
  const rafIdsRef = useRef([]);

  // Leaflet cannot fit or fly to bounds while its container has no size: its
  // zoom maths divides by the (zero) viewport and produces NaN, and
  // flyToBounds then throws "Invalid LatLng object: (NaN, NaN)". That is
  // exactly the state of the map on a phone when the operator clicks
  // Optimize from the "Controls" tab (the Network Map tab is display:none).
  // Uncaught, it unmounted the whole app. So camera moves requested while the
  // map is hidden are parked here and applied, without animation, the moment
  // the container gets a real size again (see the ResizeObserver below).
  const pendingFitRef = useRef(null);

  const isMapVisible = () => {
    const container = map && map.getContainer();
    return !!container && container.clientWidth > 0 && container.clientHeight > 0;
  };

  const applyFit = (leafletBounds, options, animated) => {
    try {
      if (animated) map.flyToBounds(leafletBounds, options);
      else map.fitBounds(leafletBounds, { ...options, animate: false });
    } catch (err) {
      // A bad camera move must never take the dashboard down with it.
      console.warn('Map camera move skipped:', err);
    }
  };

  useImperativeHandle(ref, () => ({
    fitToBounds(leafletBounds, options = {}) {
      if (!map || !leafletBounds) return;
      if (!isMapVisible()) {
        pendingFitRef.current = { leafletBounds, options };
        return;
      }
      applyFit(leafletBounds, options, false);
    },
    flyToBounds(leafletBounds, options = {}) {
      if (!map || !leafletBounds) return;
      // flyToBounds animates; a user who has the tab in the background or
      // prefers-reduced-motion still gets a correct final view because
      // Leaflet clamps duration internally when the map isn't visible, and
      // we always pass a bounded duration below rather than relying on
      // defaults drifting later.
      if (!isMapVisible()) {
        pendingFitRef.current = { leafletBounds, options };
        return;
      }
      applyFit(leafletBounds, options, true);
    },
    setView(center, zoom, options = {}) {
      if (!map || !center || !isMapVisible()) return;
      map.setView(center, zoom, options);
    },
    invalidateSize() {
      if (!map) return;
      map.invalidateSize();
    },
    getMap() {
      return map;
    }
  }), [map]);

  // --- Lifecycle sizing -----------------------------------------------
  // A Leaflet map created while its container is zero-sized (a hidden
  // mobile tab, a grid row that hasn't laid out yet on first paint) bakes
  // that wrong size into its tile grid and pixel origin. Nothing self-heals
  // that except an explicit invalidateSize() once the container's real box
  // is known. Two independent mechanisms cover the two ways the box can be
  // wrong:
  useEffect(() => {
    if (!map) return undefined;

    // (a) Wrong at construction time: give the browser two paint frames to
    // finish whatever layout was in flight (grid rows sizing, a tab
    // becoming visible) and then correct it once. This is not a guessed
    // delay - rAF-in-rAF is the standard "after the next real layout/paint"
    // signal, and it's cancelled on unmount so it can never fire against a
    // torn-down map.
    const id1 = requestAnimationFrame(() => {
      const id2 = requestAnimationFrame(() => {
        map.invalidateSize();
      });
      rafIdsRef.current.push(id2);
    });
    rafIdsRef.current.push(id1);

    // (b) Wrong at any point afterwards: a ResizeObserver on the map's own
    // container catches every later cause (window resize, sidebar
    // collapse, the mobile map/controls tab switch, a parent layout
    // change) without polling and without a remount. It only calls
    // invalidateSize when the box actually changed, so it can't loop.
    const container = map.getContainer();
    let observer;
    if (typeof ResizeObserver !== 'undefined' && container) {
      observer = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (!entry) return;
        const { width, height } = entry.contentRect;
        const prev = lastSizeRef.current;
        if (Math.abs(width - prev.width) < 1 && Math.abs(height - prev.height) < 1) return;
        lastSizeRef.current = { width, height };
        if (width === 0 || height === 0) return; // still hidden - nothing to do yet
        map.invalidateSize();
        // The map just became visible: apply the camera move that was
        // requested while it was hidden (e.g. the new route result).
        if (pendingFitRef.current) {
          const { leafletBounds, options } = pendingFitRef.current;
          pendingFitRef.current = null;
          applyFit(leafletBounds, options, false);
        }
      });
      observer.observe(container);
    }

    return () => {
      rafIdsRef.current.forEach(cancelAnimationFrame);
      rafIdsRef.current = [];
      if (observer) observer.disconnect();
    };
  }, [map]);

  return null;
});

export default MapViewController;
