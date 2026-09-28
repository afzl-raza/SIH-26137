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

// The PROVE-stage evidence panels (Scalability/E1/E2/E4/E5) call
// /api/experiments/{name}/run, which is a DIFFERENT code path from the live
// demo above - it always uses the full, paper-documented solver budget
// (population_size=40, max_iterations=100, hardcoded in
// backend/experiments/config.py) so the checked-in evidence stays
// comparable to itself no matter which machine generated it. That budget is
// fine in seconds locally, but measured live against the real deployed
// Render free-tier backend: ~35s PER ALGORITHM (population=40/iterations=100
// is genuinely CPU-bound work, not something a lighter default can safely
// shrink without changing what E1-E6 are documented to measure) - E1 alone
// is ~2.5 minutes total, comfortably blowing through E4/E5's 60s client
// timeout.
//
// So "Run Now" only re-runs live where it can actually finish in a
// reasonable demo window - locally. In production it's replaced by a plain
// explanation instead of a button that times out in front of a judge. The
// displayed numbers are never affected either way: they're always the real,
// checked-in evidence from experiments/E*/*.json|csv, whichever machine most
// recently generated them.
export const ALLOW_LIVE_EXPERIMENT_RERUN = !import.meta.env.PROD;
