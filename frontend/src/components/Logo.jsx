import React from 'react';

// Q-DFRO brand mark: a minimal white car + destination pin. Deliberately
// flat (no network nodes, no quantum ring, no text) so it stays legible at
// ~20px in the header, inside VehicleLoader, and in the Executive Overview
// empty state. Same glyph everywhere - only `holeColor` (the pin's punched
// center) changes to match whatever it's sitting on.
export default function Logo({ size = 28, className = '', color = '#FFFFFF', holeColor = '#1E1B18' }) {
  return (
    <svg
      width={size}
      height={(size * 24) / 34}
      viewBox="0 0 34 24"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Car */}
      <rect x="3" y="13" width="20" height="6" rx="2.5" fill={color} />
      <rect x="8" y="8" width="10" height="5.5" rx="1.8" fill={color} />
      <circle cx="8.5" cy="20" r="2.3" fill={color} />
      <circle cx="21" cy="20" r="2.3" fill={color} />
      {/* Destination pin */}
      <path
        d="M27 2c-2.76 0-5 2.24-5 5 0 3.75 5 9 5 9s5-5.25 5-9c0-2.76-2.24-5-5-5z"
        fill={color}
      />
      <circle cx="27" cy="7" r="1.6" fill={holeColor} />
    </svg>
  );
}
