# Direct-Sampling SDR

A direct-sampling software-defined radio transceiver and its power
amplifier for the amateur bands from 1.8 MHz to 54 MHz.

## What the equipment does

The receiver samples the antenna signal directly. It does not use a
mixer and it does not use an intermediate frequency. Four receive
channels operate at the same time. The four channels use one clock.
Thus the channels keep a constant phase relation.

The transmitter uses the same four channels in the opposite direction.
The power amplifier increases the transmit power to a maximum of 100 W.

| Item | Value |
|---|---|
| Frequency range | 1.8 MHz to 54 MHz |
| Receive channels | 4, phase coherent |
| Transmit channels | 4 |
| ADC | AD9251, 14 bit, 65 MSPS |
| DAC | AD9767, 14 bit, 125 MSPS |
| FPGA | Lattice ECP5 LFE5U-25F, BG256 |
| Filter bands | 7 for each channel |
| Amplifier power | 5, 10, 25, 50, 75 and 100 W |
| Amplifier class | A, at all power levels |
| Host interface | 2 x gigabit ethernet |
| Reference | 10 MHz external, or GPS |

## The three boards

| Board | Function | Size | Layers |
|---|---|---|---|
| A | Main board: ADC, DAC, FPGA, ethernet | 235 x 225 mm | 6 |
| C | RF board: filters, transmit/receive relays | 350 x 235 mm | 2 |
| D | Power amplifier: driver, finals, low-pass filters | 240 x 185 mm | 2 |

Board B does not exist. The first design had a separate clock board.
The clock circuit is now on board A, because the distance from the clock
to the ADC controls the phase accuracy.

## Signal path

The receive path:

1. The antenna connects to board C.
2. The band filter removes the unwanted signals.
3. The transmit/receive relay connects the filter to the receive path.
4. The attenuator sets the signal level.
5. Board A receives the signal.
6. The transformer makes the signal differential.
7. The ADC samples the signal.
8. The FPGA processes the samples.
9. The ethernet interface sends the data to the host.

The transmit path:

1. The host sends the data to board A.
2. The DAC makes the analog signal.
3. Board D receives the signal.
4. The driver stage increases the power.
5. The four final transistors increase the power to 100 W.
6. The low-pass filter removes the harmonics.
7. The directional coupler measures the forward and the reflected power.
8. The antenna radiates the signal.

## Why direct sampling

A superheterodyne receiver mixes the input signal to a lower frequency.
The mixer makes unwanted products. The local oscillator adds noise.
Each conversion stage adds distortion.

A direct-sampling receiver has none of these stages. The ADC samples the
antenna signal. The remaining signal path is digital, thus it is exact
and it does not change with the temperature.

The clock is the primary limit. The jitter of the clock sets the
maximum signal-to-noise ratio:

    SNR = -20 x log10(2 x pi x f x t_jitter)

At 30 MHz with 1 ps of jitter the limit is 74.5 dB. The ADC gives 70 dB.
Thus the clock must have less than 1 ps of jitter. The design uses a
VCXO and a fan-out buffer for this reason.

## Why four coherent channels

Four channels that share one clock keep a constant phase relation. This
makes these functions possible:

- Removal of a local noise source with a second antenna
- Measurement of the direction of a signal
- Increase of the antenna gain in one direction
- Measurement of meteor trails with two or more sites

A receiver with one channel cannot do these functions.

## Licenses

| Content | License |
|---|---|
| Hardware design | CERN-OHL-S-2.0 |
| Software and scripts | GPL-3.0 |
| Documentation | CC-BY-SA-4.0 |

## Repository content

| Directory | Content |
|---|---|
| `hardware/kicad/A_main` | Board A: schematic, PCB, generator scripts |
| `hardware/kicad/C_rf` | Board C |
| `hardware/kicad/D_pa` | Board D |
| `hardware/kicad/lib` | Symbols and footprints |
| `docs` | Design documentation |

The schematics are not drawn by hand. Python scripts make them. Each
script writes one sheet. To change a sheet, change the script and run
it again. The document `docs/TOOLS.md` gives the procedure.

## Status

The three schematics are complete. The electrical rule check finds no
errors. The placement is complete. The routing is in progress.

The FPGA gateware does not exist. This is the largest remaining task.
