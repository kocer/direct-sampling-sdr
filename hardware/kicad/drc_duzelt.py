#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""DRC'nin bulduğu cakismalari dogrudan cozer.

    python3 drc_duzelt.py A_main/dogrudan_sdr_A.kicad_pcb

NEDEN AYRI ADIM: pcb_kur.py cakismayi kendi sinir-kutusu testiyle
sinamiyordu ve KiCad'in gercek courtyard COKGENI ile ayrisiyordu —
bir kartta fazla, otekinde eksik buluyordu. Iki farkli olcut yerine
GERCEK HAKEME gore duzeltiyoruz: DRC'yi kostur, bulduklarini ayir,
tekrarla.
"""
import os, re, subprocess, sys
import pcbnew

MM = 1000000


def drc(pcb):
    rpt = "/tmp/_dd.rpt"
    subprocess.run(["kicad-cli", "pcb", "drc", pcb, "-o", rpt,
                    "--severity-error"], capture_output=True)
    t = open(rpt, encoding="utf-8").read()
    ciftler = []
    blok = None
    for satir in t.split("\n"):
        m = re.match(r"\[(\w+)\]", satir)
        if m:
            blok = m.group(1)
            oge = []
            continue
        m = re.search(r"@\([\d.]+ mm, [\d.]+ mm\): (?:Footprint |.*? of )(\w+)",
                      satir)
        if m and blok in ("courtyards_overlap", "clearance",
                          "solder_mask_bridge", "shorting_items",
                          "pth_inside_courtyard", "npth_inside_courtyard"):
            oge.append(m.group(1))
            if len(oge) == 2 and oge[0] != oge[1]:
                ciftler.append(tuple(oge))
                oge = []
    return ciftler, t.count("[")


def ayir(pcb, tur=14):
    for t in range(tur):
        ciftler, _ = drc(pcb)
        if not ciftler:
            print(f"  tur {t}: cakisma yok")
            return 0
        b = pcbnew.LoadBoard(pcb)
        oynatildi = 0
        for ra, rb in ciftler:
            fa, fb = (b.FindFootprintByReference(ra),
                      b.FindFootprintByReference(rb))
            if fa is None or fb is None:
                continue
            pa, pb = fa.GetPosition(), fb.GetPosition()
            dx, dy = pb.x - pa.x, pb.y - pa.y
            if dx == 0 and dy == 0:
                dx = MM
            n = max(abs(dx), abs(dy))
            # kucuk olani oynat: buyuk cipler yerinde kalsin
            kucuk, buyuk = (fb, fa) if fb.GetArea() < fa.GetArea() else (fa, fb)
            isaret = 1 if kucuk is fb else -1
            adim = int(0.45 * MM)
            k = kucuk.GetPosition()
            kucuk.SetPosition(pcbnew.VECTOR2I(
                k.x + isaret * int(adim * dx / n),
                k.y + isaret * int(adim * dy / n)))
            oynatildi += 1
        b.Save(pcb)
        print(f"  tur {t}: {len(ciftler)} cift, {oynatildi} parca oynatildi")
    ciftler, _ = drc(pcb)
    return len(ciftler)


if __name__ == "__main__":
    for pcb in sys.argv[1:]:
        print(os.path.basename(pcb))
        kalan = ayir(pcb)
        print(f"  -> {kalan} cift kaldi")
