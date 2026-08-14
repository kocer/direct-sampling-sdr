# Board C — RF Board

Board C holds the band filters, the transmit/receive relays and the
attenuators. The board has 2 layers and it measures 350 x 235 mm.

**Warning:** The board carries 100 W during transmission.

## Structure

The board has four channels. Each channel has seven bands.

| Position | Content | Y coordinate |
|---|---|---|
| Channel 1 | Antenna 1 to receiver 1 | 25 mm |
| Channel 2 | Antenna 2 to receiver 2 | 80 mm |
| Channel 3 | Antenna 3 to receiver 3 | 135 mm |
| Channel 4 | Antenna 4 to receiver 4 | 190 mm |

The four channels have the same geometry. Each part is at the same
relative position in its channel. Thus the four signal paths have the
same length.

| Measurement | Value in all four channels |
|---|---|
| SMA to band 1 | 41.0 mm |
| Band 1 to band 7 | 240.0 mm |
| Band 7 to the transmit/receive relay | 26.0 mm |
| Relay to the output | 40.9 mm |

**Warning:** Do not move one channel without the other three. The
value of this board is the phase relation between the four channels.

## Signal path in one channel

Receive:

1. The antenna connects to the SMA connector at the left edge.
2. The protection circuit limits the voltage.
3. The transmit/receive relay is not energized, thus it connects the
   antenna to the receive path.
4. The band filter removes the unwanted signals.
5. The attenuator PE4312 sets the level.
6. The signal goes to board A.

Transmit:

1. The signal comes from board A.
2. The transmit/receive relay is energized, thus it connects the
   transmit path to the antenna.
3. The antenna radiates the signal.

**Note:** The transmit path does not go through the band filter of
board C. Board D contains the low-pass filter for the transmit path.

## Connectors

Each channel has one antenna connector and two connectors to board A.

| Connector | Function |
|---|---|
| J1 to J4 | Antenna 1 to 4, left edge |
| J82 to J85 | Receive output to board A, right edge |
| J86 to J89 | Transmit input from board A, right edge |
| J80, J81 | Control, bottom edge |
| J90 | Control to board D, bottom edge |

## Protection

The receive path has three protection stages. Each stage operates on a
different time scale.

| Stage | Part | Event | Time |
|---|---|---|---|
| 1 | Gas discharge tube | Lightning, static | Microseconds |
| 2 | TVS diode | Fast transient | Nanoseconds |
| 3 | Diode limiter | Nearby transmitter | Continuous |

One stage cannot replace another stage. A transmitter can be near the
antenna. Thus all three stages are necessary.

The second pole of the transmit/receive relay connects the filter
return line to ground during transmission. This protects the front end
of the adjacent channel.

## Band filters

Each band uses a Chebyshev bandpass filter. The design targets a
reactance of 200 ohm at the resonator.

**Note:** Do not calculate the capacitance first. The first design
calculated the capacitance and it gave an inductance of 68 microhenry
for the 160 m band. No RF inductor has this value.

Two bands need toroid inductors. The other bands use SMD inductors.

| Band | Inductor type | Loss with SMD |
|---|---|---|
| 160 m | Toroid | 3.5 dB |
| 6 m | Toroid | 2.4 dB |
| Other bands | SMD | Acceptable |

The insertion loss follows this relation:

    IL = 4.343 x sum(g) x Qbp / Qu

The unloaded Q of the inductor sets the loss. An SMD inductor has a low
unloaded Q at the two ends of the frequency range.

## Relay control

The relay drivers are in one line at the bottom edge of the board. The
RF channels are above them.

**Note:** The pulse into a latching relay coil is some amperes. Do not
put this current next to an RF channel. The coil lines go up between the
band positions. There is 40 mm between the positions. The lines are on
an inner layer, below the ground plane.

| Reference | Part | Function |
|---|---|---|
| U60 to U66 | 74HC595 | Shift registers |
| U70 to U83 | DRV8833 | Relay drivers |
| KT1 to KT4 | G6K-2F-Y | Transmit/receive relays |

**Warning:** The transmit/receive relay is a single-side-stable type.
It is not a latching type. A latching relay keeps its position when it
has no power. If the power fails during transmission, a latching relay
keeps the antenna connected to the amplifier. Then 100 W can go into the
receiver input. A single-side-stable relay returns to the receive
position. The safe condition must come from the hardware and not from
the software.

The band relays are latching. This is correct: a band selection has no
safety function, and a latching relay uses no continuous coil power.
