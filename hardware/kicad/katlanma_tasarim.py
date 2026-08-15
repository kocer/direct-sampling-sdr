#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""KATLANMA BASTIRMASI — bant filtrelerine iletim sifiri arayan tasarimci.

    python3 katlanma_tasarim.py            # butun bantlari degerlendir
    python3 katlanma_tasarim.py 15_10m     # tek bant icin deger ara

SORUN. Dogrudan ornekleyen alicida ADC'nin onunde tek koruma bant
filtresidir. 80 MSPS'te Nyquist 40 MHz; f > 40 MHz'teki her sinyal
|f - 80| olarak banda KATLANIR ve katlandiktan sonra istenen
sinyalden ayirt edilemez. Sayisal tarafta duzeltmenin yolu yoktur —
bilgi ornekleme aninda kaybolmustur.

zincir_sim.py ile olculdu, iki bant kaliyor:

    15_10m   50.3 MHz -> 29.7 MHz    24 dB    (50.3 MHz = 6 m bandi)
    6m       30.0 MHz -> 50.0 MHz    37 dB    (30 MHz = 10 m ustu)

Birincisi ciddi: kendi vericimiz 6 m'de calisirken 10 m alicisinin
tam ustune duser.

IKI SORUN AYNI ILACI ISTEMIYOR — bu isin puf noktasi:

  15_10m'de girisim bandin USTUNDE. Seri kolu bandin ustunde bir
  frekansta ACIK DEVRE yapmak gerekiyor. Seri bobine paralel
  kondansator (D kartinin harmonik tuzaklariyla ayni fikir):

      Ls || Ct  ->  paralel rezonans ft'de -> seri kol acik -> sifir

  6m'de girisim bandin ALTINDA. Ayni ilac ISE YARAMAZ: bir seri kol
  tuzagi sifiri her zaman gecirme bandinin ustune koyar, ve ft'nin
  ustunde kol kapasitif olur — yani bandi bozar. Alttaki bir sifir
  icin SONT kolu o frekansta KISA DEVRE yapmak gerekiyor. Sont
  bobine SERI kondansator:

      (Lp + Cx) || Cp  ->  seri rezonans fz'de -> sont kisa -> sifir

TASARIM ARAMAYLA YAPILIYOR, FORMULLE DEGIL. Sifir eklemek gecirme
bandini da bozuyor: seri kol tuzagi bant icinde bobini BUYUK
gosteriyor (L/(1-(f/ft)^2)), sont kola seri kondansator da rezonansi
kaydiriyor. Kapali formulle "sonra telafi ederim" demek yerine
butun degerler (E12) birlikte taraniyor ve olcut ikili:

    gecirme bandi: en kotu kayip <= 3 dB, duzluk <= 2 dB
    katlanma:      en kotu bastirma >= 45 dB

Cevap zincirin TAMAMI uzerinden okunuyor (zayiflatici, trafo, seri
direncler, ADC kapasitesi dahil) — filtreyi tek basina olcmek yanlis
cevap verir, zincir_sim.py'nin basindaki nota bak.

HIZ. Arama analitik (ABCD carpimi, karmasik sayi); kazanan deger
ngspice ile AYRICA dogrulaniyor. Ikisi tutmuyorsa bu da bir bulgudur
ve arac bagirir — tek bir hesap yontemine guvenmiyoruz.
"""
import cmath
import math
import re
import subprocess
import sys

FS = 80e6
Q_BOBIN = 40.0
R_SERI = 33.0
C_DIF = 22e-12
C_ADC = 6e-12
ATT_KAYIP_DB = 1.5

DUZLUK_ESIK = 2.0       # bant ici tepe-cukur farki (dB)
KATLANMA_ESIK = 45.0    # katlanan sinyal en az bu kadar altta (dB)

# EKLEME KAYBI ESIGI BANDA GORE — tek sayi kullanmak aramayi bozdu.
#
# Ilk surumde butun bantlara 3 dB dayattim ve 6 m'de "cozum yok"
# cikti. Sebep tasarim degil, esikti: 6 m'in MEVCUT kaybi zaten
# 5.45 dB. Yani arama bos bir kumede geziyordu ve bunu "topoloji
# yetmiyor" diye okumak yanlis olurdu.
#
# 5.45 dB'nin sebebi fizik: bobin kaybi frekansla artiyor ve Q=40'lik
# SMD bobinle 50 MHz'te bu kadar oluyor. Bant filtresinin kaybi
# dogrudan alicinin gurultu katsayisina biniyor; HF'te onemi az
# (gurultu tabanini atmosfer belirliyor) ama 50 MHz'te atmosferik
# gurultu cok dustugu icin onemi buyuk. Esigi gevsetiyoruz ama
# kaybi puanliyoruz: ayni katlanma bastirmasini veren iki adaydan
# kaybi dusuk olani seciliyor.
KAYIP_ESIK = {"6m": 7.0}
KAYIP_VARSAYILAN = 3.0

E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]

KAPSAM = {
    "160m":   [(1.8, 2.0)],
    "80_60m": [(3.5, 3.8), (5.3515, 5.3665)],
    "40_30m": [(7.0, 7.2), (10.1, 10.15)],
    "20_17m": [(14.0, 14.35), (18.068, 18.168)],
    "15_10m": [(21.0, 21.45), (24.89, 24.99), (28.0, 29.7)],
    "6m":     [(50.0, 54.0)],
}

# mevcut tasarim: (Lp nH, Cp pF, Ls nH, Cs pF)
MEVCUT = {
    "160m":   (1000, 6800, 18000, 390),
    "80_60m": (1000, 1200,  3300, 390),
    "40_30m": ( 470,  680,  2200, 180),
    "20_17m": ( 220,  470,  1500,  68),
    "15_10m": ( 150,  270,   680,  56),
    "6m":     (  33,  270,   820,  12),
}


def e12_yakin(x, alt=0.5, ust=2.0):
    """x'in etrafindaki E12 degerleri (alt..ust kati araliginda)."""
    out = []
    us = math.floor(math.log10(max(x, 1e-12))) - 1
    for k in range(us, us + 4):
        for m in E12:
            v = m * 10.0 ** k
            if x * alt <= v <= x * ust:
                out.append(round(v, 6))
    return sorted(set(out))


# ---------------------------------------------------------------- ABCD
def seri(z):
    return ((1.0, z), (0.0, 1.0))


def sont(y):
    return ((1.0, 0.0), (y, 1.0))


def carp(a, b):
    return ((a[0][0] * b[0][0] + a[0][1] * b[1][0],
             a[0][0] * b[0][1] + a[0][1] * b[1][1]),
            (a[1][0] * b[0][0] + a[1][1] * b[1][0],
             a[1][0] * b[0][1] + a[1][1] * b[1][1]))


def z_bobin(w, l_h):
    """Kayipli bobin: Q sabit alinmiyor, seri direnc 10 MHz'te
    hesaplanip sabit tutuluyor (uretici verisi boyle veriliyor)."""
    r = 2 * math.pi * 10e6 * l_h / Q_BOBIN
    return complex(max(r, 1e-3), w * l_h)


def z_kond(w, c_f):
    return complex(0.0, -1.0 / (w * c_f)) if c_f > 0 else complex(1e12, 0)


def paralel(z1, z2):
    return z1 * z2 / (z1 + z2)


def tepki(f_hz, p):
    """Zincirin tamami: 50R kaynak -> filtre -> zayiflatici -> trafo
    -> 33R -> C -> ADC. Doner: dB, eslesmis referansa gore."""
    w = 2 * math.pi * f_hz
    Lp, Cp, Ls, Cs, Ct, Cx = p

    # sont kol: Cx varsa bobinle SERI (alt tarafa sifir acar)
    zl = z_bobin(w, Lp * 1e-9)
    if Cx:
        zl = zl + z_kond(w, Cx * 1e-12)
    z_sont = paralel(zl, z_kond(w, Cp * 1e-12))

    # seri kol: Ct varsa bobine PARALEL (ust tarafa sifir acar)
    zs = z_bobin(w, Ls * 1e-9)
    if Ct:
        zs = paralel(zs, z_kond(w, Ct * 1e-12))
    z_seri = zs + z_kond(w, Cs * 1e-12)

    m = carp(carp(sont(1.0 / z_sont), seri(z_seri)), sont(1.0 / z_sont))

    # filtre cikisi 50 ohm'a bakiyor (zayiflaticinin girisi)
    zl_att = complex(50.0, 0)
    a, b = m[0]
    c, d = m[1]
    # gerilim orani: V2/V1 = ZL / (A*ZL + B)
    v_filt = zl_att / (a * zl_att + b)
    # kaynak 50 ohm: giris empedansindan bolucu
    z_in = (a * zl_att + b) / (c * zl_att + d)
    v_giris = z_in / (z_in + 50.0)

    # zayiflatici: kayip, sonra 50 ohm kaynak empedansiyla trafoyu surer
    g_att = 10 ** (-ATT_KAYIP_DB / 20.0)

    # trafo 1:1 diferansiyel; yuk = 2*33R seri + (22+6)pF diferansiyel
    z_c = z_kond(w, (C_DIF + C_ADC))
    z_yuk = 2 * R_SERI + z_c
    v_tr = z_yuk / (50.0 + z_yuk)          # 50R kaynaktan bolucu
    v_adc = z_c / z_yuk                    # direncler uzerinden bolucu

    v = v_giris * v_filt * g_att * v_tr * v_adc
    # eslesmis referans: 50R kaynak + 50R yuk -> 0.5. Ona gore dB.
    return 20 * math.log10(abs(v) / 0.5 + 1e-30)


def katlanan(lo, hi, bolge=5):
    fs = FS / 1e6

    def sayisal(f):
        k = round(f / fs)
        return abs(f - k * fs)
    d_lo, d_hi = sorted((sayisal(lo), sayisal(hi)))
    out = []
    for k in range(0, bolge + 1):
        for isaret in (+1, -1):
            for d in (d_lo, (d_lo + d_hi) / 2, d_hi):
                f = k * fs + isaret * d
                if f <= 0.05 or lo - 0.05 <= f <= hi + 0.05:
                    continue
                out.append(round(f, 4))
    return sorted(set(out))


def degerlendir(ad, p):
    """(kayip, duzluk, katlanma_bastirma, en_kotu_frekans)."""
    # BANT ICI IZGARA SIK OLMALI. Once 9 nokta kullaniyordum ve
    # analitik hesapla ngspice kayipta 1.9 dB ayristi: dar ve keskin
    # tepeli bir filtrede seyrek izgara tepeyi kaciriyor. Kayipta bu
    # kotumser tarafa hata, zarari yok; ama DUZLUK ayni sebeple
    # OLDUGUNDAN KUCUK cikiyor, yani dalgali bir filtreyi duz sanip
    # kabul edebilirdik. Izgara siklastirildi.
    ic = []
    for lo, hi in KAPSAM[ad]:
        n = 40
        for i in range(n + 1):
            ic.append(tepki((lo + (hi - lo) * i / n) * 1e6, p))
    tepe = max(ic)
    kayip = -tepe
    duzluk = tepe - min(ic)
    en_kotu, ff = -300.0, 0.0
    for lo, hi in KAPSAM[ad]:
        for f in katlanan(lo, hi):
            a = tepki(f * 1e6, p) - tepe
            if a > en_kotu:
                en_kotu, ff = a, f
    return kayip, duzluk, -en_kotu, ff


def ara(ad):
    """Bant icin (Lp,Cp,Ls,Cs,Ct,Cx) ara. Doner: en iyi aday ya da None."""
    Lp0, Cp0, Ls0, Cs0 = MEVCUT[ad]
    lo0 = min(l for l, h in KAPSAM[ad])
    hi0 = max(h for l, h in KAPSAM[ad])
    # girisim bandin ustunde mi altinda mi — sifiri nereye acacagimizi
    # bu belirliyor
    kf = katlanan(lo0, hi0)
    en_yakin = min(kf, key=lambda f: min(abs(f - lo0), abs(f - hi0)))
    ustte = en_yakin > hi0

    esik_kayip = KAYIP_ESIK.get(ad, KAYIP_VARSAYILAN)
    # mevcut tasarimdan DAHA KOTU bir kayba razi olmuyoruz
    k0, _, _, _ = degerlendir(ad, (Lp0, Cp0, Ls0, Cs0, 0, 0))
    esik_kayip = max(esik_kayip, k0 + 0.5)

    if ustte:
        # seri kola tuzak: ft ~ en yakin katlanan frekans
        ct0 = 1.0 / ((2 * math.pi * en_yakin * 1e6) ** 2 * (Ls0 * 1e-9)) * 1e12
        ct_ad = e12_yakin(ct0, 0.55, 1.9)
        cx_ad = [0]
    else:
        # sont kola seri kondansator: fz ~ en yakin katlanan frekans
        #
        # ARALIK GENIS TUTULUYOR. Formulun verdigi Cx sadece BASLANGIC:
        # o kondansator Cp ile birlikte sont kolun kutbunu da
        # kaydiriyor, yani sifiri dogru yere koyan deger bandi dogru
        # gecirense ayni deger olmak zorunda degil. Ikisini birlikte
        # tarayip olcuyoruz.
        cx0 = 1.0 / ((2 * math.pi * en_yakin * 1e6) ** 2 * (Lp0 * 1e-9)) * 1e12
        cx_ad = e12_yakin(cx0, 0.3, 3.5)
        ct_ad = [0]

    en_iyi = None
    for Ls in e12_yakin(Ls0, 0.4, 1.6):
        for Cs in e12_yakin(Cs0, 0.6, 2.6):
            for Lp in e12_yakin(Lp0, 0.4, 2.6):
                for Cp in e12_yakin(Cp0, 0.4, 2.6):
                    for Ct in ct_ad:
                        for Cx in cx_ad:
                            p = (Lp, Cp, Ls, Cs, Ct, Cx)
                            k, d, b, f = degerlendir(ad, p)
                            if k > esik_kayip or d > DUZLUK_ESIK:
                                continue
                            # once katlanma esigini gecenler, sonra
                            # en dusuk kayip
                            puan = (min(b, 70.0), -k)
                            if en_iyi is None or puan > en_iyi[0]:
                                en_iyi = (puan, p, (k, d, b, f))
    return en_iyi


# ---------------------------------------------------- ngspice dogrulama
def ngspice_dogrula(ad, p):
    Lp, Cp, Ls, Cs, Ct, Cx = p
    rq_p = 2 * math.pi * 10e6 * (Lp * 1e-9) / Q_BOBIN
    rq_s = 2 * math.pi * 10e6 * (Ls * 1e-9) / Q_BOBIN
    s = ["* %s dogrulama" % ad, "V1 ant 0 AC 1", "Rs ant f0 50"]
    for i, n in ((1, "f0"), (2, "f1")):
        # sont kol
        s.append("Lp%d %s mp%d %.4fn" % (i, n, i, Lp))
        if Cx:
            s.append("Rp%d mp%d xp%d %.4f" % (i, i, i, max(rq_p, 1e-3)))
            s.append("Cx%d xp%d 0 %.4fp" % (i, i, Cx))
        else:
            s.append("Rp%d mp%d 0 %.4f" % (i, i, max(rq_p, 1e-3)))
        s.append("Cp%d %s 0 %.4fp" % (i, n, Cp))
    s.append("Ls1 f0 ms1 %.4fn" % Ls)
    s.append("Rs1 ms1 mc1 %.5f" % max(rq_s, 1e-3))
    if Ct:
        s.append("Ct1 f0 mc1 %.4fp" % Ct)      # bobinin IKI UCUNA
    s.append("Cs1 mc1 f1 %.4fp" % Cs)
    s.append("Rl_filt f1 0 50")
    s.append("Eatt attx 0 f1 0 %.6f" % (10 ** (-ATT_KAYIP_DB / 20.0)))
    s.append("Ratt attx a0 50")
    s.append("Etr sp 0 a0 0 0.5")
    s.append("Etrn sn 0 a0 0 -0.5")
    s.append("Rp sp vp %.3f" % R_SERI)
    s.append("Rn sn vn %.3f" % R_SERI)
    s.append("Cd vp vn %.4fp" % ((C_DIF + C_ADC) * 1e12))
    s.append("Rin vp vn 100k")
    s.append(".ac dec 600 500k 500meg")
    s.append(".print ac vdb(vp,vn)")
    s.append(".end")
    yol = "/tmp/kat_%s.cir" % ad
    open(yol, "w").write("\n".join(s))
    r = subprocess.run(["ngspice", "-b", yol], capture_output=True, text=True)
    v = []
    for satir in r.stdout.splitlines():
        m = re.match(r"\s*\d+\s+([\d.eE+-]+)\s+([-\d.eE+]+)", satir)
        if m:
            try:
                v.append((float(m.group(1)), float(m.group(2)) + 6.02))
            except ValueError:
                pass
    if not v:
        return None

    def db(f):
        return min(v, key=lambda x: abs(x[0] - f * 1e6))[1]
    ic = [db(lo + (hi - lo) * i / 8.0)
          for lo, hi in KAPSAM[ad] for i in range(9)]
    tepe = max(ic)
    en_kotu = max(db(f) - tepe
                  for lo, hi in KAPSAM[ad] for f in katlanan(lo, hi))
    return -tepe, tepe - min(ic), -en_kotu


if __name__ == "__main__":
    hedefler = sys.argv[1:] or list(MEVCUT)
    print("KATLANMA BASTIRMASI — %.0f MSPS, esik %.0f dB"
          % (FS / 1e6, KATLANMA_ESIK))
    print()
    print("%-9s %26s %7s %7s %8s" %
          ("bant", "mevcut (Lp Cp Ls Cs)", "kayip", "duzluk", "katlanma"))
    duzeltilecek = []
    for ad in hedefler:
        Lp, Cp, Ls, Cs = MEVCUT[ad]
        k, d, b, f = degerlendir(ad, (Lp, Cp, Ls, Cs, 0, 0))
        bayrak = "" if b >= KATLANMA_ESIK else "  <-- YETERSIZ"
        print("%-9s %26s %6.2f %6.2f %7.1f dB (%.1f MHz)%s"
              % (ad, "%g %g %g %g" % (Lp, Cp, Ls, Cs), k, d, b, f, bayrak))
        if b < KATLANMA_ESIK:
            duzeltilecek.append(ad)

    if not duzeltilecek:
        print("\nbutun bantlar esigi geciyor")
        sys.exit(0)

    print("\nARAMA — %s" % ", ".join(duzeltilecek))
    for ad in duzeltilecek:
        print("\n--- %s" % ad)
        r = ara(ad)
        if r is None:
            print("    bu topolojiyle olcutleri karsilayan deger BULUNAMADI")
            continue
        _, p, (k, d, b, f) = r
        Lp, Cp, Ls, Cs, Ct, Cx = p
        print("    Lp %g nH  Cp %g pF  Ls %g nH  Cs %g pF" % (Lp, Cp, Ls, Cs))
        print("    %s" % ("Ct %g pF (seri bobine PARALEL, ust tarafa sifir)"
                          % Ct if Ct else
                          "Cx %g pF (sont bobine SERI, alt tarafa sifir)" % Cx))
        print("    analitik : kayip %.2f dB  duzluk %.2f dB  katlanma %.1f dB "
              "(%.1f MHz)" % (k, d, b, f))
        ng = ngspice_dogrula(ad, p)
        if ng is None:
            print("    ngspice  : cikti vermedi")
            continue
        nk, nd, nb = ng
        print("    ngspice  : kayip %.2f dB  duzluk %.2f dB  katlanma %.1f dB"
              % (nk, nd, nb))
        fark = max(abs(nk - k), abs(nd - d), abs(nb - b))
        if fark > 3.0:
            print("    DIKKAT: iki yontem %.1f dB ayrisiyor — birine guvenme"
                  % fark)
