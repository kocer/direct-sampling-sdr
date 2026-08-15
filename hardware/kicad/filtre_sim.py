#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""C kartinin bant filtrelerini ngspice ile olc.

    python3 filtre_sim.py

NEDEN. Semanin BAGLANTISI dogru olmasi, DEGERLERININ dogru oldugunu
gostermiyor. Bir bant filtresinin kondansatoru yanlissa alici o
bantta sagir olur ve bunu ne ERC ne DRC ne de bir netlist denetimi
gorur — ancak olculur.

Filtre topolojisi (gen_03_filter.py):

    50R --Cu-- N1 --Ck-- N2 --Ck-- N3 --Cu-- 50R
               |         |         |
             L||Cr     L||Cr     L||Cr
               |         |         |
              GND       GND       GND

Uc rezonatorlu, tepeden kuplajli bant geciren.

BOBIN KAYIPSIZ DEGIL. Q girilmezse ekleme kaybi sifir cikar ve
filtre kusursuz gorunur. Toroid icin Q=150, SMD bobin icin Q=40
aliniyor (uretici veri sayfalari bu mertebeyi veriyor). Seri direnc
merkez frekansta R = 2*pi*f0*L/Q.

NE SORULUYOR:
  1 Tepe nerede — bandin icinde mi?
  2 Bant kenarlarinda ekleme kaybi ne? Alicida her dB dogrudan
    gurultu tabanina ekleniyor.
  3 Ikinci harmonikte bastirma ne? Verici tarafinda bu yasal bir
    sinir; alici tarafinda guclu bir yayin kanalini tikar.
"""
import os
import re
import subprocess
import sys

# gen_03_filter.py'deki tablo — (ad, L nH, Cr pF, Ck pF, Cu pF, tip)
BANTLAR = [
    ("160m",   16000, 430, 62,  270, "toroid"),
    ("80_60m",  7500, 180, 82,  390, "smd"),
    ("40_30m",  3900,  91, 33,  160, "smd"),
    ("20_17m",  2000,  51, 13,   56, "smd"),
    ("15_10m",  1300,  30, 10,   47, "smd"),
    ("6m",       620,  15, 1.3, 5.6, "toroid"),
]

# Her bandin kapsamasi gereken amatör telsiz araliklari (MHz).
KAPSAM = {
    "160m":   [(1.8, 2.0)],
    "80_60m": [(3.5, 3.8), (5.3515, 5.3665)],
    "40_30m": [(7.0, 7.2), (10.1, 10.15)],
    "20_17m": [(14.0, 14.35), (18.068, 18.168)],
    "15_10m": [(21.0, 21.45), (24.89, 24.99), (28.0, 29.7)],
    "6m":     [(50.0, 54.0)],
}

Q = {"toroid": 150.0, "smd": 40.0}


def netlist(ad, Ln, Cr, Ck, Cu, tip):
    L = Ln * 1e-9
    f0 = 1.0 / (2 * 3.141592653589793 * (L * Cr * 1e-12) ** 0.5)
    rs = 2 * 3.141592653589793 * f0 * L / Q[tip]
    s = [f"* {ad}"]
    s.append("V1 in 0 AC 1")
    s.append("Rs in n0 50")
    s.append(f"Cu1 n0 n1 {Cu}p")
    s.append(f"Ck1 n1 n2 {Ck}p")
    s.append(f"Ck2 n2 n3 {Ck}p")
    s.append(f"Cu2 n3 out {Cu}p")
    s.append("Rl out 0 50")
    for j in (1, 2, 3):
        s.append(f"L{j} n{j} m{j} {Ln}n")
        s.append(f"Rl{j} m{j} 0 {rs:.4f}")
        s.append(f"Cr{j} n{j} 0 {Cr}p")
    s.append(".ac dec 400 100k 300meg")
    s.append(".print ac vdb(out)")
    s.append(".end")
    return "\n".join(s)


def kos(ad, *p):
    nl = netlist(ad, *p)
    yol = "/tmp/f_%s.cir" % ad
    open(yol, "w").write(nl)
    r = subprocess.run(["ngspice", "-b", yol], capture_output=True, text=True)
    veri = []
    for satir in r.stdout.splitlines():
        m = re.match(r"\s*\d+\s+([\d.eE+-]+)\s+([-\d.eE+]+)", satir)
        if m:
            try:
                veri.append((float(m.group(1)), float(m.group(2))))
            except ValueError:
                pass
    return veri


# KAYNAK BOLUCUSU: 1 V'luk kaynak 50 ohm uzerinden eslesmis yuke
# 0.5 V verir, yani KAYIPSIZ filtre bile vdb(out) = -6.02 dB okur.
# Bunu dusmeden okursam her filtreye 6 dB fazla kayip yazarim —
# ilk kosuda tam bunu yaptim ve "her yapilandirmada 7 dB taban"
# diye tuhaf bir sonuc cikti. Gercek ekleme kaybi = vdb + 6.02.
BOLUCU_DB = 6.02


def db_at(veri, f):
    """f (Hz) civarinda en yakin noktanin dB'i."""
    if not veri:
        return None
    return min(veri, key=lambda x: abs(x[0] - f))[1]


if __name__ == "__main__":
    # BU ARAC ESKI TOPOLOJIYI OLCUYOR — GECERLI OLAN filtre_tasarim.py.
    # Kart tepeden kuplajli yapidan MERDIVEN bant gecirene gecti
    # (gen_03_filter.py). Buradaki model o degisikligi izlemiyor, yani
    # asagidaki "KENAR ZAYIF" satirlarinin hepsi kartta OLMAYAN bir
    # filtreye ait. Arac tarihsel kayit olarak duruyor: yeniden
    # sentezin gerekcesi olan olcum budur.
    print("** ESKI TOPOLOJI (tepeden kuplajli). Karttaki filtre icin "
          "filtre_tasarim.py kullan. **")
    print("C KARTI BANT FILTRELERI — ngspice AC analizi")
    print("%-9s %8s %8s %9s %9s  %s" %
          ("bant", "tepe MHz", "kayip dB", "kenar dB", "2.harm", "kapsam"))
    kotu = 0
    for b in BANTLAR:
        ad = b[0]
        veri = kos(*b)
        if not veri:
            print("%-9s  ngspice cikti vermedi" % ad)
            kotu += 1
            continue
        tepe_f, tepe_db = max(veri, key=lambda x: x[1])
        tepe_db += BOLUCU_DB
        # kapsanan araliklarin en kotu kenari
        enkotu = None
        for lo, hi in KAPSAM[ad]:
            for f in (lo, hi):
                d = db_at(veri, f * 1e6) + BOLUCU_DB
                if enkotu is None or d < enkotu[0]:
                    enkotu = (d, f)
        h2 = db_at(veri, 2 * tepe_f) + BOLUCU_DB
        durum = "OK"
        if enkotu[0] < tepe_db - 3.0:
            durum = "KENAR ZAYIF (%.1f dB tepeden asagi)" % (tepe_db - enkotu[0])
            kotu += 1
        print("%-9s %8.2f %8.2f %9.2f %9.1f  %s" %
              (ad, tepe_f / 1e6, tepe_db, enkotu[0], h2 - tepe_db, durum))
    sys.exit(1 if kotu else 0)
