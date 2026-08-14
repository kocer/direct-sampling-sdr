# Board D — Power Amplifier

Board D increases the transmit power. The board has 2 layers and it
measures 240 x 185 mm.

**Warning:** The board operates at 50 V. The output is 100 W of radio
frequency energy. The heatsink becomes hot. Do not touch the board when
it operates.

## Power levels

The amplifier gives these output levels:

    5 W, 10 W, 25 W, 50 W, 75 W, 100 W

The amplifier operates in class A at each level. The bias current
changes with the level. The class does not change.

    Idq = Pout / (0.3 x Vcc)

| Output | Bias current | DC input |
|---|---|---|
| 5 W | 0.33 A | 17 W |
| 10 W | 0.67 A | 33 W |
| 25 W | 1.67 A | 83 W |
| 50 W | 3.33 A | 167 W |
| 75 W | 5.00 A | 250 W |
| 100 W | 6.67 A | 333 W |

**Note:** In class A the direct current does not change with the
signal. The amplifier takes the full current when there is no signal.
This is the cost of class A. The result is that the third-order
intermodulation stays low at all levels.

## Signal path

The signal goes from the left to the right. There is no return path.

| Reference | Part | Function |
|---|---|---|
| J10 | SMA | Input from board A |
| U10 | PE4312 | Digital attenuator, sets the drive level |
| U11 | PGA-103+ | Preamplifier |
| T12 | BN43-202, 2:3 | Driver output transformer |
| Q20, Q21 | IRF530N | Driver transistors |
| T10 | BN43-202, 3:1 | Final input transformer |
| Q10 to Q13 | IRFP250N | Final transistors, 4 |
| T11 | BN43-3312, 2:4 | Final output transformer |
| KL1 to KL7 | G2RL-2 | Low-pass filter selection |
| T20, T21 | FT50-43, 1:32 | Directional coupler |
| U30, U31 | AD8318 | Power detectors |
| J40 | Terminal | Antenna output |

## Thermal design

The four final transistors dissipate 233 W at 100 W of output. Each
transistor dissipates 58 W.

The four transistors are in one line at the top edge of the board. The
tab of each transistor points away from the board. Thus one copper bar
holds all four tabs.

**Warning:** The transistors must be in one line and they must have the
same thermal path. A transistor at a different temperature has a
different bias. A difference in the bias makes the intermodulation
worse.

## Symmetry

The amplifier uses a push-pull circuit. The two arms must be equal. If
the arms are not equal, the even harmonics do not cancel.

| Measurement | Value |
|---|---|
| Driver Q20 to final Q10 | 19.5 mm |
| Driver Q20 to final Q11 | 19.5 mm |
| Driver Q21 to final Q12 | 19.5 mm |
| Driver Q21 to final Q13 | 19.5 mm |
| Arm 1 to the output transformer | 73.3 mm |
| Arm 2 to the output transformer | 73.3 mm |

## Low-pass filter bank

The bank has 7 sections. Each section has a relay and a filter. The
filter is a Chebyshev type of the 5th order with 0.1 dB of ripple.

| Section | Band | Cut-off frequency |
|---|---|---|
| 1 | 160 m | 2.2 MHz |
| 2 | 80 m | 6.0 MHz |
| 3 | 40 m | 11 MHz |
| 4 | 30 m and 20 m | 19 MHz |
| 5 | 17 m and 15 m | 31 MHz |
| 6 | 12 m and 10 m | 56 MHz |
| 7 | 6 m | Bypass |

**Warning:** Use powdered-iron cores. Do not use ferrite cores. At
100 W a ferrite core saturates. A saturated core makes harmonics. The
filter must remove harmonics, thus a ferrite core defeats the filter.

The inductors of two adjacent sections are at 90 degrees to each other.
Two inductors in the same direction have a mutual inductance. Then the
signal of one band goes into the stop band of the other band.

The relays are the G2RL-2 type. The contact rating is 8 A at 250 VAC.

**Note:** A signal relay is not sufficient. At 100 W into 50 ohm the
current is 1.4 A and the peak voltage is 100 V. A 1 A signal relay welds
at the first operation.

## Measurement

The directional coupler gives two samples: the forward power and the
reflected power. Each sample goes to an AD8318 logarithmic detector.

The coupler ratio is -30 dB. At 100 W the sample is 100 mW, which is
+20 dBm. An attenuator of 20 dB follows. Thus the detector receives
0 dBm at 100 W and -30 dBm at 100 mW. The full power range is inside
the input range of the detector.

The TADJ pin of each detector has a 500 ohm resistor to ground. This
resistor sets the temperature correction.

**Note:** Do not connect TADJ directly to ground. The datasheet gives
no value of 0 ohm. Without the resistor the intercept moves with the
temperature. The amplifier dissipates 233 W, thus the temperature
changes. If the power measurement moves, the protection operates at the
wrong level.

The value of 500 ohm is the recommended value at four of the six
frequencies in the datasheet table. HF is below the table. Measure the
correct value during the temperature test.

## Antenna output

The signal goes from the coupler to terminal J40. A short coaxial cable
connects J40 to an SO-239 connector on the enclosure.

**Note:** The connector is on the enclosure and not on the board. The
station cables use PL-259 connectors. An adapter at each joint makes a
loss and it makes a contact that can fail.
