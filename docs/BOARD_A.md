# Board A — Main Board

Board A holds the converters, the FPGA, the clock and the host
interface. The board has 6 layers and it measures 235 x 225 mm.

## Layer stack

| Layer | Function |
|---|---|
| 1 | Signal, RF and high-speed |
| 2 | Ground |
| 3 | Signal |
| 4 | Power |
| 5 | Signal |
| 6 | Ground |

Layer 2 is a continuous ground plane. The plane has no split below the
ADC. A split in the ground below a converter makes the return current
go around the split. This adds inductance and it makes the noise worse.

## Receive chain

Each channel has these parts in this order:

1. SMA connector at the board edge
2. Termination resistor, 49.9 ohm
3. Transformer ADT1-1WT+, ratio 1:1
4. Two series resistors, one for each polarity
5. Differential capacitor
6. ADC input

The four chains have the same geometry. The distance from the SMA to
the transformer is 28.9 mm in all four chains. The distance from the
transformer to the ADC is 36.2 mm in all four chains.

The transformer makes the signal differential. The ADC needs a
differential input. The transformer also removes the direct current and
it isolates the antenna from the board ground.

**Note:** The ADT1-1WT+ has an impedance of 75 ohm. It is not 50 ohm.
The termination resistor corrects for this.

## Clock

The clock circuit has these parts:

| Reference | Part | Function |
|---|---|---|
| Y10 | VCXO | Makes the reference frequency |
| U15 | ADCLK846 | Divides the clock to the two ADCs |

The buffer U15 is at the same distance from each ADC. The distance is
30.0 mm to ADC 1 and 30.0 mm to ADC 2. The difference is 0.00 mm.

**Warning:** Do not move the clock buffer. A difference in the two
clock paths makes a phase error between the ADCs. You cannot calibrate
this error, because it changes with the temperature.

## FPGA banks

The peripherals are on the side of the FPGA bank that connects to them:

| Bank | Peripheral | Side of the FPGA |
|---|---|---|
| 0 | Control, SDRAM address overflow | Top |
| 1 | GPS, debug, transmit/receive control | Top |
| 2 | DAC 1 | Right, upper |
| 3 | Ethernet PHY 1 and 2 | Right, lower |
| 6 | ADC 1 and ADC 2 | Left, lower |
| 7 | SDRAM data | Left, upper |

## Ball assignment

The ball assignment is not alphabetical. A script calculates it from the
board geometry.

An ECP5 user input/output can change place with another input/output in
the same bank. Thus the assignment is a design choice. The script
projects the two ends of each bus on the axis that is at 90 degrees to
the bus. Then it sorts the two ends and it connects them in order. A
mapping in the same order cannot cross.

Result: 130 signals in 9 buses, 6 crossings. The 6 crossings are in the
four buses that contain a clock.

| Bus | Signals | Crossings | Mean length | Difference |
|---|---|---|---|---|
| ADC 1 | 16 | 0 | 59.5 mm | 7.8 mm |
| ADC 2 | 16 | 1 | 91.3 mm | 6.8 mm |
| SDRAM bank 7 | 25 | 0 | 61.3 mm | 17.7 mm |
| SDRAM bank 0 | 7 | 0 | 54.4 mm | 6.4 mm |
| DAC 1 port 1 | 14 | 0 | 86.5 mm | 8.7 mm |
| DAC 1 port 2 | 14 | 0 | 93.2 mm | 8.2 mm |
| DAC 2 | 14 | 0 | 63.3 mm | 8.0 mm |
| PHY 1 RGMII | 12 | 2 | 69.1 mm | 4.8 mm |
| PHY 2 RGMII | 12 | 3 | 92.6 mm | 1.7 mm |

The last column shows the difference between the longest signal and the
shortest signal. This is the quantity of meander that the routing must
add.

## Clock pins

Each clock connects to a clock-capable ball. The ECP5 calls these balls
PCLKT and PCLKC.

| Signal | Ball | Function of the ball |
|---|---|---|
| ADC1_DCO | M1 | PCLKT6_0 |
| ADC2_DCO | M2 | PCLKC6_0 |
| PHY1_RXC | M16 | PCLKT3_0 |
| PHY1_TXC | L16 | PCLKT3_1 |
| PHY2_RXC | M15 | PCLKC3_0 |
| PHY2_TXC | L15 | PCLKC3_1 |
| REF10_IN | B8 | PCLKC1_0 |
| SD_CLK_FPGA | J1 | PCLKT7_1 |

**Warning:** A clock on a normal input/output does not go directly into
the clock tree. It goes through the general routing and it collects
skew. The RGMII receive clock operates at 125 MHz. At this frequency
the timing does not close.

GPS_1PPS is on a normal input/output. This is correct. A signal at 1 Hz
does not go into the clock tree.

## Decoupling

Each decoupling capacitor is at the power pin that it decouples.

| Quantity | Value |
|---|---|
| Capacitors | 75 |
| Mean distance to the pin | 2.8 mm |
| Median distance | 2.7 mm |
| Maximum distance | 7.1 mm |
| Distance less than 3 mm | 52 |

The capacitors for the FPGA are on the bottom of the board. They are in
a grid with 2.5 mm between the positions. A capacitor at each ball is
not possible: the balls have 0.8 mm between them and a 0402 capacitor
needs 1.5 mm.

## Status indicators

| Reference | Color | Function |
|---|---|---|
| D60 | Green | The gateware operates and the PLL is locked |
| D61 | Blue | The receive chain makes data |
| D62 | Red | The transmitter operates |
| D63 | Yellow | Ethernet traffic |

The anode connects to +3V3. The FPGA pulls the cathode to ground. The
ECP5 input/output sinks more current than it sources. A 3.3 V bank
sinks 8 mA.

Each indicator has a 1 kilohm resistor. The current is 1.6 mA.
