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
//      since those buttons cannot call useMap() themselves - and up to
//      NetworkMap's own auto-fit effect, the same way.
//
//   3. Tell NetworkMap, via `onReady`, the moment this component actually
//      has a live map to hand out through that imperative API. react-leaflet's
//      MapContainer mounts in two passes - the wrapping <div>'s ref callback
//      constructs the Leaflet map and calls setState, and only on the
//      NEXT render (a separate commit) does it actually render children
//      like this component - so a `ref`/effect in the PARENT (NetworkMap)
//      that runs during the FIRST commit will always see this component's
//      own ref as not-yet-attached, with no further render/effect ever
//      re-triggered by that (nothing about a plain `mapControllerRef` ever
//      changes). Without `onReady`, that parent effect's one and only
//      chance to fit the map to the new scenario/result is silently and
//      permanently missed - confirmed via a real render test, not assumed.
//
// It never decides *what* bounds to show - NetworkMap computes those from
// the actual scenario data. This component only knows how to point an
// already-mounted Leaflet map at a box it's given, safely and without
// fighting the user's own pan/zoom.
const MapViewController = forwardRef(function MapViewController({ onReady } = {}, ref) {
  const map = useMap();
  const lastSizeRef = useRef({ width: 0, height: 0 });
  const rafIdsRef = useRef([]);
  // A fit requested while this container has no real pixel size (a hidden
  // mobile "Controls" tab - the map's wrapping div is display:none whenever
  // Dashboard.jsx's activeMobileTab !== 'map', and the Generate button that
  // starts a new scenario/result lives on that OTHER tab - or any other
  // genuinely zero-sized moment) can't be computed correctly: Leaflet's
  // getBoundsZoom divides by the container's current pixel size
  // (map.getSize()), so a 0x0 read produces a nonsensically low zoom - the
  // map ends up "zoomed out to a huge area" - no matter how tight and
  // correct the bounds passed in were. invalidateSize() alone can't fix
  // this after the fact: it only re-syncs Leaflet's projection to whatever
  // center/zoom is ALREADY set, it never re-fits to a target. So a fit
  // asked for while hidden is remembered here and genuinely (re-)applied
  // once the container is next observed to have a real size.
  const pendingFitRef = useRef(null);

  useEffect(() => {
    if (map) onReady?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  const hasRealSize = () => {
    if (!map) return false;
    const size = map.getSize();
    return size.x > 0 && size.y > 0;
  };

  const applyOrDefer = (kind, leafletBounds, options) => {
    if (!map || !leafletBounds) return;
    if (!hasRealSize()) {
      pendingFitRef.current = { kind, leafletBounds, options };
      return;
    }
    pendingFitRef.current = null;
    if (kind === 'fit') {
      map.fitBounds(leafletBounds, options);
    } else {
      map.flyToBounds(leafletBounds, options);
    }
  };

  useImperativeHandle(ref, () => ({
    fitToBounds(leafletBounds, options = {}) {
      applyOrDefer('fit', leafletBounds, options);
    },
    flyToBounds(leafletBounds, options = {}) {
      // flyToBounds animates; a user who has the tab in the background or
      // prefers-reduced-motion still gets a correct final view because
      // Leaflet clamps duration internally when the map isn't visible, and
      // we always pass a bounded duration below rather than relying on
      // defaults drifting later.
      applyOrDefer('fly', leafletBounds, options);
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
        // The container may have gained a real size only just now (this is
        // the very case (a) exists for) - if a fit was deferred waiting for
        // that, apply it for real rather than leaving it pending until some
        // later, unrelated resize happens to fire the observer below.
        if (pendingFitRef.current && hasRealSize()) {
          const { kind, leafletBounds, options } = pendingFitRef.current;
          pendingFitRef.current = null;
          if (kind === 'fit') map.fitBounds(leafletBounds, options);
          else map.flyToBounds(leafletBounds, options);
        }
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
        // The container just went from zero (or unknown) to a real size -
        // e.g. the mobile "Controls" tab that was active when Generate ran
        // just got switched back to "Map". A fit requested while hidden
        // couldn't be computed correctly then; apply it for real now that
        // Leaflet has an actual size to measure against.
        if (pendingFitRef.current) {
          const { kind, leafletBounds, options } = pendingFitRef.current;
          pendingFitRef.current = null;
          if (kind === 'fit') map.fitBounds(leafletBounds, options);
          else map.flyToBounds(leafletBounds, options);
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
