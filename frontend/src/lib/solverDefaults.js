// Render's free tier (see render.yaml: plan: free) gives the backend a
// throttled, shared CPU - a full population_size=40/max_iterations=100 run
// is comfortably fast on a local dev machine, but Run Benchmark (5-6
// population-based algorithms, each doing population_size * max_iterations
// real candidate evaluations, back to back) gets noticeably slower there.
//
// import.meta.env.PROD is Vite's own build-mode flag: true only for a
// `vite build` production bundle (what Vercel actually deploys), false for
// the local dev server (`vite`/`npm run dev`) regardless of which backend
// it happens to point at. That matches this project's real deployment
// pairing (Vercel frontend + Render backend) without needing to guess at
// the backend's own resources from the frontend.
//
// This only changes how long a run takes, never what is computed or how
// results are labeled - population_size/max_iterations are always the real
// values used and are always shown as-is (Comparison Conditions, the
// reproducibility footer, etc.), just smaller by default in production.
export const DEFAULT_POPULATION_SIZE = import.meta.env.PROD ? 20 : 40;
export const DEFAULT_MAX_ITERATIONS = import.meta.env.PROD ? 40 : 100;
