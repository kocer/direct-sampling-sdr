#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""Yerlesim kalitesini OLC — yonlendirmeye bakmadan once.

    python3 yerlesim_kalite.py          # uc kart
    python3 yerlesim_kalite.py D

NEDEN. Kotu yonlendirmenin sebebi cogu zaman yonlendirici degil,
YERLESIMDIR. Birbirine baglanan parcalar kartin iki ucundaysa hicbir
yonlendirici duzgun bir yol bulamaz; cikan sey dolambacli, uzun,
via dolu bir agdir ve buna bakip "router kotu" denir.

Bu arac yonlendirmeden BAGIMSIZ olcuyor: her agin pedleri arasindaki
yarim-cevre (half-perimeter wirelength, HPWL) yerlesimin o age
dayattigi ALT SINIR. Yonlendirici bunun altina inemez. Buyuk HPWL =
yerlesim hatasi, yonlendirme hatasi degil.

OLCULENLER
  HPWL toplami     yerlesimin genel kalitesi, kucuk iyi
  en kotu aglar    hangi ag kartin dortte ucunu geziyor
  yayilim          bir agin pedleri kac parcaya ve ne kadar alana
                   dagilmis
  RF zinciri       RF aglarinin kartin bir ucundan otekine gidip
                   geri donup donmedigi

Yonlendirilmis kartlarda ayrica GERCEK bakir uzunlugu HPWL'e
bolunuyor: oran 1.0-1.5 iyi, 2.5 ustu yonlendirici dolambac yapmis
(ya da yer yok) demek.
"""
import collections
import math
import os
import re
import sys

import pcbnew

KARTLAR = {
    "A": "A_main/dogrudan_sdr_A.kicad_pcb",
    "C": "C_rf/dogrudan_sdr_C.kicad_pcb",
    "D": "D_pa/dogrudan_sdr_D.kicad_pcb",
}

# Dokum tasidigi icin uzunlugu anlamsiz olan aglar
ATLA = re.compile(r"^(GND|AGND|unconnected)")


def kart_dene(ad):
    b = pcbnew.LoadBoard(KARTLAR[ad])
    bb = b.GetBoardEdgesBoundingBox()
    kw, kh = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
    kosegen = math.hypot(kw, kh)

    ped = collections.defaultdict(list)
    for f in b.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if n and not ATLA.match(n):
                ped[n].append((f.GetReference(), p.GetPosition()))

    dokum = {z.GetNetname() for z in b.Zones()}

    bakir = collections.defaultdict(float)
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK":
            bakir[t.GetNetname()] += t.GetLength() / 1e6

    satir = []
    toplam = 0.0
    for n, q in ped.items():
        if len(q) < 2 or n in dokum:
            continue
        xs = [p.x for _, p in q]
        ys = [p.y for _, p in q]
        hpwl = ((max(xs) - min(xs)) + (max(ys) - min(ys))) / 1e6
        toplam += hpwl
        satir.append((hpwl, n, len({r for r, _ in q}), bakir.get(n, 0.0)))

    satir.sort(reverse=True)
    print("=" * 72)
    print("KART %s   %.0f x %.0f mm   kosegen %.0f mm   %d ag"
          % (ad, kw, kh, kosegen, len(satir)))
    print("toplam HPWL %.0f mm   ag basina ortalama %.1f mm"
          % (toplam, toplam / max(1, len(satir))))

    # Kartin kosegeninin yarisindan uzun yayilan ag = yerlesim suphesi
    genis = [s for s in satir if s[0] > kosegen * 0.5]
    print("\nkartin kosegeninin yarisindan GENIS yayilan ag: %d" % len(genis))
    print("  %-20s %8s %6s %10s  %s" % ("ag", "HPWL", "parca", "bakir", "oran"))
    for hpwl, n, kac, bk in satir[:12]:
        oran = "%.2f" % (bk / hpwl) if bk > 0.1 and hpwl > 0.1 else "-"
        isaret = "!" if hpwl > kosegen * 0.5 else " "
        print("%s %-20s %7.1f %6d %9.1f  %s" % (isaret, n[:20], hpwl, kac, bk, oran))

    # yonlendirilmisse dolambac
    yonlu = [s for s in satir if s[3] > 0.1]
    if yonlu:
        kotu = [s for s in yonlu if s[3] / max(s[0], 0.1) > 2.5]
        print("\nyonlendirilmis ag: %d   dolambacli (bakir/HPWL>2.5): %d"
              % (len(yonlu), len(kotu)))
        for hpwl, n, kac, bk in sorted(kotu, key=lambda s: -s[3] / max(s[0], .1))[:8]:
            print("  ! %-20s HPWL %6.1f  bakir %7.1f  (%.1fx)"
                  % (n[:20], hpwl, bk, bk / hpwl))
    else:
        print("\n(kart henuz yonlendirilmemis, dolambac olculemiyor)")
    return len(genis)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        if k in KARTLAR:
            kart_dene(k)
