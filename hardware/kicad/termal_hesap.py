#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""TERMAL — 233 W surekli isiyi tasiyan sey ne olmali.

    python3 termal_hesap.py

A sinifi seciminin bedeli burada odeniyor. 100 W cikis icin DC giris
333 W ve aradaki 233 W ISI. Bu bir tercihin sonucu, kusur degil:
A sinifi en dogrusal calisma noktasi ve bu alette dogrusallik
pazarlik konusu degil (dort kanalli huzme yonlendirme, sonyayilim
sinirlari). Ama 233 W'i gercekten disari atmak gerekiyor ve o is
kagit uzerinde bitmiyor.

ISI YOLU, cihaz basina:

    lehim/kalip -> govde     Rth(j-c)   IRFP250N veri sayfasi
    govde -> sogutucu        Rth(c-s)   montaj yontemine bagli
    sogutucu -> hava         Rth(s-a)   ARANAN SAYI

Ilk iki basamak CIHAZ BASINA gucu goruyor (58 W), ucuncu basamak
TOPLAM gucu goruyor (233 W). Bu ayrimi kacirmak yaygin bir hata ve
sonucu iki kat yaniltir.

Arac uc montaj senaryosunu ve iki bilesim sicakligi hedefini ayri
ayri cozuyor, cunku gereken sogutucu bu tercihlere cok duyarli.
"""
import sys

P_CIKIS = 100.0
VERIM_A = 0.30          # A sinifi push-pull, gercekci
CIHAZ = 4

RTH_JC = 0.70           # IRFP250N, veri sayfasi (C/W)
T_ORTAM = 40.0          # kapali kutu ici, yaz

# YALITIMSIZ MONTAJ BU DEVREDE KULLANILAMAZ.
#
# Ilk surumde "dogrudan montaj" secenegini de koydum ve arac en
# kucuk sogutucuyu onun uzerinden onerdi. Fiziksel olarak mumkun
# degil: TO-247'de tirnak DRENAJ'a bagli. Bu bir push-pull kat,
# iki kolun drenajlari ayri dugumlerde ve dort cihaz ortak bir
# sogutucuya yalitimsiz vidalanirsa cikis trafosunun birincili
# kisa devre olur.
#
# Yani secim yalitimli montaj yontemleri ARASINDA yapiliyor ve
# bedeli agir: cihazin kendi icinde dusen sicaklik butcenin
# yarisindan fazlasini yiyor.
#
# (ad, Rth(c-s) C/W, aciklama, kullanilabilir mi)
MONTAJ = [
    ("mika + macun", 0.50, "ucuz, ama en kotu isi yolu", True),
    ("seramik AlN",  0.24, "alüminyum nitrur ped", True),
    ("seramik AlN+", 0.15, "kalin AlN, iyi yuzey basinci", True),
    ("yalitimsiz",   0.10, "TIRNAK = DRENAJ, KULLANILAMAZ", False),
]

HEDEF = [("guvenli", 125.0), ("sinirda", 150.0)]

# Sogutucu siniflari — gercek urun mertebeleri (C/W)
SOGUTUCU = [
    ("dogal tasinim, buyuk profil",      0.50),
    ("zorlamali hava, orta profil",      0.25),
    ("zorlamali hava, buyuk profil",     0.12),
    ("zorlamali hava, sunucu sinifi",    0.07),
    ("sivi sogutma plakasi",             0.02),
]


if __name__ == "__main__":
    p_dc = P_CIKIS / VERIM_A
    p_isi = p_dc - P_CIKIS
    p_cihaz = p_isi / CIHAZ
    print("A SINIFI GUC BILANCOSU")
    print("   cikis %.0f W, verim %.0f%% -> DC giris %.0f W"
          % (P_CIKIS, VERIM_A * 100, p_dc))
    print("   isiya donen        : %.0f W" % p_isi)
    print("   cihaz basina       : %.1f W (%d cihaz)" % (p_cihaz, CIHAZ))
    print()
    print("   DIKKAT: ilk iki termal basamak CIHAZ BASINA gucu gorur")
    print("   (%.1f W), sogutucu-hava basamagi TOPLAM gucu gorur (%.0f W)."
          % (p_cihaz, p_isi))
    print()

    print("GEREKEN SOGUTUCU — Rth(s-a), ortam %.0f C" % T_ORTAM)
    print("%-16s %8s %12s %12s" %
          ("montaj", "Rth(c-s)", "Tj<=125 C", "Tj<=150 C"))
    en_iyi = {}
    for ad, rcs, _, kullanilir in MONTAJ:
        if not kullanilir:
            print("%-16s %7.2f  %s" % (ad, rcs,
                  "KULLANILAMAZ (tirnak = drenaj, push-pull)"))
            continue
        satir = []
        for _, tj in HEDEF:
            # Tj = Ta + P_toplam*Rsa + P_cihaz*(Rjc + Rcs)
            ic = p_cihaz * (RTH_JC + rcs)
            rsa = (tj - T_ORTAM - ic) / p_isi
            satir.append(rsa)
            en_iyi[(ad, tj)] = rsa
        print("%-16s %7.2f  %10s %12s"
              % (ad, rcs,
                 "%.3f C/W" % satir[0] if satir[0] > 0 else "IMKANSIZ",
                 "%.3f C/W" % satir[1] if satir[1] > 0 else "IMKANSIZ"))
    print()

    for ad, rcs, aciklama, kullanilir in MONTAJ:
        if not kullanilir:
            continue
        ic = p_cihaz * (RTH_JC + rcs)
        print("%s (%s): cihazin kendi icinde %.0f C dusuyor"
              % (ad, aciklama, ic))
    print()
    print("   Bu dususu sogutucu DUZELTEMEZ. Rth(s-a) sifir olsa bile")
    print("   bilesim, sogutucu yuzeyinden bu kadar sicak olur. Butcenin")
    print("   nereye gittigini gosteren sayi budur.")
    print()

    print("HANGI SOGUTUCU YETER (montaj: seramik AlN, Tj<=150 C)")
    hedef_rsa = en_iyi[("seramik AlN", 150.0)]
    print("   gereken: %.3f C/W" % hedef_rsa)
    bulundu = False
    for ad, r in SOGUTUCU:
        isaret = "YETER" if r <= hedef_rsa else "yetmez"
        if r <= hedef_rsa and not bulundu:
            isaret = "YETER  <-- en kucuk yeterli"
            bulundu = True
        print("   %-32s %5.2f C/W  %s" % (ad, r, isaret))
    print()

    kotu = 0
    if hedef_rsa < 0.12:
        print("** SONUC: ZORLAMALI HAVA SART VE SUNUCU SINIFI GEREKIYOR **")
        print("   Dogal tasinimla bu guc atilamaz. Fan arizasi da tek-ariza")
        print("   yikim yolu: flans sicakligi olcumu (TMP235, 06_power)")
        print("   ZATEN VAR ve 85 C'de kademe dusurup 100 C'de kesiyor —")
        print("   yani fan durursa koruma calisiyor. Fan izleme yok, ama")
        print("   sicaklik izleme dogru katmanda: fanin dondugunu degil,")
        print("   ISININ ATILDIGINI olcuyor.")
    elif hedef_rsa < 0.30:
        print("SONUC: zorlamali hava sart, buyuk profil yeter.")
    else:
        print("SONUC: dogal tasinim yeterli olabilir.")
        kotu += 0
    print()
    print("SURE SINIRI OLARAK CALISMA — alternatif")
    print("   Amator kullanimda %100 gorev cevrimi seyrek. Isi kapasitesi")
    print("   ile calisilirsa (buyuk alüminyum kütle), kisa surelerde daha")
    print("   kucuk sogutucu yeter. 5 kg alüminyum (0.90 J/g/K) %.0f W'ta"
          % p_isi)
    print("   dakikada %.1f C isinir. On dakikalik bir QSO'da %.0f C artis"
          % (p_isi * 60 / (5000 * 0.90), p_isi * 600 / (5000 * 0.90)))
    print("   demek — yani kutle tek basina cozum degil, sadece pay.")
    sys.exit(1 if kotu else 0)
