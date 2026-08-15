#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""KAZANC BUTCESI — DAC'a ne verilirse antenden 100 W cikar.

    python3 kazanc_butcesi.py

Sema uzerinde bir butce yazili (gen_01_driver.py):

    AD9767 cikisi        +0.5 dBm
    PE4312               -1.5 .. -15 dB
    PGA-103+             +22 dB
    IRF530N cifti        +18 dB
    -> final girisine    +39 dBm (8 W)

Bu butce zincirin SURUCU tarafini topluyor ama bir seyi hic
soylemiyor: FINALLER ne kadar surus ISTIYOR. O sayi yazili
olmadigi surece butcenin kapanip kapanmadigi bilinmiyor; iki
tarafi ayri ayri hesaplayip ortada bulusturmak gerekiyor.

Yanlis tarafta hata yapmak pahali. Surus GEREKENDEN cok olursa A
sinifi kat asiri surulur: dalga tepesi kirpilir, sonyayilim ve
intermodulasyon patlar, ve harmonik filtresi kendisinin
bastirmasi gereken seyi uretmis bir kata baglanmis olur.

FINALLERIN ISTEDIGI SURUS — cihazdan hesaplaniyor:

  Gecit dugumu, kol basina: 1 ohm bastirma direnci, ustune iki
  IRFP250N'in Ciss'i paralel. 1 ohm rastgele degil, Ciss'in
  30 MHz'teki reaktansi 1.02 ohm — ayni mertebede direnc girisi
  frekanstan bagimsiz kiliyor.

  Gereken gecit salinimi gecis iletkenliginden: kol basina tepe
  akim / gm.

  Surus gucu o salinimi o dugumde tutmak icin gereken guc.

CIKIS GUCU ayrica dogrulaniyor: A sinifi push-pull'da tepe akim
dinlenme akimini gecemez (gecerse cihaz kesime girer ve sinif A
olmaktan cikar). Yani dinlenme akimi cikis gucunu ustten
sinirliyor ve bu iki sayi birbirini tutmali.
"""
import math
import sys

# --- IRFP250N, veri sayfasi
CISS = 2700e-12         # giris kapasitesi (F)
GM_KOL = 8.0            # gecis iletkenligi, KOL basina (gen_02_final)
CIHAZ_KOL = 2           # kol basina cihaz
KOL = 2                 # push-pull

# --- kat
R_BASTIRMA = 1.0        # gecit dugumundeki bastirma direnci (ohm)
VCC = 50.0
IDQ_CIHAZ = 1.67        # dinlenme akimi, cihaz basina (A)
P_HEDEF = 100.0         # hedef cikis gucu (W)

# --- surucu zinciri (gen_01_driver.py)
DAC_DBM = 0.5
ATT_MIN = 1.5           # PE4312, 0 dB ayarindaki ekleme kaybi
ATT_MAX = 31.5          # PE4312 azami zayiflatma
PGA_DB = 22.0
DRV_DB = 18.0

BANTLAR = [("160m", 1.9e6), ("80m", 3.65e6), ("40m", 7.1e6),
           ("20m", 14.2e6), ("15m", 21.2e6), ("10m", 28.85e6),
           ("6m", 52.0e6)]


def dbm(w):
    return 10 * math.log10(w / 1e-3)


def surus_gucu(f_hz):
    """Kol basina gereken surus gucu (W) ve gecit salinimi (V tepe)."""
    # A sinifi: kol basina tepe akim = kol basina dinlenme akimi
    i_tepe_kol = IDQ_CIHAZ * CIHAZ_KOL
    v_gecit = i_tepe_kol / GM_KOL              # tepe (V)
    v_rms = v_gecit / math.sqrt(2)
    # gecit dugumu: R_BASTIRMA paralel Ciss (kol basina iki cihaz)
    c_kol = CISS * CIHAZ_KOL
    x_c = 1.0 / (2 * math.pi * f_hz * c_kol)
    # GERCEK guc sadece direnc uzerinde; kapasitif akim reaktif ve
    # giris trafosunda rezonansa alinabiliyor. Ama surucunun o akimi
    # TASIMASI gerekiyor, o yuzden gorunur guc de raporlaniyor.
    p_gercek = v_rms ** 2 / R_BASTIRMA
    z = 1.0 / math.sqrt((1.0 / R_BASTIRMA) ** 2 + (1.0 / x_c) ** 2)
    i_rms = v_rms / z
    p_gorunur = v_rms * i_rms
    return p_gercek, p_gorunur, v_gecit, x_c


def cikis_gucu():
    """A sinifi push-pull'un dinlenme akimindan cikabilecek azami guc."""
    i_tepe = IDQ_CIHAZ * CIHAZ_KOL * KOL       # toplam tepe (A)
    # gerilim salinimi Vcc ile sinirli; guc = 0.5 * V * I
    v_tepe = 2 * P_HEDEF / i_tepe
    return i_tepe, v_tepe, 0.5 * v_tepe * i_tepe


if __name__ == "__main__":
    kotu = 0
    i_tepe, v_tepe, p_hesap = cikis_gucu()
    print("CIKIS TARAFI")
    print("   dinlenme akimi     : %.2f A (%d cihaz x %.2f A)"
          % (IDQ_CIHAZ * CIHAZ_KOL * KOL, CIHAZ_KOL * KOL, IDQ_CIHAZ))
    print("   tepe akim          : %.2f A" % i_tepe)
    print("   %.0f W icin gereken gerilim tepesi: %.1f V (besleme %.0f V)"
          % (P_HEDEF, v_tepe, VCC))
    if v_tepe > VCC * 0.9:
        print("   ** GERILIM SALINIMI BESLEMEYE COK YAKIN **")
        kotu += 1
    else:
        print("   gerilim payi       : %.0f%% (doyma riski yok)"
              % (100 * (1 - v_tepe / VCC)))
    print()

    print("SURUS TARAFI — finaller ne istiyor")
    print("%-7s %9s %9s %10s %11s" %
          ("bant", "Xc kol", "gecit V", "gercek W", "gereken dBm"))
    en_yuksek = -300
    for ad, f in BANTLAR:
        pg, pgo, vg, xc = surus_gucu(f)
        toplam = pg * KOL
        d = dbm(toplam)
        en_yuksek = max(en_yuksek, d)
        print("%-7s %8.2fR %8.2f V %9.3f W %10.1f dBm"
              % (ad, xc, vg, toplam, d))
    print()

    print("SURUCU ZINCIRI — ne verebiliyor")
    azami = DAC_DBM - ATT_MIN + PGA_DB + DRV_DB
    asgari = DAC_DBM - ATT_MAX + PGA_DB + DRV_DB
    print("   DAC %.1f dBm, PGA-103+ %+.0f dB, IRF530N cifti %+.0f dB"
          % (DAC_DBM, PGA_DB, DRV_DB))
    print("   zayiflatici 0 dB   -> %+.1f dBm" % azami)
    print("   zayiflatici %.1f dB -> %+.1f dBm" % (ATT_MAX, asgari))
    print()

    print("BULUSMA")
    print("   finallerin istedigi : %+.1f dBm" % en_yuksek)
    print("   zincirin azamisi    : %+.1f dBm" % azami)
    fazla = azami - en_yuksek
    print("   fark                : %+.1f dB" % fazla)
    if asgari > en_yuksek:
        print()
        print("   ** ZAYIFLATICI TAM ACIKKEN BILE %.1f dB FAZLA **" %
              (asgari - en_yuksek))
        print("   Kat en dusuk ayarda bile asiri surulur.")
        kotu += 1
    elif fazla > 3:
        print()
        print("   Zincir gerekenden %.0f dB fazla verebiliyor. Bu KUSUR"
              % fazla)
        print("   degil, ayar araligi — ama semadaki butcede 'final")
        print("   girisine +39 dBm' yazmasi yaniltici: finaller %.0f dBm"
              % en_yuksek)
        print("   istiyor, aradaki %.0f dB zayiflaticiyla kapatiliyor."
              % fazla)
        print("   Zayiflaticinin acilis varsayilani AZAMI ZAYIFLATMA")
        print("   olmak zorunda; 0 dB varsayilani kati %.0f dB asiri"
              % fazla)
        print("   surerdi. (gen_01_driver.py bunu zaten boyle kurmus.)")
    else:
        print("   butce kapaniyor")
    sys.exit(1 if kotu else 0)
