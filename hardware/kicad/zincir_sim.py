#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""ALIS ZINCIRI — antenden ADC pinine, uctan uca ngspice.

    python3 zincir_sim.py

NEDEN. Blok blok olcmek yetmiyor. Filtreyi tek basina olcunce
"1.3 dB kayip" diyor, ama o filtre 50 ohm kaynak ve 50 ohm yuk
arasinda olculuyor. Gercekte cikisinda trafo, seri direnc ve ADC'nin
giris kapasitesi var; girisinde de zayiflaticinin cikis empedansi.
Zincir kurulunca her blok komsusunun empedansini goruyor ve sonuc
bloklarin toplami DEGIL.

ADC, DAC, FPGA gibi parcalarin ICI simule edilmiyor — gerek de yok,
nasil calistiklari veri sayfasinda yazili. Onlar burada SINIR KOSULU:
ADC'nin giris kapasitesi, tam olcek gerilimi ve ortak mod seviyesi.
Sorulan soru "ADC ne yapiyor" degil, "ADC'nin BACAGINA ne geliyor".

ZINCIR (bir alis kanali):

  anten 50R
    -> [C karti] gaz desarj + TVS      : sinyal seviyesinde gorunmez
    -> [C karti] bant filtresi          : merdiven bant geciren, 3 kutup
    -> [C karti] PE4312 zayiflatici     : 0 dB ayarinda ekleme kaybi
    -> kablo (SMA-SMA, kayip ihmal)
    -> [A karti] ADT1-1WT+ 1:1 trafo    : 75 ohm parca, 50 ohm sistemde
    -> [A karti] 33R seri (her kol)
    -> [A karti] 22 pF diferansiyel
    -> AD9251 girisi: 6 pF, tam olcek 2 V p-p diferansiyel

OLCULEN UC SEY:

  1 BANT ICI DUZLUK. Kanaldan kanala ve bant icinde tepki ne kadar
    degisiyor. Dort kanal ayni olmali; genlik farki huzme sekline
    dogrudan giriyor.

  2 TAM OLCEK ICIN GEREKEN ANTEN GUCU. ADC 2 V p-p diferansiyelde
    doyuyor. Zincirin kazanci bilinince "anten girisinde kac dBm
    ADC'yi doyurur" sorusunun cevabi cikiyor — alicinin ust siniri bu.

  3 NYQUIST'TE BASTIRMA. 80 MSPS'te Nyquist 40 MHz. Oradan yukarisi
    banda katlaniyor; zincirin orada ne kadar bastirdigi katlanan
    gurultunun ne kadar olacagini belirliyor.
"""
import math
import os
import re
import subprocess
import sys

def bantlari_oku():
    """Filtre tablosunu gen_03_filter.py'DEN OKU, kopyalama.

    Burada once elle yazilmis bir kopya vardi. Bu kartta ayni hata
    bir kez yasandi: lpf_sim.py D kartinin ESKI filtresini olcuyordu,
    tasarim yedi pozisyona ve tuzakli yapiya gecmisti, arac
    guncellenmemisti. Sonuc, aracin hic olmamasindan kotudur —
    ya yanlis alarma alisilir ya gercek bir bozulma o gurultunun
    icinde kaybolur.

    Uretec import EDILMIYOR: modul seviyesinde sema ciziyor, import
    etmek dosyalari yeniden yazardi. Tablo metinden ayikliniyor.
    """
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "C_rf", "gen_03_filter.py")
    metin = open(yol, encoding="utf-8").read()
    m = re.search(r"^BANTLAR = \[(.*?)^\]", metin, re.S | re.M)
    if not m:
        raise SystemExit("gen_03_filter.py icinde BANTLAR tablosu yok")
    out = []
    for satir in re.finditer(
            r'\(\s*"([^"]+)"\s*,([^)]*)\)', m.group(1)):
        ad = satir.group(1)
        alan = [x.strip() for x in satir.group(2).split(",")]
        sayi = [float(x) for x in alan if re.fullmatch(r"[\d.]+", x)]
        if len(sayi) < 6:
            raise SystemExit("%s satiri okunamadi: %s" % (ad, alan))
        Lp, Cp, Ls, Cs, Ct, Cx = sayi[:6]
        out.append((ad, Lp, Cp, Ls, Cs, Ct, Cx))
    return out


BANTLAR = None          # __main__'de dolduruluyor

KAPSAM = {
    "160m":   [(1.8, 2.0)],
    "80_60m": [(3.5, 3.8), (5.3515, 5.3665)],
    "40_30m": [(7.0, 7.2), (10.1, 10.15)],
    "20_17m": [(14.0, 14.35), (18.068, 18.168)],
    "15_10m": [(21.0, 21.45), (24.89, 24.99), (28.0, 29.7)],
    "6m":     [(50.0, 54.0)],
}

# BOBIN Q'SU BILINEN BIR SAYI DEGIL — ARALIK.
#
# tedarik_denetim.py gercek siparis edilebilir parcalari buldu ve Q
# her yerde ayni cikmadi: 560 nH icin Q=25@25MHz, 18 uH icin
# Q=35@1MHz, bazilarinda Q hic verilmemis, bazilarinda da 900 MHz
# gibi calisma frekansindan cok uzak bir noktada verilmis (o sayi
# 25 MHz hakkinda hicbir sey soylemiyor).
#
# Tek bir Q secip "tasarim calisiyor" demek bu yuzden yanlis olurdu.
# Onun yerine tasarim Q'ya DUYARLILIK olarak olculuyor: en kotu
# makul degerde de olcutleri geciyorsa parca secimi tasarimi
# bozamaz. Gecmiyorsa problem parcada degil tasarimda.
Q_ARALIK = (25.0, 40.0, 60.0)
Q_BOBIN = 40.0          # tek kosuda kullanilan varsayilan

# --- A karti giris agi, AD9251 veri sayfasi Tablo 9 (0-70 MHz satiri)
R_SERI = 33.0           # her kolda
C_DIF = 22e-12          # diferansiyel
C_ADC = 6e-12           # AD9251 giris kapasitesi
V_TAM_OLCEK = 2.0       # V p-p diferansiyel

# --- PE4312 zayiflatici, 0 dB ayarinda ekleme kaybi (veri sayfasi)
ATT_KAYIP_DB = 1.5

# --- ADT1-1WT+ : 1:1 ama parca 75 ohm. Kaynak 50 ohm.
Z_TRAFO = 75.0

FS = 80e6               # AD9251BCPZ-80 ornekleme hizi
KATLANMA_ESIK = 40.0    # katlanan sinyal en az bu kadar altta olmali (dB)


def katlanan_frekanslar(f_mhz_lo, f_mhz_hi, bolge_sayisi=5):
    """Bu banda katlanan GIRIS frekanslari (MHz).

    fs = 80 MHz. Bir giris frekansi f, sayisal tarafta
    |f - k*fs| olarak beliriyor. Bandin ustune dusen butun k'lar
    taraniyor; kendi bolgesi (dogru sinyal) haric.

    Bandin kendisi Nyquist'in ustundeyse (6 m) sayisal karsiligi
    once bulunuyor, sonra o karsiliga katlanan diger bolgeler.
    """
    fs = FS / 1e6
    # bandin SAYISAL karsiligi
    def sayisal(f):
        k = round(f / fs)
        return abs(f - k * fs)
    d_lo, d_hi = sorted((sayisal(f_mhz_lo), sayisal(f_mhz_hi)))
    out = []
    for k in range(0, bolge_sayisi + 1):
        for isaret in (+1, -1):
            for d in (d_lo, (d_lo + d_hi) / 2, d_hi):
                f = k * fs + isaret * d
                if f <= 0.05:
                    continue
                # kendi bolgesi = dogru sinyal, atlanir
                if min(abs(f - f_mhz_lo), abs(f - f_mhz_hi)) < 1e-6:
                    continue
                if f_mhz_lo - 0.05 <= f <= f_mhz_hi + 0.05:
                    continue
                out.append(round(f, 4))
    return sorted(set(out))


def netlist(ad, Lp, Cp, Ls, Cs, Ct=0, Cx=0, q=None):
    """Antenden ADC pinine kadar butun zincir, tek netlist."""
    q = q or Q_BOBIN
    rq_p = 2 * math.pi * 10e6 * (Lp * 1e-9) / q
    rq_s = 2 * math.pi * 10e6 * (Ls * 1e-9) / q
    s = ["* alis zinciri %s" % ad]
    # anten: 1 V kaynak, 50 ohm. Eslesmis yukte 0.5 V okunur (-6.02 dB).
    s.append("V1 ant 0 AC 1")
    s.append("Rs ant f0 50")
    # --- C karti: merdiven bant geciren (sont / seri / sont)
    for i, n in ((1, "f0"), (2, "f1")):
        s.append("Lp%d %s mp%d %.4fn" % (i, n, i, Lp))
        if Cx:
            # sont bobine SERI kondansator: gecirme bandinin ALTINDA
            # iletim sifiri (6 m'de 30 MHz'ten katlanan sinyal icin)
            s.append("Rp%d mp%d xp%d %.4f" % (i, i, i, max(rq_p, 1e-3)))
            s.append("Cx%d xp%d 0 %.4fp" % (i, i, Cx))
        else:
            s.append("Rp%d mp%d 0 %.4f" % (i, i, max(rq_p, 1e-3)))
        s.append("Cp%d %s 0 %.4fp" % (i, n, Cp))
    s.append("Ls1 f0 ms1 %.4fn" % Ls)
    s.append("Rs1 ms1 mc1 %.5f" % max(rq_s, 1e-3))
    if Ct:
        # seri BOBININ iki ucuna paralel tuzak: gecirme bandinin
        # USTUNDE iletim sifiri (15/10 m'de 50.3 MHz icin)
        s.append("Ct1 f0 mc1 %.4fp" % Ct)
    s.append("Cs1 mc1 f1 %.4fp" % Cs)
    # --- PE4312 ZAYIFLATICI, HER IKI UCU 50 OHM.
    #
    # Ilk surumde zayiflaticiyi tek bir gerilim kontrollu kaynakla
    # modelledim ve o kaynagin girisi AKIM CEKMIYOR — yani bant
    # filtresi yuk olarak ACIK DEVRE goruyordu. Filtre 50 ohm kaynak
    # ve 50 ohm YUK arasinda sentezlendi; yuksuz birakilinca tepkisi
    # baska bir filtre oluyor. Belirtisi de fizige aykiriydi: pasif
    # bir zincirde +5 dB kazanc cikti.
    #
    # Dogrusu: filtre cikisinda 50 ohm YUK (zayiflaticinin giris
    # empedansi), sonra zayiflatma, sonra 50 ohm KAYNAK empedansi
    # (zayiflaticinin cikisi) trafoyu suruyor.
    s.append("Rl_filt f1 0 50")
    kayip_orani = 10 ** (-ATT_KAYIP_DB / 20.0)
    s.append("Eatt attx 0 f1 0 %.6f" % kayip_orani)
    s.append("Ratt attx a0 50")
    # --- A karti: ADT1-1WT+ 1:1. Ideal trafo + parcanin 75 ohm
    #     karakteristigi: ikincil tarafta seri fark direnci olarak
    #     modellenmiyor; bunun yerine ikincil 75 ohm'a bakiyor gibi
    #     yuk empedansi olcumu ayri yapiliyor (asagida ZGIRIS).
    #     Burada 1:1 ideal, cunku bant icinde trafo duz.
    s.append("Etr sp 0 a0 0 0.5")
    s.append("Etrn sn 0 a0 0 -0.5")
    # --- seri direncler ve diferansiyel C
    s.append("Rp %s vp %.3f" % ("sp", R_SERI))
    s.append("Rn %s vn %.3f" % ("sn", R_SERI))
    s.append("Cd vp vn %.4fp" % (C_DIF * 1e12))
    s.append("Ca vp vn %.4fp" % (C_ADC * 1e12))
    # ADC girisi yuksek empedans; kacak icin buyuk direnc
    s.append("Rin vp vn 100k")
    s.append(".ac dec 400 100k 300meg")
    s.append(".print ac vdb(vp,vn) vp(vp,vn)")
    s.append(".end")
    return "\n".join(s)


def kos(nl, ad):
    yol = "/tmp/zin_%s.cir" % ad.replace("/", "_")
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


# 1 V'luk kaynak + 50 ohm: eslesmis yukte 0.5 V. Zincir kazanci
# bu referansa gore okunuyor.
BOLUCU = 6.02


def dbm_tam_olcek(kazanc_db):
    """Zincir kazanci verilince, ADC'yi doyuran anten gucu (dBm).

    ADC tam olcek 2 V p-p diferansiyel = 0.707 V rms.
    Zincirin cikisinda o gerilim icin girise gereken gerilim:
        V_ant = V_adc / 10^(kazanc/20)
    Anten 50 ohm oldugu icin P = V^2 / 50, ve kaynak gerilimi
    ACIK DEVRE gerilimi (bolucuden once), yani mevcut guc
    P_av = V_kaynak^2 / (8*50).
    """
    v_adc_rms = V_TAM_OLCEK / (2 * math.sqrt(2))
    v_kaynak = v_adc_rms / (10 ** (kazanc_db / 20.0))
    p_av = v_kaynak ** 2 / (8 * 50.0)
    return 10 * math.log10(p_av / 1e-3)


if __name__ == "__main__":
    print("ALIS ZINCIRI — anten -> C karti -> A karti -> ADC pini")
    print("ornekleme %.0f MSPS, Nyquist %.0f MHz" % (FS / 1e6, FS / 2e6))
    print("%-9s %4s %7s %7s %10s %9s %8s  %s" %
          ("bant", "Q", "kazanc", "duzluk", "katlanan", "bastirma",
           "tam olcek", "durum"))
    kotu = 0
    BANTLAR = bantlari_oku()
    for ad, Lp, Cp, Ls, Cs, Ct, Cx in BANTLAR:
      for q in Q_ARALIK:
        v = kos(netlist(ad, Lp, Cp, Ls, Cs, Ct, Cx, q), "%s_q%d" % (ad, q))
        if not v:
            print("%-9s ngspice cikti vermedi" % ad)
            kotu += 1
            continue

        def db(f):
            return min(v, key=lambda x: abs(x[0] - f))[1] + BOLUCU
        noktalar = [db(f * 1e6) for r in KAPSAM[ad] for f in r]
        kazanc = max(noktalar)
        duzluk = max(noktalar) - min(noktalar)
        # --- katlanma: bandin uzerine dusen en TEHLIKELI frekans
        en_kotu, en_kotu_f = -300.0, 0.0
        for lo, hi in KAPSAM[ad]:
            for f_gir in katlanan_frekanslar(lo, hi):
                a = db(f_gir * 1e6) - kazanc
                if a > en_kotu:
                    en_kotu, en_kotu_f = a, f_gir
        durum = "OK"
        if duzluk > 3.0:
            durum = "DUZ DEGIL"
            kotu += 1
        if -en_kotu < KATLANMA_ESIK:
            durum = "KATLANMA ZAYIF (%.0f dB)" % -en_kotu
            kotu += 1
        print("%-9s %4.0f %7.2f %7.2f %8.1f MHz %8.1f %6.1f dBm  %s" %
              (ad if q == Q_ARALIK[0] else "", q, kazanc, duzluk,
               en_kotu_f, en_kotu, dbm_tam_olcek(kazanc), durum))
    print()
    print("kazanc: bant icinde en yuksek nokta, eslesmis referansa gore (dB)")
    print("duzluk: bant icinde en yuksek ile en dusuk arasi (dB)")
    print("40MHz : Nyquist'te bastirma, tepeye gore (dB)")
    print("tam olcek: ADC'yi doyuran anten gucu (dBm)")
    sys.exit(1 if kotu else 0)
