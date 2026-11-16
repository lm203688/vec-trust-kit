# vec-trust-kit

**A pre-submission physical for the NeurIPS 2026 Virtual Embryo Challenge.**

Before you spend one of your two irrevocable P3 submissions, this toolkit tells you three things: how far your prediction sits from the `copy_last` floor on the official 50–100 scale, which of the weighted metrics is your bottleneck, and whether your declared external data crosses a protected developmental window.

CPU-only, one command, no competition data required.

> **Honesty note.** The built-in demo runs on **synthetic data** (`synthetic.py`, fixed seed). Its numbers are a *demo of a mechanism*, not an empirical model evaluation. Do not cite them as evidence that any model is untrustworthy. The official metric mirror is a clearly-labelled **local approximation**, not the competition scorer.

---

## Install & run

```bash
pip install .
vectrust --help
vectrust diagnose --model linear --n-boot 10       # 2-axis diagnosis
vectrust guard --stage E11.5 --gene Ctnnb1          # protected-window check
vectrust score --task T1                             # local score mirror (approx.)
vectrust format --pred pred.h5ad --task T2          # format precheck (needs anndata)
python -m pytest tests/ -q                           # 40 tests
```

Or from source without installing:

```bash
python examples/demo.py                  # diagnosis report
python examples/demo.py --mode legacy    # v0.1-compatible teaching grades
python -m vec_trust.licenses --audit --check-urls
```

Only hard dependency: numpy. `anndata` is optional (enables real `.h5ad` format checks).

---

## What changed in v0.2 (responding to an external audit)

| v0.1 problem | v0.2 fix |
|---|---|
| Every verdict was `REFUTED` — unfalsifiable, decided by the synthetic generator | `diagnose()` splits the signal into **model axis (ΔRMSE)** and **interval axis (Δcoverage)**; a correct model + adaptive interval now *passes*, a wrong model fails |
| Conformal collapse under drift presented as model evidence | Explicitly labelled a theorem-level known result; criterion is now "can adaptive intervals recover coverage?" |
| Single seed, single split | `n_boot` repeated splits + bootstrap 95% CI; paired permutation test for the baseline ladder (`paired_ladder_test`) |
| "9 metrics / 3 protocols = official tasks" — structurally wrong | Official panel mirrored: T1 25/25/30/20, T2 4×25%, T3 30/25/25/20, normalized to floor=50/ceiling=100 (clearly marked local approximation) |
| Not installable, no CLI, no CI | `pip install .`, `vectrust` CLI, GitHub Actions on 3 Python versions, `CITATION.cff` |
| 30% dead links, 40% "see repo" in licence matrix | 3 dead links fixed, all "see repo" resolved, 9 conflicts each with verdict + evidence; `--audit` checks closure |

---

## Three pre-submission modules

| Module | Solves | Scarcity |
|---|---|---|
| **Score Mirror** | Approximate the 50–100 scale, break down weighted metrics, find the weakest | P3 allows only 2 submissions per board |
| **Rule Guard** | Is your external data inside a protected window (T1 E9.5–E13.5, nearness midpoint rule; T2/T3 bands)? Emits the disclosure template | "Undisclosed = violation", boundary rules are intricate |
| **Bio Gate** | Composition / marker / 3D continuity / growth / lineage gates | A generic conformal tool cannot do this; maps to T1's 30% distribution and T2's 25% geometry |

Plus a **format precheck** (gene order, `spatial_3D`, NaN, ≤1200 MB, no label leakage) and a **3-layer licence matrix** (code / weights / data, 27 entries).

> **Rule Guard and Bio Gate are conservative approximations** of publicly documented rules. Their output is a lead for human review, not a compliance verdict. Official rules take precedence.

---

## Scope & non-goals

- Does **not** train a model. The 2025 Virtual Cell Challenge concluded that perturbation models do not yet consistently beat naive baselines across all metrics; this toolkit is built around that finding.
- Does **not** include any competition data (Terms §14: research/education only; public release requires prior approval). Only synthetic + public data.
- Does **not** claim official-score parity. The score mirror has no official truth set or scorer to calibrate against.

Adapted from SwarmLabs (MIT) conformal audit core. MIT licensed. Chinese tutorial included.
