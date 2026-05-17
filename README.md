# UnitScope (WIP)

UnitScope is a local analog circuit analysis tool for SPICE/CDL-style netlists.

It parses an analog netlist, detects common circuit building blocks, runs explainable robustness checks, and ranks potential weak points so designers can review fragile parts of a circuit faster.

The goal is not to replace SPICE simulation or expert analog review. UnitScope is intended to act as an early-stage static review assistant for analog IC designers, EDA engineers, and circuit reviewers.





<img width="1305" height="857" alt="MVP" src="https://github.com/user-attachments/assets/1a3645d2-f881-43be-a266-e59af9fad72b" />






## What It Does


UnitScope analyzes text-based netlists such as:

- `.sp`
- `.cdl`
- `.cir`
- `.net`

It detects analog functional units and reports:

- what circuit block was detected
- which devices belong to that block
- why the tool thinks the block exists
- what risks or weaknesses were found
- evidence from the original netlist
- a ranked risk score
- JSON and HTML reports

## Supported Analysis

Current detected unit types include:

- Diode-connected MOS devices
- Current mirrors
- Differential pairs
- Bias networks
- Tail current sources
- Cascode stacks
- Active load pairs
- Source followers

Current checks include:

- mirror sizing consistency
- body-tie consistency
- differential pair symmetry
- input pair sizing match
- tail node sanity
- tail bias control
- cascode bias presence
- stacked-device headroom risk
- bias fanout
- startup review for bias networks
- source follower body effect
- output swing review
- dependency/blast-radius estimation

## Why This Is Useful

Large analog netlists can be difficult to inspect manually. A designer may need to quickly answer questions like:

- Where are the major bias networks?
- Which current mirrors drive many other blocks?
- Are differential pair devices matched?
- Are there suspicious body ties?
- Are there stacked devices with headroom risk?
- Which units should be reviewed first?

UnitScope gives a first-pass explanation instead of only raw connectivity.

## Input Format

UnitScope expects a netlist, not a schematic image.

Example SPICE-style MOS line:

```spice
M1 out vin tail 0 NMOS w=10u l=180n m=1 nf=2
```

Format:

```text
Mname drain gate source bulk model parameters
```

Example passive lines:

```spice
R1 out vdd 10k
C1 out 0 1p
```

Supported parser features include:

- MOSFET parsing
- resistor parsing
- capacitor parsing
- `.SUBCKT` / `.ENDS` hierarchy labels
- continuation lines using `+`
- common SPICE suffixes such as `k`, `m`, `u`, `n`, `p`, `f`
- MOS parameters such as `w`, `l`, `m`, and `nf`
- raw source line and line number tracking

## Schematic Images

UnitScope does not directly analyze schematic images.

A schematic image usually does not contain reliable machine-readable information about:

- net connectivity
- device models
- transistor sizing
- hierarchy
- bulk connections
- simulator parameters

Recommended flow:

```text
EDA schematic -> export SPICE/CDL netlist -> analyze with UnitScope
```

Examples:

- Cadence Virtuoso: export a SPICE/CDL netlist
- LTspice: generate a SPICE netlist from the schematic
- KiCad/ngspice: export a SPICE netlist
- Xschem: generate a SPICE netlist

## Risk Scoring

Each detected unit receives:

- `L`: likelihood of weakness or fragility
- `I`: impact if the unit is problematic
- `C`: confidence in the detection and checks
- `Risk`: combined priority score

The score is currently computed as:

```text
Risk = L * I * C
```

Higher risk means the unit should be reviewed earlier.

## Output

The UI shows:

- ranked weak points
- unit type
- risk score
- likelihood, impact, and confidence
- device members
- line-level evidence
- detection explanation
- top health checks
- downstream blast-radius estimate

Reports can be exported as:

- JSON
- HTML

## Running The Tool

Install dependencies first. The main dependency is PySide6.

```bash
pip install PySide6
```

Run the app:

```bash
python main.py
```

Then:

1. Open a `.sp`, `.cdl`, `.cir`, or `.net` file.
2. Click **Analyze**.
3. Select a row in the ranked table.
4. Review the explanation and evidence.
5. Export JSON or HTML if needed.

## Project Structure

```text
main.py
app/
  ui_main.py
engine/
  api.py
  parser.py
  models.py
  units_detect.py
  health_checks.py
  dependency.py
  ranking.py
  utils.py
data/
  examples/
docs/
  ARCHITECTURE.md
```

## Main Modules

### `main.py`

Application entry point.

### `app/ui_main.py`

PySide6 desktop interface.

Handles:

- file selection
- analysis trigger
- results table
- unit detail panel
- JSON export
- HTML export
- dark glass-style UI theme

### `engine/parser.py`

Parses SPICE/CDL-style netlists into structured devices.

### `engine/models.py`

Defines core data objects:

- `Mosfet`
- `Passive`
- `Unit`

### `engine/units_detect.py`

Detects analog functional blocks from device connectivity.

### `engine/health_checks.py`

Runs explainable checks on each detected unit.

### `engine/dependency.py`

Builds heuristic dependency relationships between units.

### `engine/ranking.py`

Computes likelihood, impact, confidence, and final risk score.

### `engine/utils.py`

Shared helpers for:

- SPICE number parsing
- supply/ground detection
- severity labels
- MOS type inference
- sizing comparison

## Example

Input:

```spice
* Differential pair
M1 n1 vinp ntail 0 NMOS w=10u l=180n
M2 n2 vinn ntail 0 NMOS w=10u l=180n

* PMOS current mirror
M3 nref nref vdd vdd PMOS w=5u l=180n
M4 nbias nref vdd vdd PMOS w=5u l=180n

R1 n1 vdd 10k
C1 n2 0 1p
```

Possible detected units:

- differential pair: `M1`, `M2`
- diode-connected device: `M3`
- current mirror: `M3`, `M4`
- bias network around `nref`

## Limitations

UnitScope is a static analysis tool. It does not currently perform transistor-level simulation.

It cannot fully verify:

- DC operating point
- AC gain/phase margin
- transient startup
- noise
- mismatch Monte Carlo
- PVT corners
- layout-dependent effects
- real saturation/headroom margins without operating-point data

Some detections are heuristic and may produce false positives or miss advanced topology variants.

Use UnitScope as a review assistant, not as a signoff tool.

## Intended Users

UnitScope is designed for:

- analog IC designers
- mixed-signal engineers
- EDA tool developers
- circuit reviewers
- students learning analog topology recognition
- teams doing early-stage netlist sanity checks

## Roadmap Ideas

Possible future improvements:

- stronger Spectre/CDL compatibility
- hierarchical instance expansion
- support for BJTs, diodes, sources, and controlled sources
- better supply-domain detection
- schematic cross-probing
- waiver/suppression files
- rule configuration
- more topology detectors
- simulator-assisted operating-point checks
- integration with ngspice or commercial EDA flows
- report diffing between design revisions
- unit tests with realistic analog benchmark circuits

## License

See `LICENSE`.

## Disclaimer

UnitScope is intended to support engineering review. It does not guarantee circuit correctness, manufacturability, or signoff readiness. Always verify results with simulation, design review, and process-specific checks.
