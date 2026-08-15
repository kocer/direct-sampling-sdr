#!/usr/bin/env python3
"""Bant filtrelerini yeniden sentezle ve ngspice ile dogrula.

    python3 filtre_tasarim.py

NEDEN YENI TOPOLOJI. Karttaki filtre uc rezonatorlu TEPEDEN
KUPLAJLI bir yapi. O yapi DAR bant icindir: kuplaj kondansatorleri
rezonatore paralel binip frekansi asagi ceker ve genis bantta
kuplaj degerleri rezonator kapasitesiyle kiyaslanabilir hale gelip
eslesme bozulur.

Olculdu (filtre_sim.py, mevcut degerlerle): alti bandin da tepesi
gecirmesi gereken bandin ALTINDA ve bandin kendisi 24-41 dB
bastirilmis. Alici her bantta sagir.

Bu kartin pozisyonlari cok bantli: 80+60 m icin 3.5-5.4 MHz, yani
%44 oransal bant genisligi. Bu genislikte dogru yapi MERDIVEN bant
geciren:

    paralel LC --- seri LC --- paralel LC
       (sont)      (seri kol)     (sont)

Alcak geciren prototipten donusum:
    seri kol:  Ls = g*R0/(w0*w),  Cs = w/(g*R0*w0)
    sont kol:  Cp = g/(R0*w0*w),  Lp = w*R0/(g*w0)

g degerleri 3 kutuplu Chebyshev 0.1 dB dalgalanma.

BOBIN Q'SU HESABA KATILIYOR. Kayipsiz sentez her filtreyi kusursuz
gosterir; gercek kayip bobinin Q'sundan geliyor. Toroid 150, SMD 40.

DEGERLER E24'E OTURTULUYOR. Sentez 47.3 pF der, dunyada 47 pF var.
Oturtmadan once "kusursuz" gorunen bir tasarim, oturttuktan sonra
bozulabilir — o yuzden dogrulama E24 degerleriyle yapiliyor.
"""
import math
import re
import subprocess
import sys

R0 = 50.0
G3_CHEB = [1.0316, 1.1474, 1.0316]      # 3 kutup, 0.1 dB dalgalanma

# Pozisyon basina kapsanacak aralik (MHz) — amatör bantlari
KAPSAM = {
    "160m":   [(1.8, 2.0)],
    "80_60m": [(3.5, 3.8), (5.3515, 5.3665)],
    "40_30m": [(7.0, 7.2), (10.1, 10.15)],
    "20_17m": [(14.0, 14.35), (18.068, 18.168)],
    "15_10m": [(21.0, 21.45), (24.89, 24.99), (28.0, 29.7)],
    "6m":     [(50.0, 54.0)],
}
TIP = {"160m": "toroid", "80_60m": "toroid", "40_30m": "toroid",
       "20_17m": "smd", "15_10m": "smd", "6m": "smd"}
Q = {"toroid": 150.0, "smd": 40.0}

# E12 KULLANILIYOR, E24 DEGIL.
# E24 daha ince adimli ama stoklanma orani dusuk; E12 her
# ureticide ve JLCPCB kutuphanesinde bulunuyor. Sentezi E12'ye
# oturtup DOGRULAMAYI da E12 degerleriyle yapiyoruz — kagitta
# kusursuz, stokta olmayan bir tasarim ise yaramaz.
E24 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]


def e24(x):
    """En yakin E24 degeri (ayni buyukluk mertebesinde)."""
    if x <= 0:
        return x
    # ILK SURUM HER DEGERI 10'UN KUVVETINE YUVARLIYORDU.
    # "m / 10.0 * taban * 10" = m * taban, yani en kucuk aday zaten
    # bir ust dekada dusuyordu ve sentez sonucu 10000/1000/100 gibi
    # tuhaf yuvarlak sayilara oturuyordu. Sentez ciktisinin bu kadar
    # yuvarlak olmasi imkansiz; oradan yakalandi.
    us = math.floor(math.log10(x))
    taban = 10.0 ** us
    adaylar = ([m * taban / 10.0 for m in E24] +
               [m * taban for m in E24] + [taban * 10])
    return min(adaylar, key=lambda v: abs(v - x))


def sentez(ad):
    araliklar = KAPSAM[ad]
    lo = min(a[0] for a in araliklar) * 1e6
    hi = max(a[1] for a in araliklar) * 1e6
    # KENARLARA PAY. Tam bandin kenarina oturan bir filtre, parca
    # toleransi ile bandin icine kayar. %8 disari aciyoruz.
    lo /= 1.08
    hi *= 1.08
    f0 = math.sqrt(lo * hi)
    w = (hi - lo) / f0
    w0 = 2 * math.pi * f0
    kollar = []
    for i, g in enumerate(G3_CHEB):
        if i % 2 == 0:                       # sont rezonator
            Cp = g / (R0 * w0 * w)
            Lp = w * R0 / (g * w0)
            kollar.append(("sont", Lp, Cp))
        else:                                # seri kol
            Ls = g * R0 / (w0 * w)
            Cs = w / (g * R0 * w0)
            kollar.append(("seri", Ls, Cs))
    return f0, w, kollar


def netlist(ad, kollar, f0, oturt=True):
    q = Q[TIP[ad]]
    s = ["* %s" % ad, "V1 in 0 AC 1", "Rs in n0 50"]
    dugum = "n0"
    n = 0
    for tipi, L, C in kollar:
        n += 1
        Lv = e24(L * 1e9) if oturt else L * 1e9        # nH
        Cv = e24(C * 1e12) if oturt else C * 1e12      # pF
        # SERI DIRENC f0 ILE, SABIT 1 MHz ILE DEGIL.
        # Once "2*pi*1e6*L/q" yazmistim: 25 MHz'lik bir filtrede
        # kayip yirmi bes kat az cikiyordu ve sentez 0.02 dB gibi
        # imkansiz bir ekleme kaybi veriyordu. Q=40'lik bir bobinle
        # o deger fiziksel olarak mumkun degil; oradan yakalandi.
        rs = 2 * math.pi * f0 * (Lv * 1e-9) / q
        if tipi == "sont":
            s.append("L%d %s ml%d %.3fn" % (n, dugum, n, Lv))
            s.append("Rq%d ml%d 0 %.4f" % (n, n, max(rs, 1e-3)))
            s.append("C%d %s 0 %.3fp" % (n, dugum, Cv))
        else:
            yeni = "n%d" % n
            s.append("L%d %s ms%d %.3fn" % (n, dugum, n, Lv))
            s.append("Rq%d ms%d mc%d %.4f" % (n, n, n, max(rs, 1e-3)))
            s.append("C%d mc%d %s %.3fp" % (n, n, yeni, Cv))
            dugum = yeni
    s.append("Rl %s 0 50" % dugum)
    s.append(".ac dec 400 100k 300meg")
    s.append(".print ac vdb(%s)" % dugum)
    s.append(".end")
    return "\n".join(s)


def kos(nl, ad):
    yol = "/tmp/ft_%s.cir" % ad
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


BOLUCU = 6.02          # 1V kaynak + 50R: kayipsiz filtre -6.02 dB okur


if __name__ == "__main__":
    print("YENIDEN SENTEZ — merdiven bant geciren, 3 kutup Chebyshev 0.1 dB")
    print("%-9s %7s %6s | %-28s | %7s %8s %8s" %
          ("bant", "f0 MHz", "w", "kollar (L nH / C pF)", "kayip", "kenar", "2.harm"))
    kotu = 0
    tablo = []
    for ad in KAPSAM:
        f0, w, kollar = sentez(ad)
        nl = netlist(ad, kollar, f0)
        v = kos(nl, ad)
        if not v:
            print("%-9s ngspice cikti vermedi" % ad)
            kotu += 1
            continue
        tf, td = max(v, key=lambda x: x[1])
        td += BOLUCU

        def db(f):
            return min(v, key=lambda x: abs(x[0] - f))[1] + BOLUCU
        kenar = min(db(f * 1e6) for r in KAPSAM[ad] for f in r)
        h2 = db(2 * tf)
        ozet = " ".join("%s%.0f/%.0f" % (t[0][0].upper(), e24(L * 1e9),
                                         e24(C * 1e12))
                        for t, L, C in [(k, k[1], k[2]) for k in kollar])
        durum = "OK" if kenar > td - 3.0 else "KENAR %.1f dB" % (td - kenar)
        if kenar <= td - 3.0:
            kotu += 1
        print("%-9s %7.2f %6.2f | %-28s | %7.2f %8.2f %8.1f  %s" %
              (ad, f0 / 1e6, w, ozet, td, kenar, h2 - td, durum))
        tablo.append((ad, [(t, round(e24(L * 1e9), 1), round(e24(C * 1e12), 1))
                           for t, L, C in kollar]))
    print()
    for ad, k in tablo:
        print("  %-9s %s" % (ad, k))
    sys.exit(1 if kotu else 0)
