#!/usr/bin/env python3
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

# (ad, kesim MHz, bandin en dusuk ve en yuksek calisma frekansi MHz)
BANTLAR = [
    ("160m",   2.2,  1.8,  2.0),
    ("80_60m", 6.0,  3.5,  5.3665),
    ("40_30m", 11.0, 7.0,  10.15),
    ("20_17m", 19.0, 14.0, 18.168),
    ("15_10m", 31.0, 21.0, 29.7),
    ("6m",     56.0, 50.0, 54.0),
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


def netlist(ad, vals, fc):
    s = ["* %s" % ad, "V1 in 0 AC 1", "Rs in n0 50"]
    dugum = "n0"
    n = 0
    for tipi, val in vals:
        n += 1
        if tipi == "C":
            s.append("C%d %s 0 %.4fp" % (n, dugum, val))
        else:
            yeni = "n%d" % n
            rs = 2 * math.pi * fc * 1e6 * val * 1e-9 / Q_BOBIN
            s.append("L%d %s m%d %.4fn" % (n, dugum, n, val))
            s.append("R%d m%d %s %.5f" % (n, n, yeni, max(rs, 1e-4)))
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
    print("D KARTI HARMONIK FILTRELERI — 5 kutup Chebyshev 0.1 dB")
    print("%-9s %6s %8s %9s %9s %9s  %s" %
          ("bant", "fc MHz", "kayip", "2.harm", "3.harm", "sinir", "durum"))
    kotu = 0
    for ad, fc, f_lo, f_hi in BANTLAR:
        vals = sentez(fc)
        v = kos(netlist(ad, vals, fc), ad)
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
