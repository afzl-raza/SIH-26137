import React, { useMemo, useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';

// Animates a 0->1 progress value whenever `resultObj` becomes a *new*
// object (i.e. a fresh optimize/re-optimize result arrived) - used to fade
// the previous route out and the new route in. Both routes being faded are
// real, already-computed coordinate arrays; this only transitions opacity,
// it never invents an intermediate path.
function useRouteTransition(resultObj, duration = 800) {
  const [progress, setProgress] = useState(1);
  const prevRef = useRef(resultObj);

  useEffect(() => {
    if (resultObj === prevRef.current) return;
    prevRef.current = resultObj;
    if (!resultObj) return;
    setProgress(0);
    const start = performance.now();
    let raf;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      setProgress(t);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [resultObj, duration]);

  return progress;
}

// Custom Marker HTML Generators - hand-drawn inline SVG glyphs instead of
// emoji (emoji renders inconsistently across OSes and is a strong
// "default/AI-generated" tell). Colors follow the asphalt/traffic palette.
const createDepotMarkerIcon = () => L.divIcon({
  html: `<div style="background:#1E1B18; border:2px solid #C1443B; border-radius:6px; padding:2px 6px; color:#E8918A; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:bold; box-shadow:0 4px 12px rgba(193,68,59,0.35); display:flex; align-items:center; gap:4px;">
          <svg width="9" height="9" viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" rx="2" fill="none" stroke="#C1443B" stroke-width="1.5"/></svg>
          <span>DEPOT</span>
         </div>`,
  className: 'custom-leaflet-depot',
  iconSize: [60, 24],
  iconAnchor: [30, 12]
});

const createJobMarkerIcon = (jobId) => L.divIcon({
  html: `<div style="background:#1E1B18; border:1.5px solid #5D7A9E; border-radius:12px; padding:1px 6px; color:#9AB3CC; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:600; box-shadow:0 2px 8px rgba(0,0,0,0.5); display:flex; align-items:center; gap:3px;">
          <svg width="7" height="7" viewBox="0 0 8 8"><circle cx="4" cy="4" r="3.2" fill="#5D7A9E"/></svg>
          <span>D${jobId < 10 ? '0' + jobId : jobId}</span>
         </div>`,
  className: 'custom-leaflet-job',
  iconSize: [48, 20],
  iconAnchor: [24, 10]
});

const createVehicleMarkerIcon = (vehicleId, color, isSelected) => L.divIcon({
  html: `<div style="background:#1E1B18; border:${isSelected ? '3px' : '2px'} solid ${color}; border-radius:12px; padding:2px 7px; color:#FFFFFF; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:bold; box-shadow:0 4px 14px ${color}66; display:flex; align-items:center; gap:4px; transform:scale(${isSelected ? '1.15' : '1.0'});">
          <svg width="13" height="9" viewBox="0 0 16 10"><rect x="0.5" y="1.5" width="10" height="6.5" rx="1" fill="${color}"/><rect x="10.5" y="3.5" width="4.5" height="4.5" rx="0.8" fill="${color}"/><circle cx="4" cy="9" r="1.3" fill="#1E1B18" stroke="${color}" stroke-width="1"/><circle cx="12.5" cy="9" r="1.3" fill="#1E1B18" stroke="${color}" stroke-width="1"/></svg>
          <span>V${vehicleId < 10 ? '0' + vehicleId : vehicleId}</span>
         </div>`,
  className: 'custom-leaflet-vehicle',
  iconSize: [48, 24],
  iconAnchor: [24, 12]
});

export default function NetworkMap({
  scenario,
  currentResult,
  previousResult,
  selectedIncidentEdge,
  selectedVehicleId,
  onSelectVehicle,
  weights,
  onDisruptEdge,
  disruptDisabled,
  previewResult,
  previewedAlgorithm
}) {
  const [vehicleFilter, setVehicleFilter] = useState('all');
  const [mapView, setMapView] = useState('gis'); // 'gis' | 'graph' - same real nodes/edges, just a render toggle
  const routeTransition = useRouteTransition(currentResult);

  // ALL hooks must be called unconditionally before any early return
  const nodes = scenario?.nodes || [];
  const edges = scenario?.edges || [];
  const jobs = scenario?.jobs || [];
  const vehicles = scenario?.vehicles || [];

  const center = useMemo(() => {
    if (nodes.length === 0) return [12.9716, 77.5946];
    const lats = nodes.map(n => n.lat);
    const lngs = nodes.map(n => n.lng);
    return [
      lats.reduce((a, b) => a + b, 0) / lats.length,
      lngs.reduce((a, b) => a + b, 0) / lngs.length
    ];
  }, [nodes]);

  const nodeMap = useMemo(() => {
    const map = new Map();
    nodes.forEach(n => map.set(n.id, n));
    return map;
  }, [nodes]);

  const jobNodeIds = useMemo(() => new Set(jobs.map(j => j.node_id)), [jobs]);

  const jobMap = useMemo(() => {
    const map = new Map();
    jobs.forEach(j => map.set(j.node_id, j));
    return map;
  }, [jobs]);

  const edgeLines = useMemo(() => {
    const drawn = new Set();
    const list = [];

    edges.forEach(e => {
      const key = [Math.min(e.source, e.destination), Math.max(e.source, e.destination)].join('-');
      if (drawn.has(key)) return;
      drawn.add(key);

      const n1 = nodeMap.get(e.source);
      const n2 = nodeMap.get(e.destination);
      if (!n1 || !n2) return;

      const isIncident = selectedIncidentEdge && (
        (selectedIncidentEdge.source === e.source && selectedIncidentEdge.destination === e.destination) ||
        (selectedIncidentEdge.source === e.destination && selectedIncidentEdge.destination === e.source)
      );

      let color = '#4A423A';
      let weight = 2.5;
      let opacity = 0.6;

      if (isIncident || e.traffic_factor > 2.5) {
        color = '#C1443B';
        weight = 5.5;
        opacity = 0.95;
      } else if (e.traffic_factor > 1.5) {
        color = '#E8A93A';
        weight = 3.5;
        opacity = 0.8;
      }

      list.push({
        id: key,
        source: e.source,
        destination: e.destination,
        positions: [[n1.lat, n1.lng], [n2.lat, n2.lng]],
        color, weight, opacity, isIncident,
        trafficFactor: e.traffic_factor,
        roadName: e.road_name,
        baseTime: e.base_travel_time,
        currentTime: e.current_travel_time,
        distance: e.distance
      });
    });

    return list;
  }, [edges, nodeMap, selectedIncidentEdge]);

  const displayedResult = previewResult || currentResult;

  const activeRouteLines = useMemo(() => {
    if (!displayedResult || !displayedResult.routes) return [];
    const vColorMap = new Map(vehicles.map(v => [v.id, v.color]));

    return displayedResult.routes.map(r => {
      const coords = r.node_path.map(nid => {
        const node = nodeMap.get(nid);
        return node ? [node.lat, node.lng] : null;
      }).filter(Boolean);

      const isSelected = selectedVehicleId === r.vehicle_id || vehicleFilter === r.vehicle_id;
      const isFilteredOut = vehicleFilter !== 'all' && vehicleFilter !== r.vehicle_id;

      return {
        vehicleId: r.vehicle_id,
        color: vColorMap.get(r.vehicle_id) || '#C6602E',
        coords,
        jobsCount: r.job_ids.length,
        dist: r.route_distance,
        time: r.route_travel_time,
        isSelected, isFilteredOut,
        routeObj: r
      };
    });
  }, [displayedResult, vehicles, nodeMap, selectedVehicleId, vehicleFilter]);

  // Per-vehicle-color glow rule, applied via className (not a duplicated
  // Polyline) - avoids the zoom/pan micro-stutter a second SVG path per
  // route would add.
  const routeGlowCss = useMemo(() => {
    return activeRouteLines
      .map(ar => `.route-glow-v${ar.vehicleId} { filter: drop-shadow(0 0 4px ${ar.color}); }`)
      .join('\n');
  }, [activeRouteLines]);

  const vehicleMarkers = useMemo(() => {
    if (activeRouteLines.length === 0) return [];

    const numV = activeRouteLines.length;
    const depotNode = nodes.find(n => n.is_depot) || nodes[0];
    if (!depotNode) return [];

    return activeRouteLines.map((ar, idx) => {
      let position = [depotNode.lat, depotNode.lng];

      if (ar.coords.length > 2) {
        const firstStop = ar.coords[1];
        const secondStop = ar.coords[Math.min(2, ar.coords.length - 1)];
        position = [
          (firstStop[0] + secondStop[0]) / 2,
          (firstStop[1] + secondStop[1]) / 2
        ];
      } else if (ar.coords.length === 2) {
        position = ar.coords[1];
      } else {
        const angle = (2 * Math.PI * idx) / numV;
        position = [
          depotNode.lat + 0.003 * Math.cos(angle),
          depotNode.lng + 0.003 * Math.sin(angle)
        ];
      }

      const vehicleObj = vehicles.find(v => v.id === ar.vehicleId);

      return {
        vehicleId: ar.vehicleId,
        color: ar.color,
        position,
        jobsCount: ar.jobsCount,
        dist: ar.dist,
        time: ar.time,
        isSelected: ar.isSelected,
        vehicleObj,
        routeObj: ar.routeObj
      };
    });
  }, [activeRouteLines, nodes, vehicles]);

  const previousRouteLines = useMemo(() => {
    if (!previousResult || !previousResult.routes) return [];

    return previousResult.routes.map(r => {
      const coords = r.node_path.map(nid => {
        const node = nodeMap.get(nid);
        return node ? [node.lat, node.lng] : null;
      }).filter(Boolean);

      return { vehicleId: r.vehicle_id, coords };
    });
  }, [previousResult, nodeMap]);

  // NOW the early return, after all hooks
  if (nodes.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[#171513] text-gray-400 font-mono text-xs rounded-xl border border-[#332E29]">
        Generate a scenario to begin fleet route optimization.
      </div>
    );
  }

  return (
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-[#332E29] shadow-2xl flex flex-col">
      {routeGlowCss && <style>{routeGlowCss}</style>}
      {previewResult && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1001] bg-[#3A2318] border border-[#5A3A22] text-[#E8A578] px-3 py-1 rounded-full text-[11px] font-mono font-semibold shadow-xl">
          PREVIEWING: {(previewedAlgorithm || '').toUpperCase()} routes (benchmark result, not applied)
        </div>
      )}

      {/* GIS <-> Graph View toggle - same real nodes/edges either way */}
      <div className="absolute top-3 right-3 z-[1000] clean-panel px-2 py-1.5 rounded-lg text-xs flex items-center gap-1 border border-[#332E29] shadow-xl pointer-events-auto font-mono">
        <button
          onClick={() => setMapView('gis')}
          className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] ${
            mapView === 'gis' ? 'bg-[#C6602E] text-white' : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
          }`}
        >
          GIS View
        </button>
        <button
          onClick={() => setMapView('graph')}
          className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] ${
            mapView === 'graph' ? 'bg-[#C6602E] text-white' : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
          }`}
        >
          Graph View
        </button>
      </div>

      {/* Top Filter Bar for Vehicles */}
      {vehicles.length > 0 && (
        <div className="absolute top-3 left-3 z-[1000] clean-panel px-3 py-1.5 rounded-lg text-xs flex items-center space-x-2 border border-[#332E29] shadow-xl pointer-events-auto font-mono max-w-[calc(100%-1.5rem)] overflow-x-auto">
          <span className="text-gray-400 text-[10px] uppercase font-bold tracking-wider flex-shrink-0">ROUTES:</span>
          <button
            onClick={() => setVehicleFilter('all')}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors flex-shrink-0 focus-visible:ring-2 focus-visible:ring-[#C6602E] ${
              vehicleFilter === 'all' ? 'bg-[#C6602E] text-white' : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
            }`}
          >
            ALL ({vehicles.length})
          </button>
          {vehicles.map(v => (
            <button
              key={v.id}
              onClick={() => {
                setVehicleFilter(v.id);
                const rObj = currentResult?.routes?.find(r => r.vehicle_id === v.id);
                if (onSelectVehicle) onSelectVehicle(v, rObj);
              }}
              className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors flex items-center space-x-1 flex-shrink-0 focus-visible:ring-2 focus-visible:ring-[#C6602E] ${
                vehicleFilter === v.id || selectedVehicleId === v.id
                  ? 'text-white shadow-md'
                  : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
              }`}
              style={{
                backgroundColor: vehicleFilter === v.id || selectedVehicleId === v.id ? v.color : undefined
              }}
            >
              <span>V0{v.id}</span>
            </button>
          ))}
        </div>
      )}

      {/*
        react-leaflet's MapContainer does not reactively re-apply its own
        className after the Leaflet instance mounts (Leaflet's own JS owns
        that DOM node's class list from then on), so the GIS/Graph toggle
        class has to live on this wrapper div instead, targeted via a
        descendant selector in index.css.
      */}
      <div className={`w-full h-full ${mapView === 'graph' ? 'graph-view-grid' : ''}`}>
      <MapContainer
        center={center}
        zoom={12}
        scrollWheelZoom={true}
        className="w-full h-full"
      >
        {mapView === 'gis' && (
          // Standard OSM raster tiles at full brightness - a dark CSS
          // filter and CartoDB's dark basemap were both tried; the filter
          // looked vague/washed out and CartoDB's now requires an API key
          // (renders an "API KEY REQUIRED" watermark without one).
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        )}

        {/* Base Network Edges */}
        {edgeLines.map(e => (
          <Polyline
            key={e.id}
            positions={e.positions}
            pathOptions={{
              color: e.color,
              weight: e.weight,
              opacity: e.opacity,
              className: e.isIncident ? 'incident-road-pulse' : ''
            }}
          >
            <Popup>
              <div className="text-xs space-y-1 font-mono">
                <p className="font-bold text-[#5D7A9E]">{e.roadName}</p>
                <p>Normal Time: {e.baseTime} min</p>
                <p>Current Time: <span className={e.trafficFactor > 2.0 ? 'text-[#C1443B] font-bold' : 'text-[#6B9A57]'}>{e.currentTime} min ({e.trafficFactor}x)</span></p>
                <p>Status: {e.trafficFactor > 2.0 ? '⚠ INCIDENT DISRUPTED' : 'NORMAL'}</p>
                {weights && (
                  <div className="border-t border-[#3A342E] mt-1.5 pt-1.5 space-y-0.5">
                    <p className="text-gray-400 text-[10px] uppercase">Why this road costs what it costs</p>
                    <p>Travel Time: {weights.alpha} × {e.currentTime} = {(weights.alpha * e.currentTime).toFixed(2)}</p>
                    <p>Distance: {weights.beta} × {e.distance} = {(weights.beta * e.distance).toFixed(2)}</p>
                    <p>Congestion: {weights.gamma} × {Math.max(0, (e.trafficFactor - 1) * e.baseTime).toFixed(2)} = {(weights.gamma * Math.max(0, (e.trafficFactor - 1) * e.baseTime)).toFixed(2)}</p>
                  </div>
                )}
                {onDisruptEdge && (
                  <div className="border-t border-[#3A342E] mt-1.5 pt-1.5 space-y-1">
                    <p className="text-gray-400 text-[10px] uppercase">Disrupt This Road</p>
                    <div className="flex gap-1">
                      {[{ label: 'Low', factor: 1.5 }, { label: 'Medium', factor: 2.5 }, { label: 'Severe', factor: 4.0 }].map(sev => (
                        <button
                          key={sev.label}
                          disabled={disruptDisabled}
                          onClick={() => onDisruptEdge(e.source, e.destination, sev.factor)}
                          className="px-1.5 py-0.5 rounded bg-[#3A1C18]/80 hover:bg-[#3A1C18] text-[#E8918A] text-[10px] font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          {sev.label}
                        </button>
                      ))}
                    </div>
                    {disruptDisabled && (
                      <p className="text-[9px] text-gray-500">Optimize the fleet first to enable disruption.</p>
                    )}
                  </div>
                )}
              </div>
            </Popup>
          </Polyline>
        ))}

        {/* Previous Route Overlay - fades out as the new route fades in
            (Before->After transition, both endpoints real data) */}
        {previousRouteLines.map((pr, idx) => (
          <Polyline
            key={`prev-route-${idx}`}
            positions={pr.coords}
            pathOptions={{
              color: '#6B6259',
              weight: 2.5,
              dashArray: '6, 8',
              opacity: 0.4 * (1 - routeTransition)
            }}
          />
        ))}

        {/* Active Optimized Vehicle Routes */}
        {activeRouteLines.map(ar => {
          if (ar.isFilteredOut) return null;

          return (
            <Polyline
              key={`active-route-${ar.vehicleId}`}
              positions={ar.coords}
              eventHandlers={{
                click: () => {
                  const vehicleObj = vehicles.find(v => v.id === ar.vehicleId);
                  if (onSelectVehicle && vehicleObj) onSelectVehicle(vehicleObj, ar.routeObj);
                }
              }}
              pathOptions={{
                color: ar.color,
                weight: ar.isSelected ? 7 : 5,
                opacity: (ar.isSelected ? 1.0 : 0.85) * Math.max(0.15, routeTransition),
                className: `route-glow-v${ar.vehicleId}`
              }}
            >
              <Popup>
                <div className="text-xs space-y-1 font-mono">
                  <p className="font-bold text-sm" style={{ color: ar.color }}>Vehicle 0{ar.vehicleId}</p>
                  <p>Stops: {ar.jobsCount} Jobs</p>
                  <p>Distance: {ar.dist} km</p>
                  <p>Travel Time: {ar.time} min</p>
                </div>
              </Popup>
            </Polyline>
          );
        })}

        {/* Nodes (Depot, Jobs, Intersections) */}
        {nodes.map(n => {
          const isJob = jobNodeIds.has(n.id);
          const jobObj = jobMap.get(n.id);

          if (n.is_depot) {
            return (
              <Marker
                key={`node-${n.id}`}
                position={[n.lat, n.lng]}
                icon={createDepotMarkerIcon()}
              >
                <Popup>
                  <div className="text-xs font-mono">
                    <p className="font-bold text-[#C1443B] text-sm">CENTRAL DEPOT</p>
                    <p>Node ID: #{n.id}</p>
                  </div>
                </Popup>
              </Marker>
            );
          }

          if (isJob) {
            return (
              <Marker
                key={`node-${n.id}`}
                position={[n.lat, n.lng]}
                icon={createJobMarkerIcon(jobObj.id)}
              >
                <Popup>
                  <div className="text-xs font-mono space-y-1">
                    <p className="font-bold text-[#5D7A9E]">Delivery Job #{jobObj.id}</p>
                    <p>Node: #{n.id}</p>
                    <p>Demand: {jobObj.demand} units</p>
                    <p>Service Time: {jobObj.service_time} min</p>
                  </div>
                </Popup>
              </Marker>
            );
          }

          return (
            <CircleMarker
              key={`node-${n.id}`}
              center={[n.lat, n.lng]}
              radius={3}
              pathOptions={{
                color: '#4A423A',
                fillColor: '#242019',
                fillOpacity: 1,
                weight: 1
              }}
            />
          );
        })}

        {/* Vehicle Markers */}
        {vehicleMarkers.map(vm => (
          <Marker
            key={`vehicle-marker-${vm.vehicleId}`}
            position={vm.position}
            icon={createVehicleMarkerIcon(vm.vehicleId, vm.color, vm.isSelected)}
            eventHandlers={{
              click: () => {
                if (onSelectVehicle && vm.vehicleObj) onSelectVehicle(vm.vehicleObj, vm.routeObj);
              }
            }}
          >
            <Popup>
              <div className="text-xs font-mono">
                <p className="font-bold text-sm" style={{ color: vm.color }}>Vehicle 0{vm.vehicleId}</p>
                <p>Stops: {vm.jobsCount} Jobs</p>
                <p>Distance: {vm.dist} km</p>
                <p>Travel Time: {vm.time} min</p>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      </div>

      {/* Map Legend Overlay */}
      <div className="absolute bottom-3 left-3 z-[1000] clean-panel px-3 py-2 rounded-lg text-xs space-y-1.5 border border-[#332E29] shadow-xl pointer-events-auto">
        <div className="font-semibold text-gray-400 text-[10px] uppercase tracking-wider mb-1">MAP LEGEND</div>
        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="w-2.5 h-2.5 rounded-full bg-[#C1443B] inline-block"></span>
          <span className="text-gray-300">Depot</span>
        </div>
        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="w-2.5 h-2.5 rounded-full bg-[#5D7A9E] inline-block"></span>
          <span className="text-gray-300">Job Target</span>
        </div>
        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="w-4 h-1 bg-[#4A423A] rounded inline-block"></span>
          <span className="text-gray-300">Normal Road</span>
        </div>
        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="w-4 h-1 bg-[#C1443B] rounded inline-block animate-pulse"></span>
          <span className="text-gray-300">⚠ Incident Road</span>
        </div>
        {vehicles.length > 0 && (
          <div className="flex items-center space-x-2 text-[11px] font-mono">
            <span className="flex -space-x-0.5">
              {vehicles.slice(0, 3).map(v => (
                <span
                  key={v.id}
                  className="w-2.5 h-1 rounded-full inline-block ring-1 ring-[#1E1B18]"
                  style={{ backgroundColor: v.color }}
                />
              ))}
            </span>
            <span className="text-gray-300">Vehicle Route (color = vehicle)</span>
          </div>
        )}
        {previousResult && (
          <div className="flex items-center space-x-2 border-t border-[#332E29] pt-1 mt-1 text-[10px] font-mono text-gray-400">
            <span className="w-4 border-t-2 border-dashed border-[#6B6259] inline-block"></span>
            <span>Pre-incident Route (before this re-optimization)</span>
          </div>
        )}
      </div>
    </div>
  );
}
