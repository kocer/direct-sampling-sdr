#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""07_fpga_power: ECP5 guc (birim 1) + konfigurasyon (birim 8) + SPI flash + JTAG.
Kaynak: ../NETLIST.md §1 ve §6."""
import json, os
from schlib import Sheet, unit_pins

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

E = "dogrudan-sdr:ECP5-BGA256"
FE = ("Package_BGA:BGA-256_14.0x14.0mm_Layout16x16_P0.8mm_"
      "Ball0.45mm_Pad0.32mm_NSMD")
R, C = "Device:R", "Device:C"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
# TOPLU KONDANSATOR 0603'E SIGMIYOR. 47uF 0603'te HICBIR gerilim
# sinifinda uretilmiyor (0603'un tavani ~22uF @ 6.3 V). Kartta
# cizilebiliyor ama siparis edilemiyor; hata ancak dizgi asamasinda
# gorunur. 1206'da 47uF/6.3V ve 47uF/10V yaygin.
# Not: X5R/X7R seramik sinifina yakin gerilimde kapasitesinin
# yarisindan cogunu kaybediyor, o yuzden 3.3 V rayda 6.3 V degil
# 10 V sinifi tercih edilmeli — deger dizesi paketle birlikte
# BOM'da bunu soyluyor.
FCB = "Capacitor_SMD:C_1206_3216Metric"
FLASH = "Memory_Flash:W25Q128JVS"
FSOIC = "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm"
HDR = "Connector_Generic:Conn_02x03_Odd_Even"
FHDR = "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical"
LED = "Device:LED"
FLED = "LED_SMD:LED_0603_1608Metric"
SW = "Switch:SW_Push"
FSW = "Button_Switch_SMD:SW_SPST_TL3342"

s = Sheet("07_fpga_power", "FPGA guc + konfigurasyon", UU["07_fpga_power"],
          "ECP5 birim 1 (guc) ve 8 (konfig), W25Q128, JTAG")

U1 = unit_pins(E, 1)
U8 = unit_pins(E, 8)
rc = [0]          # ayristirma kondansatoru sayaci


def decap(x, y, rail, val="100nF"):
    """Bir ray-toprak kondansatoru. Ref'ler C100'den sayiyor ki
    01_power'daki C1..C9 ile carpismasin.

    Paket DEGERE gore: 22uF ustu 0603'e sigmiyor.
    """
    rc[0] += 1
    ref = f"C{99 + rc[0]}"
    fp = FCB if val in ("47uF", "22uF", "100uF") else FC
    s.sym(C, ref, val, x, y, fp=fp)
    s.pin_label(C, "1", x, y, 0, rail, "input")
    s.pin_power(C, "2", x, y, 0, "GND")


# ================================================================== BIRIM 1
s.text("ECP5 GUC — birim 1", 20, 14, 2.0)
s.text("VCC x6 = +1V1 cekirdek · VCCAUX x2 = +2V5 · GND x27", 20, 20, 1.4)

EX, EY = 62, 105
s.sym(E, "U10", "LFE5U-25F-7BG256I", EX, EY, fp=FE, unit=1)

# GND toplari: uzunluklari donusumlu, 2.54 aralikta guc sembolleri
# ust uste binmesin diye.
for i, num in enumerate(sorted(n for n, nm in U1.items() if nm.startswith("GND"))):
    s.pin_power(E, num, EX, EY, 0, "GND", d=3.81 + (i % 4) * 10.16)

for num in sorted(n for n, nm in U1.items() if nm.startswith("VCC") and
                  not nm.startswith("VCCAUX")):
    s.pin_label(E, num, EX, EY, 0, "+1V1", "input", d=6.35)

for num in sorted(n for n, nm in U1.items() if nm.startswith("VCCAUX")):
    s.pin_label(E, num, EX, EY, 0, "+2V5", "input", d=12.7)

# toplu ayristirma
s.text("TOPLU AYRISTIRMA", 20, 152, 1.6)
for i, (rail, val) in enumerate([("+1V1", "47uF"), ("+1V1", "10uF"),
                                 ("+1V1", "10uF"), ("+2V5", "10uF"),
                                 ("+3V3", "47uF"), ("+3V3", "10uF")]):
    decap(22 + i * 16, 172, rail, val)

# ---- pin basina ayristirma, ARTIK CIZILI
# Once "sematikte tek tek cizilmiyor" diye not birakmistim. Oyle kalirsa
# BOM ve dizgi dosyasinda bu parcalar HIC OLMUYOR — kart ayristirmasiz
# geliyor. 0402, her besleme topunun altina.
s.text("PIN BASINA 100nF — her besleme topu icin bir adet", 20, 176, 1.6)
s.decaps("+1V1", 6, "100nF", 24, 190, 200)            # VCC x6
s.decaps("+2V5", 2, "100nF", 24, 212, 210)            # VCCAUX x2
s.decaps("+3V3", 9, "100nF", 24, 234, 220, per_row=7)            # VCCIO banka 0/1/2/7/8
s.decaps("+1V8", 4, "100nF", 24, 278, 240)            # VCCIO banka 3/6
s.text("6 VCC (+1V1) · 2 VCCAUX (+2V5) · 13 VCCIO (9 x +3V3, 4 x +1V8)\\n"
       "= 21 adet 0402. YERLESIM KURALI: kondansator topun ALTINDA,\\n"
       "viasi dogrudan toprak duzlemine, kondansatorden sonra degil.\\n"
       "Vianin endüktansı kondansatorun faydasini yiyorsa parca bosuna.",
       150, 176, 1.3)

s.text("GUC SIRALAMASI — VCCIO ONCE, CEKIRDEK SONRA\\n"
       "  U1 (VIN -> +3V3) EN girise bagli, hep acik\\n"
       "  U8 (+3V3 -> +2V5 VCCAUX)\\n"
       "  U2 (+3V3 -> +1V1 VCC) EN = PG_3V3, 3.3 V oturunca kalkar\\n"
       "  yani  +3V3 (VCCIO)  ->  +2V5 (VCCAUX)  ->  +1V1 (VCC)\\n\\n"
       "Bu sayfada once 'VCC once, VCCIO en son' yaziyordu; YANLISTI.\\n"
       "Lattice ECP5 Hardware Checklist / sysIO Usage Guide:\\n"
       "'It is recommended that the I/O buffers be powered-up prior\\n"
       " to the FPGA core fabric, which means VCCIO supplies should\\n"
       " be powered before VCC and VCCAUX.'\\n"
       "Ustelik tersi topolojik olarak imkansiz: +1V1 bucki girisini\\n"
       "+3V3'ten aliyor, cekirdek rayi once kalkamaz.\\n"
       "Kart bastan beri dogrusunu yapiyor — degistirilmesi gereken\\n"
       "yazidir, devre degil.", 20, 212, 1.35)

s.text("+2V5 rayi ilk guc agacinda YOKTU. ECP5 VCCAUX'suz calismiyor;\\n"
       "kart basilmis olsaydi tel cekilecekti. 01_power U8, ADP150-2.5,\\n"
       "LCSC C144257.", 20, 240, 1.35)

# ================================================================== BIRIM 8
s.text("KONFIGURASYON — birim 8", 205, 14, 2.0)
s.text("Master SPI: FPGA acilista flash'i kendi okuyor", 205, 20, 1.4)

CX, CY = 232, 110
s.sym(E, "U10", "LFE5U-25F-7BG256I", CX, CY, fp=FE, unit=8)

s.pin_label(E, "L6", CX, CY, 0, "+3V3", "input")

# LED_RX BURAYA TASINDI — banka 2'deki K16'yi saat icin bosalttik.
# K16 = PCLKT2_0, bankanin saat-yetenekli tek ball'i; sistem saati
# (FPGA_CLK80) oraya girdi. LED'in saat pinine ihtiyaci yok.
# Banka 8 konfigurasyon bankasi ve VCCIO'su flash ile ayni +3V3,
# yani surus seviyesi degismiyor. Tek yan etki: yapilandirma
# sirasinda bu bacak titrer ve LED bir an yanip soner — zararsiz,
# hatta acilisin gorunur isareti.
s.pin_label(E, "R6", CX, CY, 0, "LED_RX", "output", d=5.08)

# --- SPI flash
FX, FY = 352, 60
s.sym(FLASH, "U11", "W25Q128JVSIQ", FX, FY, fp=FSOIC)

for fpin, net, shape in [("1", "CFG_CS", "input"),    # ~CS
                         ("2", "CFG_MISO", "output"),  # DO
                         ("3", "CFG_WP", "input"),     # ~WP / IO2
                         ("5", "CFG_MOSI", "input"),   # DI
                         ("6", "CFG_CLK", "input"),    # CLK
                         ("7", "CFG_HOLD", "input")]:  # ~HOLD / IO3
    s.pin_label(FLASH, fpin, FX, FY, 0, net, shape, d=25.4)
s.pin_label(FLASH, "8", FX, FY, 0, "+3V3", "input", d=7.62)
s.pin_power(FLASH, "4", FX, FY, 0, "GND")

# ~WP ve ~HOLD: quad mod acilirsa IO2/IO3 olacaklar, o yuzden
# dogrudan raya degil 10k uzerinden.
for i, (net, ref) in enumerate([("CFG_WP", "R20"), ("CFG_HOLD", "R21")]):
    rx, ry = 372, 88 + i * 16
    s.sym(R, ref, "10k", rx, ry, rot=90, fp=FR)
    s.pin_label(R, "1", rx, ry, 90, "+3V3", "input")
    s.pin_label(R, "2", rx, ry, 90, net, "passive")

s.text("~WP ve ~HOLD dogrudan +3V3'e DEGIL, 10k uzerinden.\\n"
       "Quad SPI'a gecersek bu iki bacak IO2/IO3 oluyor;\\n"
       "raya baglanmis olsalardi cip yanardi.", 300, 100, 1.3)

# --- FPGA tarafi SPI
for pin, net, shape in [("N8", "CFG_CS", "output"),     # ~CSSPI
                        ("N9", "CFG_CLK", "output"),    # MCLK/CCLK
                        ("T8", "CFG_MOSI", "output"),   # D0/PICO
                        ("T7", "CFG_MISO", "input")]:   # D1/POCI
    s.pin_label(E, pin, CX, CY, 0, net, shape)

s.text("SPI ESLESMESI\\n"
       "  N8 ~CSSPI  -> flash ~CS\\n"
       "  N9 MCLK    -> flash CLK   (kullanici bitstream'inde USRMCLK)\\n"
       "  T8 D0/PICO -> flash DI\\n"
       "  T7 D1/POCI <- flash DO\\n"
       "PICO/POCI Lattice'in MOSI/MISO adlandirmasi.", 300, 150, 1.3)

# --- CFG[2:0]: hem yukari hem asagi ayak izi
s.text("CFG[2:0] — MOD SECIMI", 205, 178, 1.6)
# MASTER SPI = CFGMDN[2:0] = 010  (TN1260 Tablo 5)
#   CFG0 = 0   asagi
#   CFG1 = 1   yukari
#   CFG2 = 0   asagi
# Direnc degerleri de veri sayfasindan, ve TAHMIN ETTIGIMDEN FARKLI:
# CFGMDN bacaklarinda DAHILI ZAYIF PULL-UP var. Asagi cekmek icin
# "external <500-Ohm pull-down resistors" gerekiyor — 10k ile asagi
# cekmeye calissaydim dahili pull-up'a karsi seviye belirsiz kalir,
# FPGA yanlis modda acilir ve bu yalniz JTAG'le anlasilirdi.
# Yukari cekme icin onerilen 4.7k.
CFGMDN = [("N10", "CFG0", 0), ("P10", "CFG1", 1), ("R10", "CFG2", 0)]
for i, (pin, name, seviye) in enumerate(CFGMDN):
    x = 212 + i * 30
    s.pin_label(E, pin, CX, CY, 0, name, "output")
    if seviye:
        s.sym(R, f"R{30 + i * 2}", "4.7k", x, 192, rot=90, fp=FR)
        s.pin_label(R, "1", x, 192, 90, "+3V3", "input")
        s.pin_label(R, "2", x, 192, 90, name, "passive")
    else:
        s.sym(R, f"R{31 + i * 2}", "470R", x, 216, rot=90, fp=FR)
        s.pin_label(R, "1", x, 216, 90, name, "passive")
        s.pin_power(R, "2", x, 216, 90, "GND")

s.text("MASTER SPI = CFGMDN[2:0] = 010   (TN1260 Tablo 5)\\n"
       "  CFG0 = 0  470R asagi\\n"
       "  CFG1 = 1  4.7k yukari\\n"
       "  CFG2 = 0  470R asagi\\n\\n"
       "** DIRENC DEGERLERI TAHMIN EDILEMEZDI. ** CFGMDN bacaklarinda\\n"
       "DAHILI ZAYIF PULL-UP var. TN1260: 'External <500-Ohm pull-down\\n"
       "resistors ensure that the CFGMDN pin senses a low.' Ilk cizimde\\n"
       "hem yukari hem asagi 10k ayak izi birakmistim; 10k ile asagi\\n"
       "cekmek dahili pull-up'a karsi seviyeyi BELIRSIZ birakirdi ve\\n"
       "FPGA rastgele modda acilirdi. Bu ariza yalniz JTAG'le anlasilir.\\n\\n"
       "Yukari cekme icin onerilen 4.7k (TN1260 ayni paragraf).\\n"
       "CFGMDN INITN'in yukselen kenarinda ornekleniyor.", 205, 232, 1.3)

# --- kontrol pinleri
s.text("KONTROL", 285, 188, 1.6)

# ~PROGRAM: pull-up + buton
s.pin_label(E, "R9", CX, CY, 0, "nPROGRAM", "input")
s.sym(R, "R36", "10k", 285, 200, rot=90, fp=FR)
s.pin_label(R, "1", 285, 200, 90, "+3V3", "input")
s.pin_label(R, "2", 285, 200, 90, "nPROGRAM", "passive")
s.sym(SW, "SW1", "PROG", 285, 224, fp=FSW)
s.pin_label(SW, "1", 285, 224, 0, "nPROGRAM", "passive")
s.pin_power(SW, "2", 285, 224, 0, "GND")

# ~INIT: sadece pull-up
s.pin_label(E, "T9", CX, CY, 0, "nINIT", "input")
s.sym(R, "R37", "10k", 320, 200, rot=90, fp=FR)
s.pin_label(R, "1", 320, 200, 90, "+3V3", "input")
s.pin_label(R, "2", 320, 200, 90, "nINIT", "passive")

# DONE: acik-drenaj, pull-up + LED
s.pin_label(E, "P9", CX, CY, 0, "DONE", "output")
s.sym(R, "R38", "10k", 352, 200, rot=90, fp=FR)
s.pin_label(R, "1", 352, 200, 90, "+3V3", "input")
s.pin_label(R, "2", 352, 200, 90, "DONE", "passive")
s.sym(R, "R39", "1k", 388, 200, rot=90, fp=FR)
s.pin_label(R, "1", 388, 200, 90, "DONE", "passive", d=12.7)
s.sym(LED, "D10", "yesil", 388, 224, rot=90, fp=FLED)
s.link(s.P(R, "2", 388, 200, 90), s.P(LED, "1", 388, 224, 90))
s.pin_power(LED, "2", 388, 224, 90, "GND")

s.text("DONE acik drenaj: FPGA yuklenene kadar asagida.\\n"
       "LED yandi = bitstream gecerli. Bringup'ta bakilacak ilk sey.\\n"
       "SW1 ~PROGRAM'i kisa devre yapinca yeniden yukleme basliyor.",
       290, 246, 1.3)

# --- JTAG
s.text("JTAG", 130, 62, 1.6)
JX, JY = 140, 80
s.sym(HDR, "J10", "JTAG 2x3", JX, JY, fp=FHDR)
for hp, net, shape in [("1", "JTAG_TCK", "input"), ("3", "JTAG_TMS", "input"),
                       ("5", "JTAG_TDI", "input"), ("2", "JTAG_TDO", "output")]:
    s.pin_label(HDR, hp, JX, JY, 0, net, shape, d=17.78)
s.pin_label(HDR, "4", JX, JY, 0, "+3V3", "output", d=17.78)
s.pin_power(HDR, "6", JX, JY, 0, "GND", d=10.16)

for pin, net, shape in [("T10", "JTAG_TCK", "input"), ("T11", "JTAG_TMS", "input"),
                        ("R11", "JTAG_TDI", "input"), ("M10", "JTAG_TDO", "output")]:
    s.pin_label(E, pin, CX, CY, 0, net, shape)

s.text("2.54 mm 2x3, kart KENARINA — kutu kapaliyken erisilebilsin.\\n"
       "Flash BOS gelecek: ilk bitstream buradan yuklenecek, sonra\\n"
       "flash JTAG uzerinden programlanacak. Bu baslik olmadan\\n"
       "kartin hicbir bringup yolu yok.\\n"
       "+3V3 pini programlayiciyi BESLEMEK icin degil, seviye\\n"
       "referansi icin (FT2232H/ft232r tarafi 3.3V gorsun).",
       115, 26, 1.3)

# --- kullanilmayan konfig bacaklari
s.text("KULLANILMAYAN KONFIG BACAKLARI\\n"
       "D2..D7, ~CS1, ~CSO/DOUT, ~WRITE, D4/PICO2, D5/POCI2 — bunlar\\n"
       "paralel/slave modlar icin. Master SPI'da bosta. Yine de\\n"
       "TEST NOKTASI birakiliyor: mod degistirmek gerekirse kart\\n"
       "revizyonu degil, bir tel yeter.", 20, 262, 1.3)

# R6 ARTIK BOS DEGIL — LED_RX oraya tasindi (yukari bak), listeden
# cikarildi. Kalmis olsaydi hem NC bayragi hem ag ayni bacakta
# olurdu; ERC bunu no_connect_connected diye gordu.
for pin in ["M7", "M8", "M9", "N7", "P7", "P8", "R7", "R8", "T6"]:
    s.nc(*s.P(E, pin, CX, CY))

s.write(os.path.join(HERE, "07_fpga_power.kicad_sch"))
print("07_fpga_power.kicad_sch yazildi")
