import React from 'react';
import LandingNavbar from '../components/landing/LandingNavbar';
import Hero from '../components/landing/Hero';
import FeatureCards from '../components/landing/FeatureCards';
import CTABanner from '../components/landing/CTABanner';

// onEnterApp is a plain navigation hook today (jumps straight into the
// dashboard). Once authentication exists, App.jsx can point this at the
// auth route instead without any change here.
export default function LandingPage({ onEnterApp }) {
  return (
    <div className="min-h-screen bg-[#0D0C0B] text-gray-100 font-sans selection:bg-[#C6602E] selection:text-white">
      <LandingNavbar onEnterApp={onEnterApp} />
      <Hero onEnterApp={onEnterApp} />
      <FeatureCards />
      <CTABanner onEnterApp={onEnterApp} />

      <footer className="border-t border-[#332E29] py-6 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-mono text-gray-500">
          <span>Q-DFRO &mdash; Quantum-Inspired Intelligent Traffic Route Optimization</span>
          <span>Smart India Hackathon &middot; Concept Prototype</span>
        </div>
      </footer>
    </div>
  );
}
