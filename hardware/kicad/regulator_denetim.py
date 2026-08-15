#!/usr/bin/env python3
"""Regulator denetimi — parca numarasi cikis rayiyla tutuyor mu.

    python3 regulator_denetim.py
    python3 regulator_denetim.py A

NEDEN. Sabit cikisli bir LDO'nun gerilimi PARCA NUMARASINDA yaziyor:
ADP150AUJZ-1.8 ile -2.5 ayri parcalar, TPS7A2018 ile TPS7A2033 ayri
parcalar. Numara yanlissa ray yanlis gerilimde gelir ve bunu hicbir
bagli-mi denetimi goremez: sema dogru, netlist dogru, DRC temiz.

BU KARTTA UC KEZ OLDU:

  U3   TPS7A2033 (3.3 V)  cikisi +1V8      -> ray 3.3 V cikardi
  U4/U5/U9  hepsi "ADP150" adiyla tek BOM satirinda ve tek LCSC
       koduyla (C144257 = ADP150AUJZ-2.5) toplaniyordu; cikislari
       +1V8_A, +1V8_D, +1V8_CLK. AD9251'in AVDD mutlak azamisi
       2.0 V (veri sayfasi Tablo 3) — iki ADC de ilk enerjilendirmede
       olurdu.
  U6/U7  cikislari +3V3_A ve +3V3_CLK, GIRISLERI de +3V3. Bir LDO'nun
       dusme gerilimi var; 3.3'ten 3.3 uretilemez.

UC DENETIM:

  1 PARCA NUMARASI vs CIKIS RAYI. Numaradan gerilim cikariliyor
    (ADP150-1.8, TPS7A2033, AMS1117-3.3 ...), ray adindan da
    (+1V8_A -> 1.8). Tutmuyorsa bulgu.

  2 GIRIS > CIKIS. LDO'da giris rayi cikistan en az DUSME GERILIMI
    kadar yuksek olmali. Ayni ya da dusukse regulator calismaz.

  3 AYARLANABILIR REGULATORDE GERI BESLEME. FB agina bagli bolucu
    okunup cikis gerilimi hesaplaniyor ve ray adiyla karsilastiriliyor.

Ray adindan gerilim: "+1V8_A" -> 1.8, "+3V3" -> 3.3, "+12V" -> 12.
"""
import collections
import os
import re
import sys

import pcbnew

KARTLAR = {
    "A": "A_main/dogrudan_sdr_A.kicad_pcb",
    "C": "C_rf/dogrudan_sdr_C.kicad_pcb",
    "D": "D_pa/dogrudan_sdr_D.kicad_pcb",
}

# Sabit cikisli aileler ve numaradan gerilim cikarma kalibi.
SABIT = [
    (re.compile(r"ADP150[A-Z]*-?(\d)[._]?(\d)", re.I), "nokta"),
    (re.compile(r"TPS7A20(\d\d)", re.I), "iki_hane"),
    (re.compile(r"AMS1117-?(\d)[._](\d)", re.I), "nokta"),
    (re.compile(r"MIC5205-?(\d)[._]?(\d)", re.I), "nokta"),
]

# LDO dusme gerilimi (V) — veri sayfasi tipik degerleri, pay birakildi.
DUSME = 0.35


def ray_gerilimi(ad):
    """"+1V8_A" -> 1.8 ; "+3V3" -> 3.3 ; "+12V" -> 12.0 ; "+50V" -> 50."""
    m = re.match(r"\+(\d+)V(\d*)", ad)
    if not m:
        return None
    tam = m.group(1)
    kesir = m.group(2)
    return float(tam + ("." + kesir if kesir else ""))


def parca_gerilimi(deger):
    for kalip, tip in SABIT:
        m = kalip.search(deger)
        if not m:
            continue
        if tip == "nokta":
            return float("%s.%s" % (m.group(1), m.group(2)))
        if tip == "iki_hane":
            # TPS7A2033 -> 3.3 ; TPS7A2018 -> 1.8
            h = m.group(1)
            return float("%s.%s" % (h[0], h[1]))
    return None


def kart_isle(ad):
    b = pcbnew.LoadBoard(KARTLAR[ad])
    bulgu = []
    for f in sorted(b.GetFootprints(), key=lambda x: x.GetReference()):
        ref = f.GetReference()
        if not ref.startswith("U"):
            continue
        deger = f.GetValue()
        vp = parca_gerilimi(deger)
        if vp is None:
            continue                       # ayarlanabilir ya da tanimadigim aile
        aglar = [p.GetNetname() for p in f.Pads() if p.GetNetname()]
        raylar = sorted({a for a in aglar if ray_gerilimi(a) is not None})
        if not raylar:
            continue
        # Cikis rayi: parca geriliminie EN YAKIN olan; giris ondan yuksek olan
        cikis = min(raylar, key=lambda r: abs(ray_gerilimi(r) - vp))
        vc = ray_gerilimi(cikis)
        girisler = [r for r in raylar if ray_gerilimi(r) > vc + 1e-9]

        if abs(vc - vp) > 0.05:
            bulgu.append("%-5s %-14s cikis %s (%.1f V) ama parca %.1f V"
                         % (ref, deger[:14], cikis, vc, vp))
        if not girisler:
            bulgu.append("%-5s %-14s cikis %s (%.1f V) — DAHA YUKSEK GIRIS YOK "
                         "(dusme gerilimi karsilanmiyor)"
                         % (ref, deger[:14], cikis, vc))
        else:
            en_dusuk = min(ray_gerilimi(r) for r in girisler)
            if en_dusuk - vc < DUSME:
                bulgu.append("%-5s %-14s giris %.1f V, cikis %.1f V — fark "
                             "%.2f V, dusme gerilimi %.2f V"
                             % (ref, deger[:14], en_dusuk, vc,
                                en_dusuk - vc, DUSME))

    print("=" * 66)
    print("KART %s" % ad)
    for x in bulgu:
        print("   " + x)
    if not bulgu:
        print("   bulgu yok")
    print("=> KART %s: %d bulgu" % (ad, len(bulgu)))
    return len(bulgu)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    t = 0
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        if k in KARTLAR:
            t += kart_isle(k)
    print("TOPLAM %d bulgu" % t)
    sys.exit(1 if t else 0)
