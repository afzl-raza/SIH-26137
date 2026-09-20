// Presentation for the congestion states the BACKEND declares.
//
// The map used to decide a road's colour from numeric cutoffs written here in
// React (traffic_factor > 2.5, > 1.5). Those cutoffs had no connection to the
// traffic model's own levels and would drift from them silently. Now the
// backend classifies every edge into a band as it writes the edge cost
// (realdata.conditions.recompute_edge_cost) and ships the result on
// `edge.congestion_level`; this file only says what each band LOOKS like.
//
// Nothing here computes a congestion state, a multiplier or a travel time.
// The published thresholds behind these names are readable at
// GET /api/conditions/model -> simulated.congestion_bands.
//
// All of it describes SIMULATED congestion from the traffic model. It is not a
// live traffic feed and must never be labelled as one.

export const CONGESTION_STYLES = {
  free_flow: { label: 'Free flow', color: '#4A423A', weight: 2.5, opacity: 0.6 },
  light: { label: 'Light', color: '#6B9A57', weight: 3.0, opacity: 0.7 },
  moderate: { label: 'Moderate', color: '#E8C578', weight: 3.5, opacity: 0.8 },
  heavy: { label: 'Heavy', color: '#E8A93A', weight: 4.5, opacity: 0.9 },
  severe: { label: 'Severe', color: '#C1443B', weight: 5.5, opacity: 0.95 }
};

// The order the legend lists them in - matches the backend's own band order.
export const CONGESTION_ORDER = ['free_flow', 'light', 'moderate', 'heavy', 'severe'];

// An operator-injected road incident. A separate axis from the network-wide
// level on the backend, so it gets its own treatment rather than being folded
// into whichever band its multiplier happens to land in.
export const INCIDENT_STYLE = { label: 'Incident', color: '#C1443B', weight: 6, opacity: 1.0 };

// A scenario generated before the backend declared bands (or a legacy inline
// scenario POSTed by an older client) has no congestion_level. Falling back to
// free_flow keeps such an edge drawn in the neutral road colour rather than
// guessing a state from its multiplier, which is exactly the client-side
// classification this module exists to remove.
export function congestionStyle(edge) {
  if (!edge) return CONGESTION_STYLES.free_flow;
  if (edge.has_incident) return INCIDENT_STYLE;
  return CONGESTION_STYLES[edge.congestion_level] || CONGESTION_STYLES.free_flow;
}

export function congestionLabel(edge) {
  if (!edge) return CONGESTION_STYLES.free_flow.label;
  if (edge.has_incident) return INCIDENT_STYLE.label;
  return (CONGESTION_STYLES[edge.congestion_level] || CONGESTION_STYLES.free_flow).label;
}
