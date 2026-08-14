#!/usr/bin/env python3
"""Yerlesim kalitesi: ratsnest uzunlugu."""
import math, re, sys, pcbnew
ATLA = re.compile(r"^(GND|\+|VIN_PROT|CHASSIS|GND_HDR|GND_STRAP|GND_MODE)")
b = pcbnew.LoadBoard(sys.argv[1])
pos = {}
for fp in b.Footprints():
    for pad in fp.Pads():
        n = pad.GetNetname()
        if n and not ATLA.match(n):
            pos.setdefault(n, []).append((pad.GetPosition().x / 1e6,
                                          pad.GetPosition().y / 1e6))
tot = cnt = 0
uzun = []
for n, ps in pos.items():
    for i in range(len(ps) - 1):
        d = math.dist(ps[i], ps[i + 1]); tot += d; cnt += 1
        uzun.append((d, n))
uzun.sort(reverse=True)
print(f"{sys.argv[1].split('/')[-1]}: {cnt} baglanti, {tot:.0f} mm, "
      f"ort {tot/max(cnt,1):.1f} mm, en uzun {uzun[0][0]:.0f} mm ({uzun[0][1]})")
