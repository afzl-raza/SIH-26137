import React from 'react';
import LandingNavbar from '../components/landing/LandingNavbar';
import Hero from '../components/landing/Hero';
import HowItWorks from '../components/landing/HowItWorks';
import QPSOExplainer from '../components/landing/QPSOExplainer';
import FeatureCards from '../components/landing/FeatureCards';
import TrafficAdaptation from '../components/landing/TrafficAdaptation';
import BenchmarkSnapshot from '../components/landing/BenchmarkSnapshot';
import PlatformPreview from '../components/landing/PlatformPreview';
import CTABanner from '../components/landing/CTABanner';

// onEnterApp is a plain navigation hook - App.jsx wires it to the auth page
// today (from which "Continue as Guest" is still reachable) - nothing here
// needs to change if that target moves again.
export default function LandingPage({ onEnterApp }) {
  return (
    <div className="min-h-screen bg-[#0D0C0B] text-gray-100 font-sans selection:bg-[#C6602E] selection:text-white">
      <LandingNavbar onEnterApp={onEnterApp} />
      <Hero onEnterApp={onEnterApp} />
      <HowItWorks />
      <QPSOExplainer />
      <FeatureCards />
      <TrafficAdaptation />
      <BenchmarkSnapshot />
      <PlatformPreview />
      <CTABanner onEnterApp={onEnterApp} />

      <footer className="border-t border-[#332E29] py-6 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-mono text-gray-500">
          <span>Q-DFRO &mdash; Quantum-Inspired Intelligent Traffic Route Optimization</span>
          <span>Quantum-inspired optimization for intelligent fleet mobility.</span>
        </div>
      </footer>
    </div>
  );
}
