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

  useImperativeHandle(ref, () => ({
    fitToBounds(leafletBounds, options = {}) {
      if (!map || !leafletBounds) return;
      map.fitBounds(leafletBounds, options);
    },
    flyToBounds(leafletBounds, options = {}) {
      if (!map || !leafletBounds) return;
      // flyToBounds animates; a user who has the tab in the background or
      // prefers-reduced-motion still gets a correct final view because
      // Leaflet clamps duration internally when the map isn't visible, and
      // we always pass a bounded duration below rather than relying on
      // defaults drifting later.
      map.flyToBounds(leafletBounds, options);
    },
    setView(center, zoom, options = {}) {
      if (!map || !center) return;
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
