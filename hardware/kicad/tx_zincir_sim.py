#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""VERICI ZINCIRI — DAC cikisindan antene, imaj urunleriyle birlikte.

    python3 tx_zincir_sim.py

zincir_sim.py alis tarafini olcuyor: antenden ADC pinine. Bu arac
verici tarafini olcuyor: DAC'a bir sinyal verildiginde ANTENDEN NE
CIKIYOR. DAC'in ICI simule edilmiyor; sinir kosulu olarak sadece iki
sey aliniyor — ornekleme hizi ve sifir dereceli tutucu (ZOH) tepkisi.

SORUN. Ornekleyen bir DAC tek bir frekans uretmez. Sayisal frekans
f_d ise cikista |k*fs +/- f_d| noktalarinin HEPSI belirir. Bunlara
IMAJ deniyor ve genlikleri ZOH'un sinc tepkisiyle agirlikli:

    |H(f)| = |sin(pi f / fs) / (pi f / fs)|

sinc yavas duser. Istenen tasiyici Nyquist'e yakinsa kendisi zaten
bastirilmis olur, ve DAHA ALTTAKI bir imaj ondan GUCLU cikabilir.
Bu, tasarimin en sinsi hatasi: kart calisiyor gorunur, cikis gucu
dogru olcunur, ve verici yanlis frekansta yayin yapar.

BU KARTTA GERCEK BIR RISK, CUNKU FILTRE YOK:

  A kartinda DAC cikisinda sadece 50 ohm cift sonlandirma ve trafo
  var. gen_04_dac.py'de "Rekonstruksiyon filtresi (36 MHz LPF) ve
  surucu C KARTINDA" yaziyor — C kartinda OYLE BIR FILTRE YOK. TX
  orada SMA'dan girip dogrudan T/R rolesine ve antene gidiyor.

  Yani DAC imajlarinin onundeki tek suzgec, PA modunda D kartinin
  harmonik filtresi. Dusuk guc modunda (C karti uzerinden) hicbir
  suzgec yok.

IKI CALISMA MODU AYRI OLCULUYOR:

  4 kanal, fs = 40 MSPS/kanal. Nyquist 20 MHz. dac_cogullu.v'nin
  kisiti: IQWRT 80 MHz, iki evre. 20 MHz ustundeki her bant imajla
  yayinlanmak zorunda.

  2 kanal, fs = 80 MSPS. Sadece U30, cift port. Nyquist 40 MHz.

OLCUT: yasal sonyayilim siniri. 30 MHz altinda tasiyicinin en az
43 dB altinda, ustunde 60 dB. Ayni esikler lpf_sim.py'de kullaniliyor.

D kartinin filtresi lpf_sim'DEN aliniyor, kopyalanmiyor — arac
olctugu tasarimla ayni sey olmak zorunda.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lpf_sim                                            # noqa: E402

MODLAR = [("4 kanal", 40e6), ("2 kanal", 80e6)]

# DESTEKLENEN VERICI ZARFI — olcumun sonucu, dilek degil.
#
# Asagidaki (bant, mod) ikilileri sonyayilim sinirini geciyor. Digerleri
# GECMIYOR ve filtreyle de gecirilemiyor; sebepleri:
#
#   20_17m / 4 kanal   fs=40, tasiyici 18.2 MHz, ilk imaj 21.8 MHz.
#                      Arada 1.2 kat var. Oraya konacak centik bandin
#                      kendi ust kenarini da asagi ceker.
#
#   15_10m / 4 kanal   fs=40'ta 29.7 MHz Nyquist'in ustunde, yani
#                      tasiyicinin KENDISI imaj. Temel bilesen
#                      10.3 MHz'te ve sinc yuzunden tasiyicidan 10 dB
#                      GUCLU. Alcak geciren filtre altindakini kesemez.
#
#   6m / iki mod da    Ayni sebep. 80 MSPS'te bile 50-54 MHz Nyquist'in
#                      ustunde; temel bilesen 26-30 MHz'te ve 7 dB
#                      guclu. Bastirmak icin 0.9 oktavda 67 dB gereken
#                      bir bant geciren lazim — pratik degil.
#
# 6 m ALIS tarafi calisiyor ve iyi durumda (zincir_sim.py, katlanma
# bastirmasi 68 dB). Kisit sadece VERICI.
#
# Bu tablo bir mazeret degil, ARAC. Desteklenen bir ikili bozulursa
# arac hata veriyor; desteklenmeyen bir ikili tasarim degisip gecmeye
# baslarsa tabloyu guncellemek gerekiyor.
DESTEKLENEN = {
    "160m":   {"4 kanal", "2 kanal"},
    "80m":    {"4 kanal", "2 kanal"},
    "60m":    {"4 kanal", "2 kanal"},
    "40_30m": {"4 kanal", "2 kanal"},
    "20_17m": {"2 kanal"},
    "15_10m": {"2 kanal"},
    "6m":     set(),          # verici yok, sadece alis
}


def sinc_db(f, fs):
    """Sifir dereceli tutucunun genlik tepkisi (dB)."""
    if f <= 0:
        return 0.0
    x = math.pi * f / fs
    return 20 * math.log10(abs(math.sin(x) / x))


def sayisal_frekans(f0, fs):
    """Istenen cikis f0 icin NCO'nun uretmesi gereken sayisal frekans.

    f0 Nyquist'in altindaysa dogrudan f0. Ustundeyse en yakin
    katlanma: |f0 - k*fs|. O zaman f0 bir IMAJ olarak yayinlaniyor
    ve bu bilincli bir tercih (dac_cogullu.v'deki kisit).
    """
    k = round(f0 / fs)
    return abs(f0 - k * fs)


def imajlar(f_d, fs, kmax=6):
    """Cikista beliren butun frekanslar (Hz)."""
    out = set()
    for k in range(0, kmax + 1):
        for isaret in (+1, -1):
            f = k * fs + isaret * f_d
            if f > 0:
                out.add(round(f, 3))
    return sorted(out)


def lpf_tepkisi(ad, fc, t1, t2, centik=None):
    """D kartinin o bant filtresi. Doner: db(f_hz) fonksiyonu."""
    vals = lpf_sim.sentez(fc)
    v = lpf_sim.kos(lpf_sim.netlist(ad, vals, fc, (t1, t2), centik),
                    "tx_" + ad)
    if not v:
        return None

    def db(f):
        return min(v, key=lambda x: abs(x[0] - f))[1] + lpf_sim.BOLUCU
    return db


if __name__ == "__main__":
    print("VERICI ZINCIRI — DAC -> D karti harmonik filtresi -> anten")
    print("DAC imajlari: |k*fs +/- f_d|, ZOH sinc agirlikli")
    print()
    print("%-9s %-8s %7s %8s %9s %8s %7s  %s" %
          ("bant", "mod", "tasiyici", "sayisal", "en kotu", "seviye",
           "sinir", "durum"))
    kotu = 0
    for ad, fc, t1, t2, f_lo, f_hi, cn_f, cn_l in lpf_sim.BANTLAR:
        db = lpf_tepkisi(ad, fc, t1, t2, (cn_f, cn_l) if cn_f else None)
        if db is None:
            print("%-9s ngspice cikti vermedi" % ad)
            kotu += 1
            continue
        sinir = 60.0 if f_hi > 30.0 else 43.0
        for mod_ad, fs in MODLAR:
            en_kotu = (-300.0, 0.0, 0.0)
            for f0_mhz in (f_lo, (f_lo + f_hi) / 2, f_hi):
                f0 = f0_mhz * 1e6
                f_d = sayisal_frekans(f0, fs)
                if f_d < 1e3:
                    continue                  # DC'ye dusuyor, kullanilmaz
                tasiyici = sinc_db(f0, fs) + db(f0)
                for f in imajlar(f_d, fs):
                    if abs(f - f0) < 1e3:
                        continue
                    seviye = sinc_db(f, fs) + db(f) - tasiyici
                    if seviye > en_kotu[0]:
                        en_kotu = (seviye, f, f0)
            seviye, f_img, f0 = en_kotu
            f_d = sayisal_frekans(f0, fs)
            destekli = mod_ad in DESTEKLENEN.get(ad, set())
            if not destekli:
                durum = "desteklenmiyor (zarf disi)"
            elif -seviye < sinir:
                durum = "SONYAYILIM SINIRI ASILIYOR"
                kotu += 1
            else:
                durum = "OK"
            print("%-9s %-8s %6.1f M %6.1f M %7.1f M %7.1f %6.0f  %s" %
                  (ad if mod_ad == MODLAR[0][0] else "", mod_ad,
                   f0 / 1e6, f_d / 1e6, f_img / 1e6, seviye, sinir, durum))
    print()
    print("tasiyici: istenen cikis frekansi")
    print("sayisal : NCO'nun urettigi frekans (tasiyici Nyquist ustundeyse")
    print("          tasiyicinin kendisi bir imajdir)")
    print("en kotu : tasiyiciya en yakin seviyedeki imajin frekansi")
    print("seviye  : o imajin tasiyiciya gore seviyesi (dBc)")
    print()
    print("VERICI ZARFI: 160m-30m dort kanalli, 20m-10m iki kanalli.")
    print("6 m'de verici YOK (alis calisiyor). Gerekce icin DESTEKLENEN.")
    if kotu:
        print("DESTEKLENEN bir ikili sinirin altina dustu — %d adet" % kotu)
    sys.exit(1 if kotu else 0)
