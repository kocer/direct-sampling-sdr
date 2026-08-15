#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""Veri yolu demetlerini olc: kesisme, uzunluk, uzunluk farki.

KESISME NEDEN ONEMLI: iki hat sirasi iki ucta ters ise yollar
birbirini kesmek zorunda. Kesisme = via = katman degisimi = empedans
sicramasi ve ek gecikme. Paralel demet cizebilmek icin sifir olmali.

UZUNLUK FARKI: demetin en uzun ve en kisa hatti arasindaki fark.
Meander cekilecek miktar bu. Ne kadar kucukse o kadar az yer yiyor.
"""
import itertools, math, sys
import pcbnew
from ball_atama import YOLLAR, FPGA, pedler, eksen

MM = 1e6


def olc(pcb):
    b = pcbnew.LoadBoard(pcb)
    fpga = next(f for f in b.Footprints() if f.GetReference() == FPGA)
    ball = {p.GetNumber(): (p.GetPosition().x / MM, p.GetPosition().y / MM,
                            p.GetNetname()) for p in fpga.Pads()}
    fm = (fpga.GetPosition().x / MM, fpga.GetPosition().y / MM)
    tk = tu = 0
    for cevre, ad, netler in YOLLAR:
        cp = pedler(b, cevre)
        var = [n for n in netler if n in cp
               and any(v[2] == n for v in ball.values())]
        if len(var) < 4:
            continue
        cf = next(f for f in b.Footprints()
                  if f.GetReference() == cevre).GetPosition()
        e = eksen(fm, (cf.x / MM, cf.y / MM))
        poz = {n: (cp[n][e], next(v[e] for v in ball.values() if v[2] == n))
               for n in var}
        ters = sum(1 for x, y in itertools.combinations(var, 2)
                   if (poz[x][0] - poz[y][0]) * (poz[x][1] - poz[y][1]) < 0)
        uz = [math.dist(cp[n], next(v[:2] for v in ball.values()
                                    if v[2] == n)) for n in var]
        tk += ters
        tu += sum(uz)
        print(f"  {ad:9s} {len(var):2d} hat  kesisme {ters:3d}  "
              f"ort {sum(uz) / len(uz):5.1f} mm  fark {max(uz) - min(uz):5.1f}")
    print(f"TOPLAM kesisme {tk}, demet bakir {tu / 1000:.2f} m")
    return tk


if __name__ == "__main__":
    sys.exit(0 if olc(sys.argv[1]) == 0 else 0)
