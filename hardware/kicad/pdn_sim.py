#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""BESLEME AGI EMPEDANSI (PDN) — cipin rayda gordugu empedans.

    python3 pdn_sim.py

Ayirma kondansatorlerini SAYMAK yetmiyor. kondansator_denetim.py
"her besleme bacagina bir kondansator var mi" diye bakiyor ve bu
gerekli, ama yeterli degil: onemli olan cipin rayda gordugu
EMPEDANSIN frekansa gore ne oldugu.

Cip akim cektiginde ray gerilimi Z x I kadar duser. Ray dususu
sayisal kismin gurultu payini yer; ADC/DAC/saat rayinda ise dogrudan
sinyale karisir. Hicbir baglanti denetimi bunu goremez: sema dogru,
netlist dogru, DRC temiz, ve ray yine de calmiyor.

ASIL TEHLIKE ANTI-REZONANS. Bir kondansator kendi ESL'i ile bir seri
rezonansa sahip; ustunde ENDUKTIF davraniyor. Yigin kondansatoru
(47 uF) endüktif hale geldigi frekansta seramik (100 nF) hala
kapasitif; ikisi paralel bir LC olusturuyor ve o noktada empedans
tek basina her ikisinden de BUYUK cikiyor. Yani kondansator eklemek
empedansi belli bir frekansta ARTIRABILIYOR.

MONTAJ ENDUKTANSI BASKIN. 0603 bir kondansatorun kendi ESL'i ~0.5 nH
ama ped + via + duzlem yolu 1-2 nH ekliyor. Yani kondansatorun
degerini degistirmek cogu zaman is gormuyor, ADEDI ve YERI is
goruyor. Bu araç montaj enduktansini ayri bir sayi olarak tutuyor,
cunku tasarimda oynanabilen sey odur.

HEDEF EMPEDANS = izin verilen ray dalgalanmasi / gecici akim.
Asilirsa bulgu.
"""
import math
import sys

# GECICI AKIM VARSAYIMI SONUCU BELIRLIYOR — bu yuzden ayri yazili.
#
# Ilk surumde ECP5 cekirdegine 1.5 A gecici akim verdim ve arac
# "+1V1 rayina 37 kondansator gerekiyor" dedi. O sayi varsayimin
# sonucuydu, tasarimin degil: LFE5U-25F kucuk bir FPGA ve cekirdek
# akimi tipik kullanimda 0.3-0.5 A mertebesinde; gecici adim bunun
# bir kismi. Alti kat buyuk bir varsayim, hedef empedansi alti kat
# kucultuyor ve gereken kondansator sayisini kabaca alti katina
# cikariyor.
#
# Simdiki degerler cihazlarin gercek tuketiminden. Yine de bunlar
# TAHMIN; kesin sayi ancak kart olculunce cikar. O yuzden arac
# duyarliligi de basiyor.
#
# (ray, gerilim, izin verilen dalgalanma %, gecici akim A, aciklama)
RAYLAR = [
    ("+1V1",     1.1, 0.05, 0.30, "ECP5 cekirdek"),
    ("+1V8",     1.8, 0.05, 0.25, "ECP5 VCCIO"),
    ("+1V8_A",   1.8, 0.03, 0.10, "AD9251 analog"),
    ("+1V8_CLK", 1.8, 0.03, 0.05, "saat dagitimi"),
    ("+3V3",     3.3, 0.05, 0.40, "sayisal"),
    ("+3V3_A",   3.3, 0.03, 0.10, "AD9767 analog"),
    ("+3V3_CLK", 3.3, 0.03, 0.05, "VCXO"),
]

# Netlistten sayilan kondansatorler (kicad-cli ile cikarildi)
KONDANSATOR = {
    "+1V1":     {"100nF": 14, "10uF": 2, "47uF": 1, "22uF": 1},
    "+1V8":     {"100nF": 10, "1uF": 1, "22uF": 1, "10uF": 1},
    "+1V8_A":   {"100nF": 16, "10uF": 2, "1uF": 1},
    "+1V8_CLK": {"100nF": 4, "10uF": 1, "1uF": 1},
    "+1V8_D":   {"100nF": 8, "1uF": 1, "10uF": 1},
    "+2V5":     {"1uF": 2, "100nF": 2, "10uF": 1},
    "+3V3":     {"100nF": 30, "1uF": 4, "10uF": 3, "22uF": 1, "47uF": 1},
    "+3V3_A":   {"10uF": 3, "100nF": 3},
    "+3V3_CLK": {"10uF": 1, "100nF": 1},
}

# deger -> (kapasite F, ESR ohm, kendi ESL H)
PARCA = {
    "100nF": (100e-9,  0.020, 0.5e-9),
    "1uF":   (1e-6,    0.010, 0.5e-9),
    "10uF":  (10e-6,   0.005, 0.8e-9),
    "22uF":  (22e-6,   0.004, 1.0e-9),
    "47uF":  (47e-6,   0.003, 1.2e-9),
}

# Montaj enduktansi: ped + via + duzlem yolu. Tasarimda oynanan sey bu.
L_MONTAJ = 1.2e-9

# ---------------------------------------------------------------
# TARAMA ARALIGI VE REGULATOR — ILK SURUMDE IKISI DE YANLISTI.
#
# Ilk halde 1 GHz'e kadar tariyordum ve butun raylar "hedef
# asiliyor" cikti, tepeler de 987 MHz'te — yani taramanin en ust
# ucunda. O bir anti-rezonans degildi: kalip ici ve paket
# kapasitesini modellemedigim icin empedans sonsuza kadar endüktif
# tirmaniyordu. Gercekte o frekanslarda cipin kendi ic kapasitesi
# devreye giriyor ve kartin ayirma agi zaten devrede degil.
# Kartin sorumlu oldugu bant ~200 MHz'e kadar.
#
# Regulatoru de sabit 100 nH endüktans olarak modelliyordum ve bu
# 0.4 MHz'te keskin, sahte bir anti-rezonans uretiyordu. Gercek bir
# anahtarlamali regulatorun kapali cevrimi kendi gecis frekansina
# (~100 kHz) kadar cikis empedansini dusuk tutuyor; onun ustunde
# zaten yigin kondansatorleri baskin ve ONLAR ZATEN SAYILIYOR.
# Ayri bir regulator kolu koymak ayni seyi iki kere saymak oluyordu.
F_ALT = 100e3          # bunun altinda regulator cevrimi hakim
F_UST = 200e6          # bunun ustunde cipin kendi kapasitesi hakim


def empedans(ray, f):
    """Rayin toplam empedansi (ohm) f frekansinda."""
    y = 0j
    for deger, adet in KONDANSATOR.get(ray, {}).items():
        c, esr, esl = PARCA[deger]
        l = esl + L_MONTAJ
        for _ in range(adet):
            z = complex(esr, 2 * math.pi * f * l - 1.0 / (2 * math.pi * f * c))
            y += 1.0 / z
    return abs(1.0 / y) if y != 0 else float("inf")


if __name__ == "__main__":
    print("BESLEME AGI EMPEDANSI — montaj enduktansi %.1f nH, "
          "bant %.0f kHz - %.0f MHz"
          % (L_MONTAJ * 1e9, F_ALT / 1e3, F_UST / 1e6))
    print()
    print("%-10s %6s %8s %9s %10s %9s  %s" %
          ("ray", "adet", "hedef", "en yuksek", "frekans", "pay", "durum"))
    kotu = 0
    for ray, v, oran, i_gec, aciklama in RAYLAR:
        z_hedef = v * oran / i_gec
        adet = sum(KONDANSATOR.get(ray, {}).values())
        en = (0.0, 0.0)
        f = F_ALT
        while f < F_UST:
            z = empedans(ray, f)
            if z > en[0]:
                en = (z, f)
            f *= 1.02
        pay = 20 * math.log10(z_hedef / en[0]) if en[0] > 0 else 0
        durum = "OK"
        if en[0] > z_hedef:
            durum = "HEDEF ASILIYOR"
            kotu += 1
        print("%-10s %5d %7.1f m %7.1f m %8.1f M %7.1f dB  %s"
              % (ray, adet, z_hedef * 1e3, en[0] * 1e3, en[1] / 1e6,
                 pay, durum))
    print()
    print("hedef     : izin verilen ray dalgalanmasi / gecici akim")
    print("en yuksek : anti-rezonans tepesi (yigin endüktif, seramik")
    print("            hala kapasitif — ikisi paralel LC)")
    print("pay       : tepenin hedefe gore ne kadar altinda oldugu")
    print()
    print("YIGIN KONDANSATORU DENETIMI — varsayimdan BAGIMSIZ")
    print("Ust bant hesabi gecici akim tahminine duyarli, ama bir rayda")
    print("yigin kondansatorunun HIC olmamasi tahminden bagimsiz bir")
    print("boslugtur: regulatorun cevrimi ~100 kHz'e kadar tutuyor,")
    print("seramikler ~1 MHz'in ustunde tutuyor, arasi acikta kalir.")
    for ray, v, oran, i_gec, aciklama in RAYLAR:
        k = KONDANSATOR.get(ray, {})
        yigin = sum(a for d, a in k.items()
                    if PARCA[d][0] >= 10e-6)
        if yigin == 0:
            print("   %-10s (%s) YIGIN KONDANSATORU YOK — en buyugu %s"
                  % (ray, aciklama,
                     max(k, key=lambda d: PARCA[d][0]) if k else "hic"))
            kotu += 1
    if kotu:
        print()
        print("GEREKEN ADET — ayni degerden kac tane olmali:")
        for ray, v, oran, i_gec, _ in RAYLAR:
            z_hedef = v * oran / i_gec
            en = max(empedans(ray, F_ALT * (1.02 ** k))
                     for k in range(int(math.log(F_UST / F_ALT)
                                        / math.log(1.02))))
            if en <= z_hedef:
                continue
            # ust bantta empedans L_toplam/N ile belirleniyor
            mevcut = KONDANSATOR.get(ray, {}).get("100nF", 0)
            gerek = math.ceil(mevcut * en / z_hedef) if mevcut else 0
            print("   %-10s 100nF: %d adet var, ~%d adet gerekiyor"
                  % (ray, mevcut, gerek))
        print()
        print("Empedansi dusurmenin yolu kondansator DEGERINI degistirmek")
        print("degil: %.1f nH montaj enduktansi baskin. Ayni degerden daha"
              % (L_MONTAJ * 1e9))
        print("COK adet, ve her birinin viasi kisa — is goren budur.")
    sys.exit(1 if kotu else 0)
