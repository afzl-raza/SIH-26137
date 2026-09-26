import React from 'react';
import { Truck } from 'lucide-react';
import NetworkMap from '../NetworkMap';
import VehicleInspector from '../VehicleInspector';
import SectionHeader from './SectionHeader';

// The one real, interactive Leaflet map in the Executive Overview - actual
// road geometry (when the network is OpenStreetMap-sourced), actual
// routes, click-to-inspect. Read-only: no disrupt-road controls, no
// benchmark preview overlay - those stay Engineering-only actions.
export default function RoutePerformance({
  scenario, scenarioId, loading, currentResult,
  selectedVehicle, selectedRoute, onSelectVehicle, weights
}) {
  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
      <SectionHeader icon={Truck} title="Route Details" />
      <p className="text-xs text-gray-500 -mt-1">Click a route or vehicle on the map to inspect its details.</p>
      <div className="grid lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 h-[360px] sm:h-[420px]">
          <NetworkMap
            scenario={scenario}
            scenarioId={scenarioId}
            loading={loading}
            currentResult={currentResult}
            previousResult={null}
            selectedVehicleId={selectedVehicle?.id}
            onSelectVehicle={onSelectVehicle}
            weights={weights}
            disruptDisabled
            previewResult={null}
            previewedAlgorithm={null}
          />
        </div>
        <div className="h-[360px] sm:h-[420px]">
          <VehicleInspector
            vehicle={selectedVehicle}
            route={selectedRoute}
            scenario={scenario}
            onDeselect={() => onSelectVehicle?.(null, null)}
          />
        </div>
      </div>
    </div>
  );
}
