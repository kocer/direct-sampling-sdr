# Board D — Fabrication Notes

## Copper weight

Order board D with **2 oz (70 um) outer copper**. Do not order 1 oz.

In class A at 100 W the amplifier takes 6.67 A from the 50 V rail. On
1 oz copper, IPC-2221 asks about 4 mm of track width for that current at
a 20 C rise. A 4 mm track does not find a path on a crowded two-layer
board; the router ran for half an hour without finishing.

At 2 oz the same current at the same temperature rise needs 2.2 mm,
which routes. JLCPCB lists 2 oz outer copper as a standard option.

This is the correct choice for a 100 W amplifier for its own sake. The
copper also carries heat away from the device tabs.

## Other requirements

| Item | Value |
|---|---|
| Layers | 2 |
| Outer copper | 2 oz (70 um) |
| Thickness | 1.6 mm |
| Surface finish | ENIG |
| Minimum track | 0.25 mm |
| Minimum clearance | 0.3 mm |

The edge-mount connector pads reach the board outline. This is by
design. Do not pull them back.
