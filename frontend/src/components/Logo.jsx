import React from 'react';

// Q-DFRO brand mark: a bent route (graph-path motif) between three nodes,
// with one node ringed like an orbiting quantum particle - route + quantum,
// in the brand accent color. Same mark is saved standalone as
// frontend/public/favicon.svg.
export default function Logo({ size = 28, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M6 25 L14 15 L26 8"
        fill="none"
        stroke="#C6602E"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="6" cy="25" r="2.4" fill="#C6602E" />
      <circle cx="26" cy="8" r="2.4" fill="#C6602E" />
      <circle cx="14" cy="15" r="5" fill="none" stroke="#C6602E" strokeWidth="1" opacity="0.5" />
      <circle cx="14" cy="15" r="2.4" fill="#0D0C0B" stroke="#C6602E" strokeWidth="1.5" />
    </svg>
  );
}
