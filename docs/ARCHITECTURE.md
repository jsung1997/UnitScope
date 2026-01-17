# Architecture Overview

This project is an **explainable unit-level analog circuit analysis engine**.
It reads an analog netlist, detects functional circuit units, evaluates their robustness,
and ranks potential weak points with human-readable explanations.

The system is intentionally modular so that detection logic, health checks,
and ranking logic can evolve independently.

---

## High-Level Flow

Netlist (.sp / .cdl)
↓
Parser
↓
Device Objects (MOSFETs, passives)
↓
Unit Detection (rules / patterns)
↓
Unit Dependency Graph
↓
Unit Health Checks
↓
Risk Ranking (Likelihood × Impact × Confidence)
↓
Explainable Output


---

## File & Module Responsibilities

### `main.py`
**Role:** Program entry point  
**Purpose:** Orchestrates the full pipeline.

**What happens here:**
- Load a netlist file
- Run unit detection
- Build dependency graph
- Compute scores
- Print ranked weak points

**Change this file when:**
- You want to change input/output behavior
- You want to add CLI arguments
- You want to export results to JSON or UI

---

## `engine/` package

This folder contains all core logic.

---

### `engine/models.py`
**Role:** Core data models  
**Purpose:** Defines the main objects used throughout the engine.

**Contains:**
- `Mosfet`: parsed transistor
- `Passive`: resistor / capacitor
- `Unit`: detected functional block (diff pair, mirror, etc.)

**Change this file when:**
- You want to store more attributes (e.g., W/L, device parameters)
- You want to add new result fields (recommended fix, failure mode)

---

### `engine/utils.py`
**Role:** Shared helper utilities  
**Purpose:** Small functions used across modules.

**Contains:**
- Value clipping helpers
- Supply / ground name detection
- Severity labeling logic

**Change this file when:**
- Net naming conventions differ (e.g., AVDD, DVSS)
- You want different severity thresholds

---

### `engine/parser.py`
**Role:** Netlist parsing  
**Purpose:** Converts raw netlist text into structured device objects.

**Currently supports:**
- MOSFETs
- Resistors
- Capacitors

**Change this file when:**
- Netlist syntax changes (Spectre, CDL, etc.)
- You want to parse additional devices (BJTs, sources, subcircuits)
- You want to extract sizing information (W/L)

---

### `engine/units_detect.py`
**Role:** Unit detection (structure recognition)  
**Purpose:** Identifies functional analog blocks using deterministic rules.

**Currently detects:**
- Diode-connected MOSFETs
- Simple current mirrors
- Differential pairs

**Change this file when:**
- You want to add new unit types (cascode, bias chain, gain stage)
- You want to improve pattern matching accuracy
- You want to reduce false positives

---

### `engine/dependency.py`
**Role:** Unit interaction modeling  
**Purpose:** Builds a dependency graph between units.

**Responsibilities:**
- Infer which units bias or affect others
- Compute downstream “blast radius”
- Estimate single-point-of-failure risk

**Change this file when:**
- Dependency inference is inaccurate
- You want to model signal paths or feedback loops
- You want better system-level impact logic

---

### `engine/health_checks.py`
**Role:** Unit robustness evaluation  
**Purpose:** Implements explainable health checks for each unit type.

**Examples of checks:**
- Fanout / loading
- Headroom proxies
- Symmetry / mismatch proxies
- Bias sensitivity proxies

Each check outputs:
- Severity
- Evidence
- Explanation

**Change this file when:**
- Weak-point detection is not convincing
- You want to add new checks
- You want to tune severity weights

👉 This is where **most product value grows**.

---

### `engine/ranking.py`
**Role:** Risk scoring and prioritization  
**Purpose:** Converts health checks + dependencies into ranked weak points.

**Implements:**
- Likelihood (from health checks)
- Impact (from dependency graph)
- Confidence (detection + inference)
- Final Risk = Likelihood × Impact × Confidence

**Change this file when:**
- Ranking feels wrong
- You want to emphasize impact over likelihood
- You want different explanation wording

---

### `engine/__init__.py`
**Role:** Package marker  
**Purpose:** Allows `engine` to be imported as a module.

Usually unchanged.

---

## `data/examples/`

### `data/examples/sample.sp`
**Role:** Example test netlist  
**Purpose:** Quick regression testing and demonstrations.

**Change this file when:**
- Testing new unit detection logic
- Reproducing bugs or false positives
- Adding new demo cases

---

## Design Philosophy

- **Explainable by design**  
  Every risk must have clear evidence.

- **Deterministic structure first, AI later**  
  Unit detection is rule-based; learning is layered on top.

- **Judgment, not simulation**  
  The engine mimics expert review, not SPICE.

- **Modular growth**  
  Each module can evolve independently without breaking the system.

---

## Where to Add New Features (Quick Guide)

- New unit type → `engine/units_detect.py`
- New weak-point logic → `engine/health_checks.py`
- New ranking strategy → `engine/ranking.py`
- New dependency logic → `engine/dependency.py`
- New outputs / UI → `main.py` or a new `report.py`

---

## Future Extensions (Planned)

- Cascode and gain-stage detection
- Bias network grouping
- SPICE-assisted checks (optional)
- JSON / UI export
- Learning-based ranking refinement

---

This document is intended to keep the project understandable
as it grows in complexity.