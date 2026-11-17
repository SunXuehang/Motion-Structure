# UWB Handle Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Steps use checkbox syntax for tracking.

**Goal:** Add the approved two-hole UWB shelf and deliver checked STEP files and previews.

**Architecture:** Extend the existing FreeCAD parametric handle and, on Windows without FreeCAD, apply the same shelf geometry to a frozen pre-change STEP using the installed OCP kernel. Use official dimensions for explicitly labelled UWB/antenna reference envelopes, retaining the finalized metal RTK assembly.

**Tech Stack:** Python, installed OCP, pytest, Matplotlib.

**Spec:** ../specs/2026-11-17-uwb-handle-design.md

## Global Constraints

32 × 20 × 6 mm shelf; R4 roots; two Ø3.4 through-holes, 12 mm pitch, (±6,51); unchanged 118 mm handle. Antenna folds 90° toward +Y. Preserve originals and do not modify RTK geometry.

## Review Focus

- Existing mounting holes/bore/foot must survive unchanged.
- Through-holes must be accessible from above, align to the device, and leave adequate edge material.
- Re-running the exporter must not compound the shelf onto already-modified geometry.
- Antenna hinge dimensions are incomplete: report conservative assumptions rather than exact-CAD claims.
- Exported assembly must use the new handle and preserve all other current metal-RTK parts.

### Task 1: Shelf geometry

Files: modify src/bracket/standing_handle.py; create src/bracket/uwb_mount.py and tests/test_uwb_mount.py; retain tests/standing_handle_baseline_20261117.step.

- [x] Write/run failing tests for shelf solids, two holes, unchanged legacy geometry, and invalid parameters.
- [x] Implement shared dimensions and equivalent FreeCAD/OCP shelf construction.
- [x] Run new geometry tests and existing pure-Python dimensional tests (70 passed).

### Task 2: Export, check, and illustrate

Files: create scripts/build_uwb_mount.py; exports/standing_handle_uwb.step; step/standing_device_with_uwb.step; renders/standing_handle_uwb.png; reports/uwb_mount_20261117.json and .md; update README.md and canonical handle STEP.

- [x] Test folded antenna clearance and no overlap with the complete represented assembly; negative control for the straight antenna reaching below the floor.
- [x] Build reference envelopes; check screw access, root continuity, STEP readback, non-UWB geometry preservation, and export volume/bounds.
- [x] Render actual exported geometry, inspect PNGs, fix any layout defects, and record hashes/limitations.
- [x] Obtain one fresh whole-change review; no delivery-blocking issues found. Final affected checks: 71 passed in 14.78 s.

## Execution record

- Working in the user-bound existing checkout on feature branch codex/uwb-handle; no new worktree or commits needed for requested local deliverables.
- User explicitly authorized implementation and export; no additional plan approval round.
- Windows has OCP and rendering libraries but no FreeCAD runtime. OCP exports and FreeCAD source share the same parametric dimensions; retain this runtime limitation in the report.
- STEP roundtrip diagnostic: default fixed quadrature gave artificial sensor/metal volume deltas of -0.8723/-0.5618 mm³; adaptive closed-shell integration gave -0.00000017/-0.0001009 mm³ with equal bounds and solid counts. Use adaptive integration for preservation checks; do not relax the 0.001 mm³ gate.
- Final: 16 new-vs-existing collision pairs and 19 sampled antenna bend angles have zero overlap. Folded antenna floor clearance35.04 mm; minimum handle distance25.3 mm. Export hashes verified. Two PNGs visually inspected by author and independent reviewer.
