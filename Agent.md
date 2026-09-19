# Agent.md — AI Agent Contract for Q-DFRO

This file is the tool-agnostic version of the project's development rules, for any
AI coding agent working in this repository — Claude Code, GitHub Copilot, Cursor,
Codex, Gemini, or otherwise. It restates the binding rules from
[`CLAUDE.md`](CLAUDE.md) in a tool-neutral form and points to the two other
canonical documents: [`Engineering.md`](Engineering.md) (what the system is and how
it's built) and [`Task.md`](Task.md) (what's done and what's next).

If a tool-specific file (e.g. `CLAUDE.md`) gives more detailed workflow instructions
for its own tool, follow those too — they are additive, not a replacement for the
rules here.

---

## 1. What this project is

SIH26137 — Quantum-Inspired Intelligent Traffic Route Optimization. A **research
prototype**: a dynamic, multi-vehicle route-optimization platform that models an
urban road network, runs Greedy/GA/PSO/QPSO on it through one shared evaluator, and
demonstrates traffic-triggered re-optimization plus fair benchmarking. It is not a
production logistics system.

Read [`Engineering.md`](Engineering.md) before making any architectural change —
it documents the current implementation, not an aspiration. Read [`Task.md`](Task.md)
before picking up new work — it tracks what's actually done vs. outstanding, verified
against the code and test suite, not against the master plan alone.

## 2. Non-negotiable rules

1. **Never fabricate results.** No hard-coded benchmark numbers, no invented
   percentages ("QPSO is 20% faster"), no fake convergence curves. Every number
   shown anywhere — UI, docs, PPT, paper — must trace back to an actual run of the
   actual code. If a result is unfavorable to QPSO, report it as-is.
2. **One evaluator for every algorithm.** Do not let any optimizer compute its own
   cost or feasibility. Everything routes through `backend/fitness.py`.
3. **Don't overbuild.** Do not add authentication, payments, driver accounts,
   notifications, live GPS, production deployment, or a persistence layer
   (PostgreSQL/Docker/etc.) unless a human explicitly decides to move into that
   phase. See `Engineering.md` §13 for the full deferred list.
4. **Document only what's implemented.** If a constraint, algorithm variant, or
   API capability isn't in the code, it does not go in `Engineering.md`,
   `Task.md`, the README, or any research/PPT material.
5. **Keep the layers separate.** Simulation creates the problem; optimizers solve
   it; the evaluator scores it; the API exposes it; the frontend visualizes it.
   No algorithm module imports frontend code or vice versa; no UI component
   computes cost/feasibility itself.
6. **Reproducibility is mandatory.** Any new scenario-generation or optimizer code
   must accept and honor a seed. Same seed + same config ⇒ same result, and that
   must be covered by a test, not just asserted in a docstring.
7. **Small modules, clear names, minimal dependencies.** Prefer editing an existing
   module over introducing a new abstraction. No monolithic files, no duplicated
   objective functions, no algorithm logic inside frontend components.
8. **Update `Task.md` and `Engineering.md` together with the code.** A status
   flip from ❌/⚠️ to ✅ in one without the other is treated as an incomplete change.

## 3. Working style

- Prefer the smallest change that satisfies the task. A bug fix does not need a
  refactor; a new experiment does not need a new persistence layer.
- Before claiming something works, run it — the test suite (`pytest backend/tests
  -q`), the dev servers, or both. For frontend-visible changes, actually load the
  page and interact with it; don't infer correctness from reading code alone.
- When a task in `Task.md` is ambiguous or conflicts with `Engineering.md`, resolve
  the conflict by checking the actual code first (source of truth), then update
  whichever document was stale.
- When in doubt about scope (e.g. "should this use a database now?"), default to
  the smaller/current-round answer and flag the larger option as a question rather
  than building it unasked.

## 4. Where the deeper detail lives

| Question | Look here |
|---|---|
| What's the system architecture? | `Engineering.md` §2–3 |
| What's the exact objective/constraints? | `Engineering.md` §4 |
| How does QPSO turn continuous state into routes? | `Engineering.md` §5, §7 |
| What API endpoints exist? | `Engineering.md` §11 |
| What's done vs. still needed? | `Task.md` |
| What should never be built (this round)? | `Engineering.md` §13 |
| How do I install/run this? | `Readme.md` |
| Why was a past decision made (e.g. tile provider)? | `Documnetation.md` (dated change log — not an architecture reference) |
| Claude-Code-specific tool/workflow rules | `CLAUDE.md` |
