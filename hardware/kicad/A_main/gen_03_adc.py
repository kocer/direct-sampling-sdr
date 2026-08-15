#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""03_adc: 2x AD9251-80, dort faz-uyumlu kanal. Kaynak: ../NETLIST.md §3."""
import json, os
from schlib import Sheet, yol_esle

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

A = "dogrudan-sdr:AD9251"
FA = "Package_DFN_QFN:QFN-64-1EP_9x9mm_P0.5mm_EP4.7x4.7mm"
T = "dogrudan-sdr:ADT1-1WT"
FT = "RF_Mini-Circuits:Mini-Circuits_CD542_H2.84mm"
R, C = "Device:R", "Device:C"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
CONN = "Connector:Conn_Coaxial"
FSMA = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"

# A2 KAGIT: bu sayfada dort on uc, iki ADC'nin dort birimi ve FPGA
# banka 6 birlikte duruyor. A3'e sigmiyor — ilk denemede FPGA sayfa
# cercevesinin disinda kaldi, cizim gecerli ama gorunmuyor.
s = Sheet("03_adc", "ADC x2", UU["03_adc"],
          "AD9251-80 x2, ADT1-1WT x4, banka 6, cogullamali", paper="A1")

nref = [0]


def cnt(pfx):
    nref[0] += 1
    return f"{pfx}{299 + nref[0]}"


# ------------------------------------------------------------------ giris
def frontend(tref, jref, x, y, ch, vcm):
    """Bir kanalin analog on ucu. AD9251 veri sayfasi Sekil 42 +
    Tablo 9'daki referans devre:

        SMA -(50R hat)- 49.9R sont -- trafo PRI
                        trafo SEC -- R seri -- VIN+   ve  C dif
                                  -- R seri -- VIN-
                        trafo SEC_CT -- VCM

    ILK CIZIMDE SONLANDIRMA DA, SERI DIRENC DE, DIFERANSIYEL C DE
    YOKTU. Trafonun birincili acik devre goruyordu: 50 ohm hat hic
    sonlanmiyor, gelen sinyalin tamami geri yansiyordu."""
    s.sym(CONN, jref, f"SMA {ch}", x, y, fp=FSMA)
    s.pin_label(CONN, "1", x, y, 0, f"RF_{ch}", "output")
    s.pin_power(CONN, "2", x, y, 0, "GND")

    # 49.9R sont sonlandirma — hattin bittigi yer
    s.sym(R, cnt("R"), "49.9R 1%", x + 18, y + 10, rot=90, fp=FR)
    s.pin_label(R, "1", x + 18, y + 10, 90, f"RF_{ch}", "passive")
    s.pin_power(R, "2", x + 18, y + 10, 90, "GND")

    s.sym(T, tref, "ADT1-1WT+", x + 42, y, fp=FT)
    s.pin_label(T, "3", x + 42, y, 0, f"RF_{ch}", "input", d=12.7)
    s.pin_power(T, "1", x + 42, y, 0, "GND", d=12.7)
    s.pin_label(T, "6", x + 42, y, 0, f"SEC_{ch}_P", "output", d=12.7)
    s.pin_label(T, "4", x + 42, y, 0, f"SEC_{ch}_N", "output", d=12.7)
    s.pin_label(T, "2", x + 42, y, 0, vcm, "input", d=7.62)
    s.nc(*s.P(T, "5", x + 42, y))

    # seri direncler + diferansiyel C (Tablo 9)
    for i, (a, b) in enumerate([(f"SEC_{ch}_P", f"VIN_{ch}_P"),
                                (f"SEC_{ch}_N", f"VIN_{ch}_N")]):
        rx = x + 78
        ry = y - 6 + i * 12
        # rot=90: Device:R sembolu rot=0'da DIKEY ciziliyor, pinleri
        # alt-ust. Dikey birakinca 12 mm arayla duran iki direncin
        # saplamalari ust uste bindi ve VIN+ ile VIN- kisa devre oldu
        # (netlist'te tek ag olarak cikti). Yatay cizip yan yana degil
        # alt alta koyuyoruz.
        s.sym(R, cnt("R"), "33R 1%", rx, ry, rot=90, fp=FR)
        s.pin_label(R, "1", rx, ry, 90, a, "passive")
        s.pin_label(R, "2", rx, ry, 90, b, "passive")
    s.sym(C, cnt("C"), "22pF", x + 100, y, fp=FC)
    s.pin_label(C, "1", x + 100, y, 0, f"VIN_{ch}_P", "passive")
    s.pin_label(C, "2", x + 100, y, 0, f"VIN_{ch}_N", "passive")


s.text("ANALOG ON UC — kanal basina bir trafo", 16, 14, 2.0)
s.text("SMA (C kartindan gelen filtreli RF) -> ADT1-1WT+ 1:1 -> VIN cifti\\n"
       "Orta uc VCM'e: ortak mod 0.9 V. Giris kapasitansi 6 pF.\\n"
       "VIN cifti ES BOY, SIKI CIFT, KISA — dort kanalin faz uyumu\\n"
       "buradaki simetriye bagli.", 16, 20, 1.35)

# VCM CIPE OZEL. Ilk halde iki AD9251'in VCM cikisini ayni aga
# bagladim; ERC "Output ile Output baglanmis" dedi ve hakliydi —
# iki gerilim kaynagi cikisi paralel, biri digerini suruyor.
for i, ch in enumerate(["A1", "B1", "A2", "B2"]):
    frontend(f"T{i + 1}", f"J{20 + i}", 20, 48 + i * 32, ch,
             "VCM_U20" if i < 2 else "VCM_U21")

s.text("RC AGI BANDA GORE DEGISIYOR — AD9251 Tablo 9:\\n"
       "     0-70 MHz giris   R seri 33R,  C dif 22 pF\\n"
       "   70-200 MHz giris   R seri 125R, C dif ACIK (takilmiyor)\\n\\n"
       "Bu alet hem tabanbant hem alt-ornekleme yapiyor, tek deger ikisine\\n"
       "birden uymuyor. Sematikte 33R + 22pF cizili (HF/6m kullanimi).\\n"
       "VHF/UHF alt-ornekleme icin ayni ayak izlerine 125R takilip C\\n"
       "sokuluyor. Hepsi 0603, kart degismiyor — hangi bandda calisilacagi\\n"
       "montajda seciliyor.\\n\\n"
       "ADT1-1WT+ pinout'u veri sayfasindan (Rev.G) DOGRULANDI:\\n"
       "3 PRI DOT · 1 PRI · 6 SEC DOT · 4 SEC · 2 SEC CT · 5 kullanilmiyor.\\n"
       "Ilk tahminimde orta uc 5'teydi, yanlisti.\\n\\n"
       "** PARCA 75 OHM ** — orani 1:1 oldugu icin 50 ohm sistemde de\\n"
       "calisiyor, ama uyumsuzluk var. NETLIST.md §10.14.", 16, 172, 1.35)

# ------------------------------------------------------------------ analog
s.text("AD9251 ANALOG + SAAT — birim 1", 130, 14, 2.0)


def analog(ref, x, y, cha, chb):
    vcm = "VCM_" + ref
    s.sym(A, ref, "AD9251BCPZ-80", x, y, fp=FA, unit=1)
    s.pin_label(A, "51", x, y, 0, f"VIN_{cha}_P", "input", d=10.16)
    s.pin_label(A, "52", x, y, 0, f"VIN_{cha}_N", "input", d=10.16)
    s.pin_label(A, "62", x, y, 0, f"VIN_{chb}_P", "input", d=15.24)
    s.pin_label(A, "61", x, y, 0, f"VIN_{chb}_N", "input", d=15.24)
    s.pin_label(A, "1", x, y, 0, f"ADCLK_{ref}_P", "input", d=20.32)
    s.pin_label(A, "2", x, y, 0, f"ADCLK_{ref}_N", "input", d=25.4)
    for p in ("49", "50", "53", "54", "59", "60", "63", "64"):
        s.pin_label(A, p, x, y, 0, "+1V8_A", "input", d=5.08)
    # ------- referans ve bias, NETLIST.md §3.2
    s.pin_label(A, "55", x, y, 0, f"VREF_{ref}", "passive", d=10.16)
    s.pin_power(A, "56", x, y, 0, "GND", d=15.24)     # SENSE -> AGND
    s.pin_label(A, "57", x, y, 0, vcm, "output", d=20.32)
    s.pin_label(A, "58", x, y, 0, f"RBIAS_{ref}", "passive", d=25.4)
    # ACIK PED = PIN 65, "0" DEGIL.
    # Sembolde acik ped "0" numarasindaydi, ayak izinde (QFN-64-1EP)
    # ise "65". Numaralar tutmadigi icin GND var olmayan bir pine
    # gidiyordu ve ped 65 kartta AGSIZ kaliyordu — olctum, iki ADC'de
    # de. AD9251 veri sayfasi: acik ped AGND'ye baglanmali; hem tek
    # toprak referansi hem tek termal yol o.
    s.pin_power(A, "65", x, y, 0, "GND", d=7.62)

    cx = x + 34
    s.sym(C, cnt("C"), "1uF", cx, y + 40, fp=FC)
    s.pin_label(C, "1", cx, y + 40, 0, f"VREF_{ref}", "passive")
    s.pin_power(C, "2", cx, y + 40, 0, "GND")
    s.sym(R, cnt("R"), "10k 1%", cx + 20, y + 40, fp=FR)
    s.pin_label(R, "1", cx + 20, y + 40, 0, f"RBIAS_{ref}", "passive")
    s.pin_power(R, "2", cx + 20, y + 40, 0, "GND")
    s.sym(C, cnt("C"), "100nF", cx + 40, y + 40, fp=FC)
    s.pin_label(C, "1", cx + 40, y + 40, 0, vcm, "passive")
    s.pin_power(C, "2", cx + 40, y + 40, 0, "GND")


analog("U20", 150, 60, "A1", "B1")
analog("U21", 150, 150, "A2", "B2")

s.text("SENSE (56) DOGRUDAN AGND'ye: dahili 1.0 V referans secilir.\\n"
       "VREF (55) 1uF ile AGND'ye. RBIAS (58) 10k %1 — %5 direnc\\n"
       "olcek hatasi yapar, tam deger onemli.\\n"
       "VCM CIPE OZEL: U20'ninki A1/B1 trafolarina, U21'inki A2/B2'ye.\\n"
       "Ortak baglamak iki cikisi paralel etmek olurdu.\\n\\n"
       "Pin 0 = exposed paddle, cipin TEK toprak baglantisi. Termal via\\n"
       "dizisiyle dogrudan toprak duzlemine — datasheet 'must be soldered'.",
       130, 240, 1.35)

# ------------------------------------------------------------------ veri
s.text("DIJITAL CIKIS — birim 2, cogullamali", 270, 14, 2.0)


def data(ref, x, y, n):
    s.sym(A, ref, "AD9251BCPZ-80", x, y, fp=FA, unit=2)
    dpins = ["27", "29", "30", "31", "32", "33", "34", "35", "36",
             "38", "39", "40", "41", "42"]
    for i, p in enumerate(dpins):
        s.pin_label(A, p, x, y, 0, f"ADC{n}_D{i}", "output", d=7.62)
    s.pin_label(A, "24", x, y, 0, f"ADC{n}_DCO", "output", d=12.7)
    s.pin_label(A, "43", x, y, 0, f"ADC{n}_OR", "output", d=17.78)


data("U20", 300, 60, 1)
data("U21", 300, 150, 2)

s.text("COGULLAMA ACIK (SPI'dan). Cip basina 15 hat @160 MHz SDR,\\n"
       "30 hat @80 MHz yerine. Iki gerekce:\\n"
       "  1. pin butcesi — cogullamasiz iki cip 60 pin, tutmuyor\\n"
       "  2. GURULTU — 30 yerine 15 anahtarlanan hat, analog ucun yaninda\\n\\n"
       "IKI CIP DE BANKA 6'DA. Ayni bankada olmalari zamanlama eslesmesi\\n"
       "ve faz uyumu icin sart.\\n"
       "DCO saat-yetenekli pine gidecek (Lattice pinout'undan secilecek).\\n"
       "Kanal sirasi (once A mi B mi) SPI'dan okunup firmware'de sabitlenir.",
       270, 240, 1.35)

# ------------------------------------------------------------------ B kanali
s.text("KANAL B CIKISLARI — birim 3, COGULLAMA MODUNDA BOSTA", 270, 190, 1.6)
for ref, x, y in [("U20", 300, 205), ("U21", 380, 205)]:
    s.sym(A, ref, "AD9251BCPZ-80", x, y, fp=FA, unit=3)
    for p in ["6", "7", "8", "9", "11", "12", "13", "14", "15", "16",
              "17", "18", "20", "21", "22", "23"]:
        s.nc(*s.P(A, p, x, y))

# ------------------------------------------------------------------ kontrol
s.text("GUC VE KONTROL — birim 4", 380, 14, 2.0)
for ref, x, y, n in [("U20", 400, 60, 1), ("U21", 400, 150, 2)]:
    s.sym(A, ref, "AD9251BCPZ-80", x, y, fp=FA, unit=4)
    for p in ("10", "19", "28", "37"):
        s.pin_label(A, p, x, y, 0, "+1V8_D", "input", d=5.08)
    s.pin_label(A, "44", x, y, 0, "ADC_SDIO", "bidirectional", d=10.16)
    s.pin_label(A, "45", x, y, 0, "ADC_SCLK", "input", d=15.24)
    s.pin_label(A, "46", x, y, 0, f"ADC{n}_nCSB", "input", d=20.32)
    # PDWN FPGA'dan DEGIL, dogrudan AGND'de. Guc-dusurme kullanilmiyor;
    # o pini serbest birakip banka 0'da PA'ya yer actik (08_control).
    s.pin_power(A, "48", x, y, 0, "GND", d=25.4)
    s.pin_label(A, "3", x, y, 0, "ADC_SYNC", "input", d=30.48)
    s.pin_power(A, "47", x, y, 0, "GND", d=7.62)      # ~OEB: cikislar acik
    for p in ("4", "5", "25", "26"):
        s.nc(*s.P(A, p, x, y))

s.text("SPI: SDIO ve SCLK ORTAK, ~CSB cip basina ayri (banka 0).\\n"
       "~OEB dogrudan AGND'ye — cikislar hep acik, kontrol edilecek bir sey yok.\\n\\n"
       "** ADC_SYNC IKI CIPE DE ORTAK VE ES UZUNLUKTA **\\n"
       "Iki ADC'nin ic bolucusunu ayni anda sifirliyor. Dort kanalin faz\\n"
       "uyumu — yani bu aletin butun ayirt edici ozelligi: gurultu iptali,\\n"
       "yon bulma, isin sekillendirme — bu tek hattin simetrisine bagli.\\n"
       "Yol uzunluklari esitlenmezse kanallar arasi sabit faz farki kalir\\n"
       "ve kalibrasyonla tam kapanmaz.\\n\\n"
       "SYNC'in tam davranisi (bir darbe mi, seviye mi) veri sayfasindan\\n"
       "dogrulanacak — NETLIST.md §10 acik maddesi.", 380, 240, 1.35)

s.text("SAAT: ADCLK_U20_P/N ve ADCLK_U21_P/N, 02_clock'taki ADCLK846'nin\\n"
       "1 ve 2 numarali cikislari. LVDS, dogrudan baglaniyor (AD9251 saat\\n"
       "girisi PECL/LVDS/1.8V CMOS kabul ediyor).\\n"
       "IKI YOL ES UZUNLUKTA CEKILECEK.", 130, 218, 1.35)

# ------------------------------------------------------------------ FPGA
from schlib import unit_pins

E = "dogrudan-sdr:ECP5-BGA256"
FE = ("Package_BGA:BGA-256_14.0x14.0mm_Layout16x16_P0.8mm_"
      "Ball0.45mm_Pad0.32mm_NSMD")

s.text("FPGA BANKA 6 — verinin gittigi yer", 20, 300, 2.0)
BX, BY = 260, 360
s.sym(E, "U10", "LFE5U-25F-7BG256I", BX, BY, fp=FE, unit=6)
B6 = unit_pins(E, 6)

nets = ([f"ADC1_D{i}" for i in range(14)] + ["ADC1_DCO", "ADC1_OR"] +
        [f"ADC2_D{i}" for i in range(14)] + ["ADC2_DCO", "ADC2_OR"])
io = sorted(n for n, nm in B6.items() if nm.startswith("PL"))
assert len(io) == 32 and len(nets) == 32, (len(io), len(nets))
for pin_no, net in yol_esle(io, nets, "ADC1", "ADC2"):
    s.pin_label(E, pin_no, BX, BY, 0, net, "input", d=7.62)
for n, nm in sorted(B6.items()):
    if nm.startswith("VCCIO"):
        s.pin_label(E, n, BX, BY, 0, "+1V8", "input", d=15.24)

s.text("BANKA 6 TAM DOLU: 32/32.\\n"
       "  ADC1  14 veri + DCO + OR = 16\\n"
       "  ADC2  14 veri + DCO + OR = 16\\n"
       "Marj yok. Buraya bir sinyal daha gerekirse OR bayraklarindan biri\\n"
       "feda edilir (FPGA'da doygunluk zaten tespit edilebiliyor).\\n\\n"
       "** PIN ATAMASI GECICI ** — asagidaki eslesme banka 6'nin PL pinlerini\\n"
       "sirayla dagitiyor. DCO hatlari SAAT-YETENEKLI pine dusmeli; hangi\\n"
       "toplarin PCLK oldugu Lattice pinout CSV'sinden alinip bu liste\\n"
       "yeniden siralanacak. Yerlesimden once yapilacak is.\\n"
       "VCCIO6 = +1V8 — ADC DRVDD ile ayni seviye, seviye cevirici yok.",
       20, 310, 1.35)

# ---- pin basina ayristirma (NETLIST.md §1)
s.text("AYRISTIRMA — pin basina, 0402", 20, 400, 2.0)
s.decaps("+1V8_A", 16, "100nF", 24, 415, 400, per_row=10)
s.decaps("+1V8_D", 8, "100nF", 24, 465, 420, per_row=8)
s.decaps("+1V8_A", 2, "10uF", 190, 465, 430)
s.text("AVDD 8 pin x 2 cip = 16 adet 100nF + 2 adet toplu 10uF\\n"
       "DRVDD 4 pin x 2 cip = 8 adet 100nF\\n\\n"
       "AVDD kondansatorleri ANALOG toprak adasinda, DRVDD'ninkiler\\n"
       "dijital tarafta. Ikisini karistirmak ADC'nin gurultu tabanini\\n"
       "yukseltir — bu kartta o taban aletin butun degeri.",
       24, 482, 1.35)

s.write(os.path.join(HERE, "03_adc.kicad_sch"))
print("03_adc.kicad_sch yazildi")
