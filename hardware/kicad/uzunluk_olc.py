#!/usr/bin/env python3
"""Cekilmis yollarin GERCEK uzunlugu, demet demet.

    python3 uzunluk_olc.py A_main/dogrudan_sdr_A.kicad_pcb

olc_yol.py ile karistirilmasin: o, yerlestirme kalitesini olcuyor ve
ped-ped KUS UCUSU mesafeye bakiyor. Bu ise yonlendirici bittikten
sonra calisiyor ve izlerin gercekten kat ettigi yolu topluyor.
Ikisi arasindaki fark yonlendiricinin ne kadar dolastigini gosterir.

NE ISE YARIYOR: uzunluk esitleme. Paralel bir veri yolunda butun
hatlar ayni anda varmali; aradaki fark dogrudan zamanlama butcesini
yiyor. 6 katmanli FR4'te ic katmanda sinyal ~180 ps/inc, yani

    1 mm fark ~= 7 ps

DDR sinifi bir SDRAM arayuzunde butce birkac yuz ps; 20 mm fark
140 ps demek ve tek basina butcenin buyuk kismini yer. Meander
cekilecek miktari bu arac soyluyor.

VIA'YI DA SAY: her via kart kalinligi kadar dikey yol ekliyor
(1.6 mm) ve daha onemlisi katman degistiriyor — ic katmanla dis
katmanin yayilim hizi ayni degil. Burada via'lar geometrik olarak
sayiliyor; hiz farki icin katman basina ayri raporlaniyor.
"""
import collections
import math
import os
import sys

import pcbnew

MM = 1e6
KART_KALINLIK = 1.6      # mm, JLCPCB standart


def ag_uzunluklari(b):
    """net adi -> (bakir uzunlugu mm, via sayisi, katman kumesi)"""
    uz = collections.defaultdict(float)
    via = collections.Counter()
    kat = collections.defaultdict(set)
    for t in b.GetTracks():
        n = t.GetNetname()
        if not n:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            via[n] += 1
            uz[n] += KART_KALINLIK
            continue
        a, c = t.GetStart(), t.GetEnd()
        uz[n] += math.dist((a.x / MM, a.y / MM), (c.x / MM, c.y / MM))
        kat[n].add(pcbnew.LayerName(t.GetLayer()))
    return {n: (uz[n], via[n], kat[n]) for n in uz}


def demet_raporu(pcb):
    b = pcbnew.LoadBoard(pcb)
    veri = ag_uzunluklari(b)
    if not veri:
        print("Kartta hic iz yok — once yonlendir, sonra olc.")
        return
    try:
        from ball_atama import YOLLAR, SAAT_AGLARI
    except Exception:
        YOLLAR, SAAT_AGLARI = [], set()

    toplam_meander = 0.0
    for _, ad, netler in YOLLAR:
        var = [(n, veri[n]) for n in netler if n in veri
               and n not in SAAT_AGLARI]
        if len(var) < 4:
            continue
        uzunluk = [u for _, (u, _, _) in var]
        enb = max(uzunluk)
        fark = enb - min(uzunluk)
        gerek = sum(enb - u for u in uzunluk)
        toplam_meander += gerek
        vias = sum(v for _, (_, v, _) in var)
        print(f"  {ad:9s} {len(var):2d} hat  "
              f"ort {sum(uzunluk) / len(uzunluk):6.1f} mm  "
              f"fark {fark:5.1f} mm ({fark * 7:4.0f} ps)  "
              f"via {vias:3d}  meander gereken {gerek:6.1f} mm")
        # en kisa uc hat: meander bunlara cekilecek
        for n, (u, _, _) in sorted(var, key=lambda x: x[1][0])[:3]:
            if enb - u > 0.5:
                print(f"        {n:14s} {u:6.1f} mm, +{enb - u:5.1f} mm gerek")
    print(f"  TOPLAM cekilecek meander: {toplam_meander:.0f} mm")

    # demete girmeyen ama kritik olanlar
    print("\n  SAAT HATLARI (kendi aralarinda esit olmali degil, ama")
    print("  ciftlerin — RXC/TXC gibi — birbirine yakin olmasi iyi):")
    for n in sorted(SAAT_AGLARI):
        if n in veri:
            u, v, k = veri[n]
            print(f"    {n:14s} {u:6.1f} mm, {v} via, {'/'.join(sorted(k))}")


if __name__ == "__main__":
    for pcb in sys.argv[1:]:
        print(os.path.basename(pcb))
        demet_raporu(pcb)
