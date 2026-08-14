# Tools and Procedures

The schematics and the boards are not drawn by hand. Python scripts make
them. This document gives the procedure for each task.

## Prerequisites

| Item | Version |
|---|---|
| KiCad | 9 or later |
| Python | 3.11 or later |
| `pcbnew` Python module | From the KiCad installation |
| Java | 21, for the router |
| freerouting | 1.9.0 |

## Sequence

The tools operate in this order. Do not change the order.

1. `lib/gen_symbols.py` — makes the symbol library
2. `<board>/gen_NN_*.py` — makes each schematic sheet
3. `<board>/build.sh` — checks the schematics and makes the netlist
4. `pcb_kur.py` — makes the board from the netlist
5. `gercek_yerlesim.py` — puts each part at its position
6. `ayir.py` — separates the parts that touch
7. `ipek.py` — puts the silkscreen labels
8. `dsn_yaz.py` — writes the Specctra DSN file
9. freerouting — makes the tracks
10. `ses_oku.py` — reads the tracks into the board

**Warning:** Step 4 makes the board again from the netlist. This
removes all the tracks. Do the routing last. If you change the
placement, do the routing again.

## Two-pass ball assignment

The FPGA ball assignment needs the board geometry, and the geometry
needs the netlist. Thus the procedure has two passes.

1. Make the schematics and the board. Do the placement.
2. Run `ball_atama.py`. It writes `ball_atama.json`.
3. Make the schematics again. The generators read the JSON file.
4. Make the board again and do the placement again.

One pass is sufficient. The placement coordinates come from the floor
plan and not from the netlist, thus the second pass gives the same
positions.

## Tool reference

| Tool | Function |
|---|---|
| `pcb_kur.py` | Makes the board from the netlist |
| `gercek_yerlesim.py` | Puts each part at its position |
| `ayir.py` | Separates parts, pulls parts inside the outline |
| `ball_atama.py` | Calculates the FPGA ball assignment |
| `ecp5_saat.py` | Table of the clock-capable balls |
| `ipek.py` | Silkscreen labels |
| `dsn_yaz.py` | Writes the Specctra DSN file |
| `ses_oku.py` | Reads the Specctra SES file |
| `olc_yol.py` | Measures the bus crossings before the routing |
| `uzunluk_olc.py` | Measures the track length after the routing |
| `drc_duzelt.py` | Runs the design rule check and separates parts |
| `arayuz_kontrol.py` | Compares the connectors between the boards |
| `manyetik_hesap.py` | Calculates the transformer windings |
| `filtre_hesap.py` | Calculates the filter components |

## Why the DSN and SES tools exist

KiCad has `ExportSpecctraDSN` and `ImportSpecctraSES`. These functions
get the board from the graphical interface. In a script the functions
fail and they give no message.

The tools `dsn_yaz.py` and `ses_oku.py` do the same task in a script.

**Note:** The DSN format inverts the Y axis. KiCad increases Y downward
and the DSN increases Y upward. If you do not invert the axis, the
board becomes a mirror image.

## Limitation of pcbnew in a script

The `pcbnew` module gives incorrect objects after some operations. The
object has no methods and the script stops with an `AttributeError`.

Rules that prevent this:

- Read the board extents before you iterate the drawings.
- Do not call `LoadBoard` two times in one process.
- Use the footprint dictionary that you made at the start.
- Put an operation that needs a clean board in a separate process.

## Checks

Run these checks after each change.

| Check | Command |
|---|---|
| Electrical rules | `kicad-cli sch erc <board>.kicad_sch` |
| Design rules | `kicad-cli pcb drc <board>.kicad_pcb` |
| Bus crossings | `python3 olc_yol.py <board>.kicad_pcb` |
| Track length | `python3 uzunluk_olc.py <board>.kicad_pcb` |
| Board interfaces | `python3 arayuz_kontrol.py` |

The design rule check reports `copper_edge_clearance` errors. These
errors are correct: the edge-mount connector pads must touch the board
edge.

## Faults that the checks do not find

These faults passed the electrical rule check in this design. Look for
them by hand.

| Fault | Effect |
|---|---|
| A symbol and a footprint with different pin names | The nets do not connect to the pads |
| The same reference on two sheets | KiCad makes one part from two parts |
| A footprint with fewer pads than the symbol has pins | The extra pins disappear |
| A pad number that repeats in one footprint | The router does not see the other pads |
| A clock on a normal input/output | The timing does not close |

Each fault made a board that looked correct and that did not operate.
