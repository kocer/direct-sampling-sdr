#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""D kartinin harmonik filtrelerini ngspice ile olc.

    python3 lpf_sim.py

NEDEN. Verici tarafinda filtre degeri yanlissa sonuc yasal: harmonik
bastirma sinirin altina duser ve istasyon kurallara aykiri yayin
yapar. Kartta bunun hicbir belirtisi yoktur — cikis gucu dogru
gorunur, SWR dogru gorunur, ve yayilan harmonik ancak spektrum
analizoruyle gorulur.

Filtre 5 kutuplu Chebyshev 0.1 dB, C-L-C-L-C (gen_05_lpf.py).

SINIR. HF'te (30 MHz alti) sonyayilim tasiyicinin en az 43 dB
altinda olmali. 30 MHz ustunde sinir daha siki: 60 dB. Bu araç iki
esigi de bandin yerine gore uyguluyor.

BOBIN Q'SU HESABA KATILIYOR — kayipsiz sentez her filtreyi kusursuz
gosterir. D'nin filtreleri 100 W tasiyor ve toroid sarimli, Q=200.
Kondansator ESR'i ihmal ediliyor (C0G, kayip acisi 1e-3).
"""
import math
import re
import subprocess
import sys

Z0 = 50.0
G5 = [1.1468, 1.3712, 1.9750, 1.3712, 1.1468]     # 5 kutup, 0.1 dB
Q_BOBIN = 200.0

# (ad, kesim MHz, tuzak1 MHz, tuzak2 MHz, bant alt MHz, bant ust MHz)
#
# ARAC ESKI TASARIMI OLCUYORDU. Ilk surumu duz 5 kutuplu Chebyshev'i
# ve alti pozisyonu modelliyordu; kart o zamandan beri YEDI pozisyona
# gecti ve her seri bobinin uzerine bir TUZAK kondansatoru kondu
# (gen_05_lpf.py). Arac guncellenmeyince her bandi "YETERSIZ" diye
# raporluyordu — yani dogrulama araci, dogrulamasi gereken tasarimla
# ayni sey degildi. Bu, aracin hic olmamasindan kotudur: ya yanlis
# alarma alisilir ya da gercek bir bozulma bu gurultunun icinde
# kaybolur.
#
# Degerler gen_05_lpf.BANTLAR ile BIREBIR ayni olmali; oradaki
# kesim ve tuzak frekanslari degisirse burasi da degisecek.
BANTLAR = [
    ("160m",    2.3,   3.6,   5.4,   1.8,   2.0),
    ("80m",     4.3,   7.0,  10.5,   3.5,   3.8),
    ("60m",     6.2,  10.70, 16.05,  5.3515, 5.3665),
    ("40_30m", 14.1,  14.0,  21.0,   7.0,  10.15),
    ("20_17m", 22.4,  28.0,  42.0,  14.0,  18.168),
    ("15_10m", 39.7,  42.0,  63.0,  21.0,  29.7),
    ("6m",     58.8, 100.0, 150.0,  50.0,  54.0),
]

E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3,
       3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]


def e24(x):
    if x <= 0:
        return x
    us = math.floor(math.log10(x))
    t = 10.0 ** us
    ad = [m * t for m in E24] + [10.0 * t]
    return min(ad, key=lambda v: abs(v - x))


def sentez(fc_mhz):
    w = 2 * math.pi * fc_mhz * 1e6
    v = []
    for i, g in enumerate(G5):
        if i % 2 == 0:
            v.append(("C", e24(g / (Z0 * w) * 1e12)))
        else:
            v.append(("L", e24(g * Z0 / w * 1e9)))
    return v


# TUZAGIN KUCUK AYAGI SADECE BU DEGERLERDEN SECILEBILIR.
#
# Cift kondansator fikri dogruydu ama secim TEDARIKTEN KOPUKTU:
# e24_cift matematiksel olarak en yakin ikiliyi buluyordu ve bir
# tanesi 3.6 pF cikti. tedarik_denetim.py ile arandiginda 3.6 pF'nin
# 250 V sinifinda hicbir pakette stogu olmadigi gorüldü — yani
# tasarim, siparis edilemeyecek bir parcaya dayaniyordu.
#
# Gerilim sarti tesadufi degil: 100 W ve 50 ohm'da tasiyicinin tepe
# gerilimi 100 V, tuzak bobininin uzerinde ~93 V. 50 V'luk bir C0G
# katalogda ayni degeri gosterir ve delinir; hata ancak verici
# acildiginda anlasilir.
#
# Liste JLCPCB'de 0603 / 250 V+ / C0G-NP0 ve stogu olan E24
# degerlerinden cikarildi (tedarik_denetim.py). Yenilemek icin o
# araci kosup ayni suzgeci uygula. Eksikler: 3.6, 7.5, 62, 91.
KUCUK_STOK = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7,
              3.0, 3.3, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 8.2, 9.1,
              10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 24.0, 27.0, 30.0,
              33.0, 36.0, 39.0, 43.0, 47.0, 51.0, 56.0, 68.0, 75.0,
              82.0, 100.0]


def _e24_dizi(lo=1.0, hi=1e4):
    out, us = [], 0
    while 10.0 ** us <= hi:
        for m in E24:
            v = m * 10.0 ** us
            if lo <= v <= hi:
                out.append(round(v, 4))
        us += 1
    return sorted(out)


_DIZI = None


def e24_cift(x):
    """x'e en yakin IKI E24 degerinin toplami. Doner: (a, b).

    TEK BIR E24 KONDANSATORU TUZAGA YETMIYOR — OLCULDU.
    Tuzak dar bir cukur; kondansator %5 kayarsa cukurun dibi
    harmonikten kayiyor. 40/30 m bandinda tam deger 172 pF, en yakin
    E24 180 pF, cukur 14.0 yerine 13.7 MHz'e dusuyor ve ikinci
    harmonik bastirmasi 58 dB'den 39 dB'ye iniyor — yasal sinir 43 dB.
    Yani filtre "tasarlandigi gibi" degil, "siparis edilebildigi gibi"
    calisiyordu ve aradaki fark 19 dB.

    Iki kondansatoru paralel baglamak PA filtrelerinde standart: mika
    ve ATC parcalari zaten boyle stoklanir, ve iki E24 degerinin
    toplami hedefi genellikle tam tutturuyor (172 = 12 + 160).
    """
    global _DIZI
    if _DIZI is None:
        _DIZI = _e24_dizi()
    en_iyi = None
    for buyuk in _DIZI:
        if buyuk > x:
            break
        # KUCUK AYAK STOKTAN SECILIYOR, E24'ten degil. Ikisi ayni
        # sey degil: E24'te olan her deger 250 V sinifinda uretilmiyor.
        for kucuk in KUCUK_STOK:
            if kucuk > buyuk:
                break
            h = abs(buyuk + kucuk - x)
            if en_iyi is None or h < en_iyi[0]:
                en_iyi = (h, buyuk, kucuk)
    return (en_iyi[1], en_iyi[2])


def tuzak_pf(l_nh, f_mhz):
    """Bobine paralel tuzak kondansatoru — iletim sifiri f_mhz'te.

    gen_05_lpf.py AYNI fonksiyonu cagiriyor; yoksa arac kartta
    olmayan bir filtreyi olcer.
    """
    tam = 1.0 / ((2 * math.pi * f_mhz * 1e6) ** 2 * (l_nh * 1e-9)) * 1e12
    return sum(e24_cift(tam))


def netlist(ad, vals, fc, tuzaklar):
    s = ["* %s" % ad, "V1 in 0 AC 1", "Rs in n0 50"]
    dugum = "n0"
    n = 0
    bobin = 0
    for tipi, val in vals:
        n += 1
        if tipi == "C":
            s.append("C%d %s 0 %.4fp" % (n, dugum, val))
        else:
            yeni = "n%d" % n
            rs = 2 * math.pi * fc * 1e6 * val * 1e-9 / Q_BOBIN
            s.append("L%d %s m%d %.4fn" % (n, dugum, n, val))
            s.append("R%d m%d %s %.5f" % (n, n, yeni, max(rs, 1e-4)))
            # TUZAK BOBININ TAMAMINA PARALEL, sadece L'ye degil:
            # kartta kondansator bobinin iki UCUNA lehimleniyor ve
            # kayip direnci o dugumlerin arasinda kaliyor.
            ct = tuzak_pf(val, tuzaklar[bobin])
            s.append("Ct%d %s %s %.4fp" % (n, dugum, yeni, ct))
            bobin += 1
            dugum = yeni
    s.append("Rl %s 0 50" % dugum)
    s.append(".ac dec 500 100k 500meg")
    s.append(".print ac vdb(%s)" % dugum)
    s.append(".end")
    return "\n".join(s)


def kos(nl, ad):
    yol = "/tmp/lp_%s.cir" % ad
    open(yol, "w").write(nl)
    r = subprocess.run(["ngspice", "-b", yol], capture_output=True, text=True)
    v = []
    for satir in r.stdout.splitlines():
        m = re.match(r"\s*\d+\s+([\d.eE+-]+)\s+([-\d.eE+]+)", satir)
        if m:
            try:
                v.append((float(m.group(1)), float(m.group(2))))
            except ValueError:
                pass
    return v


BOLUCU = 6.02      # 1V kaynak + 50R: kayipsiz filtre -6.02 dB okur


if __name__ == "__main__":
    print("D KARTI HARMONIK FILTRELERI — 5 kutup Chebyshev 0.1 dB + tuzak")
    print("%-9s %6s %8s %9s %9s %9s  %s" %
          ("bant", "fc MHz", "kayip", "2.harm", "3.harm", "sinir", "durum"))
    kotu = 0
    for ad, fc, t1, t2, f_lo, f_hi in BANTLAR:
        vals = sentez(fc)
        v = kos(netlist(ad, vals, fc, (t1, t2)), ad)
        if not v:
            print("%-9s ngspice cikti vermedi" % ad)
            kotu += 1
            continue

        def db(f):
            return min(v, key=lambda x: abs(x[0] - f))[1] + BOLUCU
        # gecirme bandinda en kotu kayip
        kayip = min(db(f * 1e6) for f in (f_lo, (f_lo + f_hi) / 2, f_hi))
        # EN KOTU HARMONIK: bandin EN DUSUK frekansindan gelir, cunku
        # onun harmonigi filtrenin kesimine en yakin dusen olandir.
        h2 = db(2 * f_lo * 1e6)
        h3 = db(3 * f_lo * 1e6)
        sinir = 60.0 if f_hi > 30.0 else 43.0
        enkotu = max(h2, h3)
        durum = "OK"
        if -enkotu < sinir:
            durum = "YETERSIZ (%.0f dB, %.0f gerekiyor)" % (-enkotu, sinir)
            kotu += 1
        print("%-9s %6.1f %8.2f %9.1f %9.1f %9.0f  %s" %
              (ad, fc, kayip, h2, h3, sinir, durum))
    sys.exit(1 if kotu else 0)
