# Direct-sampling SDR transceiver — ARDC technical annex

**Project:** a four-channel, phase-coherent, direct RF sampling transceiver
**For:** the amateur radio club of TEVITOL (Gebze, Kocaeli), station callsign **YM2X**
**Licence:** GPL-3.0 (gateware) · CERN-OHL-S v2 (hardware) · CC-BY-SA 4.0 (documents)

This folder is the technical annex of the ARDC grant application.

**Numbers are not written here.** They are in `VERIFICATION.md`, which
`ardc/topla.py` generates by running the tools and recording what they
report. A document that carries its own copy of the numbers becomes
old without anyone seeing it. That happened once in this project: the
bill of materials in this folder gave 150 nH for a filter inductor
when the board had 68 nH, after two redesigns.

---

## 1. What the unit does

There is no mixer and no intermediate frequency. The antenna goes to a
band-pass preselector and then to a 14-bit ADC that samples at
80 MSPS. All down-conversion, filtering and demodulation happen inside
the FPGA.

| Item | Value |
|---|---|
| Receive coverage | 1 MHz to 500 MHz (undersampling above 40 MHz) |
| Receive channels | 4, phase-coherent |
| Instantaneous window | 40 MHz per channel |
| Transmit coverage | 1.8 MHz to 30 MHz |
| Transmit power | 5 / 10 / 25 / 50 / 75 / 100 W, class A throughout |
| Clock | 80.000 MHz VCXO, less than 100 fs jitter, GPS disciplined |
| FPGA | Lattice ECP5 LFE5U-25F, caBGA-256 |
| Host interface | 2 × gigabit Ethernet |

The four phase-coherent channels are the distinctive property of the
design. `RATIONALE.md` gives the reason.

**The transmit envelope has limits.** A sampling DAC makes images as
well as the wanted frequency, and the images must be filtered. Four
channel transmit works from 160 m to 30 m. Two channel transmit works
from 160 m to 10 m. There is no transmit on 6 m: the band is above
Nyquist, the fundamental at 26 MHz to 30 MHz is stronger than the
carrier, and no practical filter removes it. Receive works on all
bands, 6 m included. Section 4.3.1 of `docs/DATASHEET.md` gives the
measurements.

---

## 2. The three boards

| Board | Role | Layers | Size |
|---|---|---|---|
| **A** — `A_main` | ADC, DAC, ECP5 FPGA, SDRAM, 2 × gigabit PHY, clock, power tree | 6 | 235 × 225 mm |
| **C** — `C_rf` | RF filter bank: 4 channels × 7 bands, protection, T/R, attenuator | 2 | 350 × 235 mm |
| **D** — `D_pa` | Power amplifier: class A 5 W to 100 W, bias servo, harmonic filter bank, SWR protection | 2 | 275 × 185 mm |

The boards connect through 2×10 and 1×6 headers. The RF paths use SMA.
Boards C and D take their shift-register data from one chain on board
A, so an added PA board needs no more pins from A.

---

## 3. Present state — the honest table

### Complete

- **Schematics.** All three boards are complete and ERC gives no
  violations. The schematics are not drawn by hand: each sheet comes
  from a Python generator (`gen_*.py`), so it is repeatable and it can
  be reviewed as source.
- **Part selection.** All three bills of materials have a verified
  order code on every line. A tool queries the supplier and checks the
  package, the value, the stock and the real properties of the part.
- **Gateware.** The Verilog RTL synthesises with Yosys and places with
  nextpnr-ecp5, and it produces a bitstream. All clocks meet their
  constraints.
- **Circuit simulation.** The receive chain, the transmit chain, the
  bias servo, the power distribution network and the thermal path are
  all simulated. Connectivity checks cannot see this class of fault.
- **Tolerance analysis.** The design is measured with real component
  tolerances and over temperature, by worst case and by Monte Carlo.
  Two filter positions were redesigned because of the result.
- **Formal verification.** Three properties are proven, and each proof
  was tested by mutation.

### Not complete — stated plainly

- **Routing is not finished.** The copper of the three boards is still
  in the automatic router. **No board in this package can go to
  manufacture.**
- **Five items need a measurement or a datasheet value.** The exposed
  pad dimensions of the RTL8211F and the AD8318, the AD8318 TADJ
  resistor at HF, the crystal stray capacitance, and the PE4312 series
  resistor timing. None of them is invented; where a choice was
  necessary, the safe direction was taken.
- **No board is built and nothing is measured.** The performance
  figures in `TASARIM.md` are calculations and datasheet values.

### Deliberately not in scope

- Enclosure, panel and cable harness design.
- Host-side software. The Ethernet packet format is defined.

---

## 4. Contents of this folder

```
ardc/
  README.md          this file
  VERIFICATION.md    generated: what ran, and what it reported
  RATIONALE.md       why direct sampling, why the ECP5, why four channels
  topla.py           the script that builds this package
  sema/              schematics of the three boards, PDF
  bom/               bills of materials of the three boards, CSV
```

Run `python3 ardc/topla.py` to rebuild the package. The script
regenerates the schematics and the bills of materials from the design
source, runs every verification tool, and writes `VERIFICATION.md`
with what they report. If a tool fails, the script says so and the
package is marked incomplete.

Related documents in the repository root: `docs/DATASHEET.md` (the
electrical specification, with the source of each row), `TASARIM.md`
(full design rationale, Turkish), `PA_TASARIM.md` (power amplifier),
`kicad/NETLIST.md` (the source of the net list).
