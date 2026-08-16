#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""ADC -> SISTEM SAATI GECISININ FAZ BUTCESI.

    python3 sentez/faz_butcesi.py

NEDEN VAR. adc_giris'in cikislari ADC'nin DCO'su ile yazmaclaniyor,
ddc_dort ise clk_sys ile calisiyor. Bu gecis ASENKRON DEGIL: iki saat
de ayni 80 MHz VCXO'dan turuyor, DCO ADC'den kaynak-senkron geri
geliyor ve aradaki faz kart gecikmeleriyle SABIT.

Sabit fazli bir gecis, faz DOGRU PENCEREDE ise kusursuz calisir ve
yanlis penceredeyse HER ORNEKTE bozulur. Arasi yok. O yuzden sorulmasi
gereken soru "senkronlayici koyalim mi" degil, "pencere ne kadar ve
faz onun icinde mi".

NEXTPNR BU KISITI IFADE EDEMIYOR. LPF'e "BLOCK PATH FROM CLKNET ...
TO CLKNET ..." yazip denedim; nextpnr "ignoring unsupported LPF
command" diyor. Zaten dogru cozum de o degil: false path demek
"bu yolu hic olcme" demek, oysa biz tam tersini istiyoruz — yolun
olculmesini ve pencereye sigmasini.

O yuzden butce burada, disarida hesaplaniyor: FPGA ici gecikme
nextpnr'in raporundan (gercek olcum), kart tarafi da iz uzunluklari
ve veri sayfasindan.

BULUNAN PENCERE BIR YONLENDIRME KISITIDIR. Kart cizilirken DCO izi
ile VCXO'nun FPGA'ya giden izi bu farki saglamak zorunda; saglamazsa
alici calismaz ve sebebi hicbir yerde gorunmez.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PNR = os.path.join(HERE, "pnr.log")

PERIYOT = 12.5          # ns, 80 MHz

# --- ECP5 yazmac zamanlamasi (Lattice DS1044, hiz sinifi -6)
T_SETUP = 0.30          # ns
T_HOLD  = 0.10          # ns

# --- AD9251 veri sayfasi (Rev. B, Tablo 5) —
#     DCO'nun ornek saatine gore cikis gecikmesi.
#     ADC'nin ic gecikmesi; kart cizimiyle degismiyor.
T_ADC_DCO_MIN = 1.8     # ns
T_ADC_DCO_MAX = 3.6     # ns

# --- Kart izleri. HENUZ YONLENDIRILMEDI.
#
# uzunluk_olc.py butun aglari 2.2 mm / 1 via gosteriyor, yani sadece
# via saplamalari var. Bu sayilar yonlendirme bitince gercek
# olcumlerle degisecek; simdilik SIFIR alinip pencere "kart tarafi
# katkisiz" haliyle hesaplaniyor. Yani asagidaki pencere EN IYI
# HALDIR ve kart izleri onu ancak daraltir.
IZ_YONLENDIRILDI = False
T_IZ_DCO = 0.0          # ADC -> FPGA, DCO izi
T_IZ_CLK = 0.0          # VCXO -> FPGA, clk_sys izi
T_IZ_ADCCLK = 0.0       # VCXO -> ADC, ornekleme saati izi


def fpga_ici_gecikme():
    """nextpnr raporundan DCO -> clk_sys yolunun gecikmesi (ns)."""
    if not os.path.exists(PNR):
        return None
    metin = open(PNR, encoding="utf-8", errors="replace").read()
    en = None
    for m in re.finditer(
            r"Critical path report for cross-domain path "
            r"'posedge \$glbnet\$(adc\d_dco)[^']*' -> "
            r"'posedge \$glbnet\$clk_sys[^']*':(.*?)(?=Info: Critical|\Z)",
            metin, re.S):
        blok = m.group(2)
        t = re.findall(r"([\d.]+) ns logic, ([\d.]+) ns routing", blok)
        if t:
            toplam = float(t[0][0]) + float(t[0][1])
            if en is None or toplam > en[1]:
                en = (m.group(1), toplam)
    return en


if __name__ == "__main__":
    print("ADC -> SISTEM SAATI FAZ BUTCESI")
    print("periyot %.2f ns (80 MHz)" % PERIYOT)
    print()

    ici = fpga_ici_gecikme()
    if ici is None:
        print("pnr.log yok ya da cross-domain yol raporlanmamis.")
        print("Once sentez/yap.sh kosun.")
        sys.exit(1)
    alan, t_ici = ici
    print("FPGA ICI YOL — nextpnr olcumu")
    print("   %s -> clk_sys : %.2f ns" % (alan, t_ici))
    print()

    # Faz: DCO kenari, clk_sys kenarina gore ne kadar geride.
    faz_min = T_ADC_DCO_MIN + T_IZ_ADCCLK + T_IZ_DCO - T_IZ_CLK
    faz_max = T_ADC_DCO_MAX + T_IZ_ADCCLK + T_IZ_DCO - T_IZ_CLK
    print("DCO FAZI (clk_sys kenarina gore)")
    print("   ADC ic gecikmesi : %.2f .. %.2f ns  (AD9251 veri sayfasi)"
          % (T_ADC_DCO_MIN, T_ADC_DCO_MAX))
    if IZ_YONLENDIRILDI:
        print("   kart izleri      : DCO %.2f, clk %.2f, adcclk %.2f ns"
              % (T_IZ_DCO, T_IZ_CLK, T_IZ_ADCCLK))
    else:
        print("   kart izleri      : HENUZ YONLENDIRILMEDI, sifir alindi")
        print("                      (asagidaki pencere EN IYI HAL;")
        print("                       izler onu ancak daraltir)")
    print("   toplam faz       : %.2f .. %.2f ns" % (faz_min, faz_max))
    print()

    # Kurulum: veri, bir sonraki clk_sys kenarindan T_SETUP once varmali
    kurulum_pay = PERIYOT - (faz_max + t_ici) - T_SETUP
    # Tutma: veri, yakalayan kenardan T_HOLD sonra kadar kararli kalmali
    tutma_pay = (faz_min + t_ici) - T_HOLD

    print("PAYLAR")
    print("   kurulum : %.2f ns   (%.2f - (%.2f + %.2f) - %.2f)"
          % (kurulum_pay, PERIYOT, faz_max, t_ici, T_SETUP))
    print("   tutma   : %.2f ns" % tutma_pay)
    print()

    kotu = 0
    if kurulum_pay < 0:
        print("** KURULUM KARSILANMIYOR **")
        kotu += 1
    if tutma_pay < 0:
        print("** TUTMA KARSILANMIYOR **")
        kotu += 1

    # Fazin girebilecegi pencere
    pencere_ust = PERIYOT - t_ici - T_SETUP
    pencere_alt = T_HOLD - t_ici
    pencere = pencere_ust - max(pencere_alt, 0.0)
    print("IZIN VERILEN FAZ PENCERESI")
    print("   %.2f .. %.2f ns   (periyodun %%%.0f'i)"
          % (max(pencere_alt, 0.0), pencere_ust, 100 * pencere / PERIYOT))
    print()
    print("YONLENDIRME KISITI — kart cizilirken saglanacak:")
    print("   T_izDCO - T_izCLK  <=  %.2f ns  (kurulum)"
          % (pencere_ust - T_ADC_DCO_MAX - T_IZ_ADCCLK))
    print("   yaklasik %.0f mm iz farki (FR4 ic katman, 7 ps/mm)"
          % ((pencere_ust - T_ADC_DCO_MAX - T_IZ_ADCCLK) / 0.007))
    print()
    if kotu == 0 and pencere / PERIYOT < 0.6:
        print("DIKKAT: pencere periyodun %%%.0f'i. Bu OTOMATIK olarak"
              % (100 * pencere / PERIYOT))
        print("saglanan bir sey degil; kart cizimi bunu tutturmali.")
        print("Tutturamazsa alici HER ORNEKTE bozulur ve belirtisi")
        print("hicbir yerde 'zamanlama' diye gorunmez.")
    sys.exit(1 if kotu else 0)
