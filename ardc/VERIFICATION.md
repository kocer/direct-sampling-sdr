# Verification evidence

Project `dogrudan-sdr`. Amateur radio club of TEVITOL, station
callsign YM2X.

**This file is generated.** `python3 ardc/topla.py` writes it. Each
number below comes from a tool that ran when the file was written.
If a tool fails, the script stops and no package is produced.

Date of this package: 2026-08-16

---

## 1. Schematic checks

These tools examine the schematic and the netlist. They find faults
that ERC cannot see, because ERC looks at the schematic alone.

| Check | Result |
|---|---|
| Symbol pins against footprint pads | pass |
| Pads with no net | pass |
| Netlist against the design intent | pass |
| Schematic rules | pass |
| Regulator part number against its rail | pass |

## 2. Circuit simulation

Connectivity can be correct while the values are wrong. These runs
measure the circuit, not the connections. Each one found a fault
that would have made a board unusable.

| Simulation | Result | Tool |
|---|---|---|
| Receive chain, antenna to ADC pin | pass | `kicad/zincir_sim.py` |
| Transmit harmonic filters | pass | `kicad/lpf_sim.py` |
| Transmit chain, DAC images | pass | `kicad/tx_zincir_sim.py` |
| PA bias servo, stability and fault | pass | `kicad/bias_sim.py` |
| Power distribution network impedance | pass | `kicad/pdn_sim.py` |
| Gain budget from device parameters | pass | `kicad/kazanc_butcesi.py` |
| Thermal budget | pass | `kicad/termal_hesap.py` |
| Tolerance and Monte Carlo | pass | `kicad/tolerans_sim.py` |

## 3. Gateware verification

| Item | Value |
|---|---|
| Checks that pass | 29 |
| Checks that fail | 0 |

The set includes module testbenches, a full-chip simulation with an
observer on every output pin, gate-level runs against the
synthesised netlist, a structural clock-domain-crossing check, and
three formal proofs. Each formal proof was tested by mutation: a
proof that passes but catches nothing gives false confidence.

## 4. Timing

| Clock | Achieved | Required | Result |
|---|---|---|---|
| adc1_dco | 164.20 MHz | 80.00 MHz | pass |
| adc2_dco | 168.01 MHz | 80.00 MHz | pass |
| clk_eth | 134.59 MHz | 125.00 MHz | pass |
| clk_sys | 86.57 MHz | 80.00 MHz | pass |
| rgmii_rxc | 140.06 MHz | 125.00 MHz | pass |

## 5. Bill of materials

| Board | Lines | Components |
|---|---|---|
| A | 80 | 303 |
| C | 60 | 404 |
| D | 113 | 252 |

Every line has a verified order code. A separate tool queries the
supplier and checks three things: the package and the value must
agree exactly, the stock must exceed the quantity, and the real
properties of the part must suit the circuit. That last check found
filter capacitors specified as X7R, and trap capacitors rated at
50 V in a position that carries 93 V.

Through-hole parts do not go into machine assembly. `ELLE_TAKILAN.md`
on board D lists them with the necessary specification.

## 6. Files in this package

| File | Content |
|---|---|
| `sema/` | Schematics of the three boards, PDF |
| `bom/` | Bill of materials of the three boards, CSV |
| `VERIFICATION.md` | This file |
| `README.md` | What the unit is and what it is for |
| `RATIONALE.md` | Why the four main design decisions were made |

The schematics and the bills of materials are regenerated from the
source of this package. They cannot be older than the design.
