/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // "Traffic Amber & Asphalt" — warm near-black base (road surface,
        // not generic cool-gray tech panel), replacing the old Tailwind
        // slate defaults that read as templated.
        dark: {
          bg: "#0D0C0B",
          card: "#1E1B18",
          border: "#332E29",
          panel: "#171513"
        },
        // Two accents, deliberately separate in meaning:
        // brand.accent = product identity (logo, primary CTA, active state).
        // traffic.amber = literal traffic-caution semantics only.
        brand: {
          accent: "#C6602E",
          accentSoft: "#3A2318"
        },
        traffic: {
          amber: "#E8A93A",
          amberSoft: "#3A2E14",
          green: "#6B9A57",
          greenSoft: "#22301B",
          red: "#C1443B",
          redSoft: "#3A1C18"
        },
        // Per-vehicle route differentiation — warm-neutral variants so
        // vehicles stay visually distinct without a cool-toned rainbow
        // fighting the warm asphalt base.
        fleet: {
          ochre: "#C99A3B",
          clay: "#B5613F",
          teal: "#5F8A80",
          dusty: "#5D7A9E",
          olive: "#8A8C4E",
          plum: "#8C5A6E"
        }
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"]
      }
    },
  },
  plugins: [],
}
