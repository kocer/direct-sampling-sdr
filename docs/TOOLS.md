# Tools

Every tool in this repository, with what it does.

**This file is generated.** `python3 docs/arac_listesi.py`
writes it from the first line of each tool's own
description. A hand-written list loses entries as tools are
added, and the reader cannot see that it happened.

## Schematic and netlist checks

| Tool | What it does |
|---|---|
| `kicad/temel_denetim.py` | Compares symbol pins against footprint pads |
| `kicad/ped_denetim.py` | Finds copper pads that have no net |
| `kicad/netlist_denetim.py` | Checks pin-to-net assignment from the schematic netlist |
| `kicad/sema_denetim.py` | Compares a symbol pin name against the net it carries |
| `kicad/regulator_denetim.py` | Checks each regulator part number against its output rail |
| `kicad/kondansator_denetim.py` | Checks capacitor value, package and voltage together |
| `kicad/ref_denetim.py` | Finds reference designator conflicts and silently lost parts |
| `kicad/arayuz_kontrol.py` | Checks the board-to-board connector agreement |
| `kicad/tedarik_denetim.py` | Verifies that every BOM line can be ordered, with the right properties |

## Circuit simulation

| Tool | What it does |
|---|---|
| `kicad/zincir_sim.py` | Simulates the receive chain from the antenna to the ADC pin |
| `kicad/tx_zincir_sim.py` | Simulates the transmit chain, including the DAC images |
| `kicad/lpf_sim.py` | Measures the harmonic filters of the power amplifier |
| `kicad/filtre_sim.py` | Measures the receive band filters |
| `kicad/filtre_tasarim.py` | Synthesises the receive band filters |
| `kicad/katlanma_tasarim.py` | Searches for a transmission zero against alias folding |
| `kicad/tolerans_sim.py` | Worst-case and Monte Carlo analysis over component tolerance |
| `kicad/bias_sim.py` | Simulates the PA bias servo: stability, start-up and fault |
| `kicad/pdn_sim.py` | Measures the impedance of the power distribution network |
| `kicad/kazanc_butcesi.py` | Computes the drive the final stage needs, from the devices |
| `kicad/termal_hesap.py` | Computes the thermal path and the heatsink requirement |
| `kicad/manyetik_hesap.py` | Computes the toroid winding and core for each inductor |
| `kicad/guc_yolu.py` | Checks trace width against the current it carries |

## Layout and routing

| Tool | What it does |
|---|---|
| `kicad/gercek_yerlesim.py` | Places the parts from the net list and the design rules |
| `kicad/plan_yerlesim.py` | Plans the placement regions |
| `kicad/kat_plani.py` | Defines the layer stack |
| `kicad/ayir.py` | Separates parts whose courtyards overlap |
| `kicad/elle_cek.py` | Pre-routes the connections that the router must not choose |
| `kicad/dikis.py` | Adds ground stitching vias |
| `kicad/ipek.py` | Places the silkscreen text |
| `kicad/montaj_isaret.py` | Adds fiducials and test points |
| `kicad/dsn_yaz.py` | Exports the design to the router, with the copper pours |
| `kicad/ses_oku.py` | Imports the routed result back into the board |
| `kicad/olc.py` | Measures the board: parts, nets, area |
| `kicad/olc_yol.py` | Measures placement quality by pad-to-pad distance |
| `kicad/uzunluk_olc.py` | Measures the real length of the routed traces, in bundles |
| `kicad/yerlesim_kalite.py` | Scores the placement |
| `kicad/drc_duzelt.py` | Corrects the design rule violations that can be corrected |
| `kicad/pcb_kur.py` | Builds the board file from the net list |
| `kicad/ecp5_saat.py` | Checks the FPGA clock pin assignment |
| `kicad/ball_atama.py` | Assigns the FPGA ball map |

## Gateware verification

| Tool | What it does |
|---|---|
| `gateware/formal/cdc_denetim.py` | Checks clock-domain crossings against the two-stage rule |

## Package assembly

| Tool | What it does |
|---|---|
| `ardc/topla.py` | Builds the ARDC package by running the tools |

## Licensing

| Tool | What it does |
|---|---|
| `kicad/telif.py` | The single source of the copyright and licence text |

Total: 43 tools.
