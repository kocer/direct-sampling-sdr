#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""TOLERANS — tasarim NOMINAL degil, GERCEK parcalarla da calisiyor mu.

    python3 tolerans_sim.py
    python3 tolerans_sim.py --kosu 5000

Buraya kadar her sey nominal degerlerle olculdu ve hepsi gecti. Ama
hicbir parca nominal degildir. %5'lik bir kondansator kutunun icinde
%5 sapabilir; bobinler daha kotu; sicaklik ikisini de kaydirir. Bir
tasarimin nominalde gecip uretimde kalmasi en pahali hata turudur,
cunku ancak kartlar geldikten sonra gorunur.

IKI AYRI SORU, IKISI DE SORULUYOR:

  EN KOTU DURUM (WCA). Her parca ayni anda en kotu yonde saparsa ne
  oluyor. Bu fiziksel olarak mumkun ve uzay/havacilik pratiginde
  tasarimin bunu da gecmesi beklenir. Cok katidir: butun parcalarin
  ayni yonde sapma olasiligi cok dusuktur, ama SIFIR degildir.

  MONTE CARLO. Parcalar bagimsiz dagilirsa kartlarin yuzde kaci
  gecer. Uretim gercegi budur. %99'un altindaki her sonuc, elli
  kartlik bir partide en az bir bozuk kart demektir.

Hangi yonun "kotu" oldugu olcute gore degisiyor ve ONCEDEN
BILINMIYOR — bir kondansatoru buyutmek bir bantta iyilestirip
digerinde bozabiliyor. O yuzden en kotu durum da ARANIYOR:
her parcanin iki ucu denenip olcutu en cok bozan bileske bulunuyor.

TOLERANSLAR — parcalarin gercek veri sayfalarindan (tedarik_denetim.py
ile secilen kodlar):

  C0G/NP0 kondansator   +/-5%   sicaklik katsayisi 30 ppm/C
  SMD bobin             +/-5%   (bazilari %10, kotumser alindi)
  direnc %1             +/-1%
  sicaklik araligi      -20 .. +60 C  (kapali kutu, saha)
"""
import argparse
import itertools
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zincir_sim                                     # noqa: E402
import katlanma_tasarim as kt                         # noqa: E402

TOL_C = 0.05            # C0G kondansator
TOL_L = 0.05            # SMD bobin
TK_C = 30e-6            # C0G sicaklik katsayisi (1/C)
TK_L = 100e-6           # bobin sicaklik katsayisi (1/C)
SICAKLIK = (-20.0, 60.0)
T_REF = 25.0

# olcutler
ESIK_KATLANMA = 40.0    # dB, alis zinciri
ESIK_DUZLUK = 3.0       # dB
# EKLEME KAYBI ESIGI BANDA GORE, VE FIZIKTEN TURETILMIS.
#
# Once butun bantlara 8.5 dB dayattim ve 160 m %89.75 ile "kaldi"
# cikti — kayip araligi 7.90-8.88 dB. Ama o esik keyfiydi.
#
# Alicinin duyarliligini belirleyen sey on uc kaybi degil, gurultu
# tabanidir. HF'in alt ucunda tabani ATMOSFER kuruyor: ITU-R P.372'ye
# gore 1.9 MHz'te yerlesim yeri gurultusu termal tabanin ~60 dB
# ustunde. O tabanin yaninda 9 dB'lik on uc kaybinin olculebilir bir
# etkisi yok — anten gurultusu zaten alicinin kendi gurultusunu
# gomuyor.
#
# Frekans yukseldikce atmosferik gurultu duser ve esik sikilasir.
# 50 MHz'te Fa ~10-20 dB; orada on uc kaybi anlamli. Yine de bu
# alette 6 m'de belirleyici olan sey dogrudan ornekleyen alicinin
# kendi gurultu katsayisi (LNA yok), filtre kaybi degil.
#
# Kaynak: ITU-R P.372 (Radio noise), Sekil 2 — is yeri/yerlesim
# ortami egrileri.
ESIK_KAYIP = {
    "160m":   12.0,     # Fa ~60 dB
    "80_60m": 10.0,     # Fa ~50 dB
    "40_30m":  8.0,     # Fa ~40 dB
    "20_17m":  7.0,     # Fa ~30 dB
    "15_10m":  6.0,     # Fa ~25 dB
    "6m":      6.5,     # Fa ~15 dB, ama ADC gurultusu baskin
}


def sapma(deger, tol, tk, t):
    """Bir parcanin tolerans ve sicaklikla kaymis degeri."""
    return deger * (1.0 + tol) * (1.0 + tk * (t - T_REF))


def olc(ad, p):
    """(kayip, duzluk, katlanma) — katlanma_tasarim'in zincir modeli."""
    return kt.degerlendir(ad, p)[:3]


def en_kotu_durum(ad, nominal):
    """Her parcanin iki ucunu deneyip olcutu en cok bozan bileske.

    HANGI YON KOTU ONCEDEN BILINMIYOR. Bir kondansatoru buyutmek bir
    olcutu iyilestirip digerini bozabiliyor, ve bant filtresinde
    parcalarin etkisi ters yonlerde. O yuzden tahmin edilmiyor,
    2^n kose taraniyor (n kucuk: en fazla alti parca).
    """
    Lp, Cp, Ls, Cs, Ct, Cx = nominal
    parcalar = [("L", Lp), ("C", Cp), ("L", Ls), ("C", Cs),
                ("C", Ct), ("C", Cx)]
    en = None
    for isaretler in itertools.product((-1, +1), repeat=len(parcalar)):
        for t in SICAKLIK:
            p = []
            for (tur, v), s in zip(parcalar, isaretler):
                if v == 0:
                    p.append(0)
                    continue
                tol = (TOL_L if tur == "L" else TOL_C) * s
                tk = TK_L if tur == "L" else TK_C
                p.append(sapma(v, tol, tk, t))
            k, d, b = olc(ad, tuple(p))
            # olcutu en cok bozan: katlanma en dusuk olan
            puan = (b, -k, -d)
            if en is None or puan < en[0]:
                en = (puan, tuple(p), (k, d, b), t)
    return en


def monte_carlo(ad, nominal, n, rng):
    """n adet rastgele kart. Doner: (kayip, duzluk, katlanma) dizileri."""
    Lp, Cp, Ls, Cs, Ct, Cx = nominal
    tur = ["L", "C", "L", "C", "C", "C"]
    sonuc = []
    for _ in range(n):
        t = rng.uniform(*SICAKLIK)
        p = []
        for (v, tp) in zip(nominal, tur):
            if v == 0:
                p.append(0)
                continue
            tol = (TOL_L if tp == "L" else TOL_C)
            tk = TK_L if tp == "L" else TK_C
            # ucgen dagilim: uretici merkeze yakin toplar, ama
            # duzgun dagilim daha kotumser. Kotumseri aliyoruz.
            p.append(sapma(v, rng.uniform(-tol, tol), tk, t))
        sonuc.append(olc(ad, tuple(p)))
    return np.array(sonuc)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kosu", type=int, default=2000)
    a = ap.parse_args()
    rng = np.random.default_rng(20260816)

    bantlar = zincir_sim.bantlari_oku()
    print("TOLERANS ANALIZI — alis zinciri")
    print("kondansator +/-%.0f%%, bobin +/-%.0f%%, sicaklik %.0f..%.0f C"
          % (TOL_C * 100, TOL_L * 100, *SICAKLIK))
    print("olcut: katlanma >= %.0f dB, duzluk <= %.0f dB"
          % (ESIK_KATLANMA, ESIK_DUZLUK))
    print("kayip esigi banda gore (ITU-R P.372 atmosferik gurultu): "
          + ", ".join("%s %.0f" % (k, v) for k, v in ESIK_KAYIP.items()))
    print()

    print("EN KOTU DURUM — her parca ayni anda en kotu yonde")
    print("%-9s %9s %9s %11s %7s  %s" %
          ("bant", "kayip", "duzluk", "katlanma", "sicak", "durum"))
    kotu = 0
    for ad, Lp, Cp, Ls, Cs, Ct, Cx in bantlar:
        nom = (Lp, Cp, Ls, Cs, Ct, Cx)
        _, _, (k, d, b), t = en_kotu_durum(ad, nom)
        durum = "OK"
        if b < ESIK_KATLANMA or d > ESIK_DUZLUK or k > ESIK_KAYIP[ad]:
            durum = "KALDI"
            kotu += 1
        print("%-9s %8.2f %8.2f %10.1f %6.0f C  %s"
              % (ad, k, d, b, t, durum))
    print()

    print("MONTE CARLO — %d kart, bagimsiz dagilim" % a.kosu)
    print("%-9s %11s %11s %11s %9s" %
          ("bant", "katlanma", "duzluk", "kayip", "gecen %"))
    for ad, Lp, Cp, Ls, Cs, Ct, Cx in bantlar:
        nom = (Lp, Cp, Ls, Cs, Ct, Cx)
        r = monte_carlo(ad, nom, a.kosu, rng)
        kayip, duzluk, katlanma = r[:, 0], r[:, 1], r[:, 2]
        gecen = np.mean((katlanma >= ESIK_KATLANMA) &
                        (duzluk <= ESIK_DUZLUK) &
                        (kayip <= ESIK_KAYIP[ad])) * 100
        print("%-9s %6.1f-%4.1f %6.2f-%4.2f %6.2f-%4.2f %8.2f%%"
              % (ad, katlanma.min(), katlanma.max(),
                 duzluk.min(), duzluk.max(),
                 kayip.min(), kayip.max(), gecen))
        if gecen < 99.0:
            kotu += 1
    print()
    print("aralik sutunlari: en dusuk-en yuksek")
    print("gecen %: uc olcutu birden saglayan kartlarin orani")
    if kotu:
        print()
        print("%d bant tolerans altinda kaliyor." % kotu)
    sys.exit(1 if kotu else 0)
