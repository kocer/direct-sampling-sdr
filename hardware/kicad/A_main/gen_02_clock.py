#!/usr/bin/env python3
"""02_clock: ABLNO-V 80 MHz VCXO + ADCLK846 1:6 LVDS dagitim.
Kaynak: ../NETLIST.md §2, ADCLK846 Rev.C, AD9251 Rev.C."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

X = "dogrudan-sdr:ABLNO-V"
FX = "dogrudan-sdr:Oscillator_Abracon_ABLNO_4pad_14.3x8.7mm"
B = "dogrudan-sdr:ADCLK846"
FB = "Package_DFN_QFN:HVQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm_ThermalVias"
LV = "Interface:SN65LVDS2DBV"
FLV = "Package_TO_SOT_SMD:SOT-23-5"
R, C, L = "Device:R", "Device:C", "Device:L"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
FFB = "Inductor_SMD:L_0603_1608Metric"
CONN = "Connector:Conn_Coaxial"
FSMA = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"

s = Sheet("02_clock", "Saat dagitimi", UU["02_clock"],
          "ABLNO-V 80MHz VCXO + ADCLK846 1:6 LVDS fanout", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{199 + nr[0]}"


s.text("SAAT DAGITIMI — aletin manset ozelligi bu sayfada", 16, 14, 2.0)
s.text("Dort ADC kanali ve iki DAC ayni saatten besleniyor. Gurultu iptali,\\n"
       "yon bulma ve isin sekillendirme bu dagitimin simetrisine bagli.",
       16, 20, 1.35)

# ================================================================== VCXO
s.text("VCXO — ABLNO-V, 80.000 MHz", 16, 40, 1.6)
s.sym(X, "Y10", "ABLNO-V-80.000MHZ", 55, 70, fp=FX)
s.pin_label(X, "1", 55, 70, 0, "VCXO_VC", "input", d=10.16)
s.pin_label(X, "4", 55, 70, 0, "VCXO_VDD", "input", d=10.16)
s.pin_label(X, "3", 55, 70, 0, "CLK80", "output", d=10.16)
s.pin_power(X, "2", 55, 70, 0, "GND", d=7.62)
# VCXO beslemesi ferritten geciyor, ferrit pasif: ERC bu rayda bir
# guc kaynagi goremiyor. Bayrak, gercek baglanti degil.
s.glabel("VCXO_VDD", 30, 40, "input")
s.wire(30, 40, 30, 33.65)
s.pwr_flag(30, 33.65)

# ferrit + ayristirma: besleme gurultusu DOGRUDAN faz gurultusu
s.sym(L, "FB10", "ferrit 600R", 55, 40, rot=90, fp=FFB)
s.pin_label(L, "1", 55, 40, 90, "+3V3_CLK", "input")
s.pin_label(L, "2", 55, 40, 90, "VCXO_VDD", "output")
for i, v in enumerate(("100nF", "10uF")):
    s.sym(C, cnt("C"), v, 95 + i * 20, 45, rot=90, fp=FC)
    s.pin_label(C, "1", 95 + i * 20, 45, 90, "VCXO_VDD", "passive")
    s.pin_power(C, "2", 95 + i * 20, 45, 90, "GND")

s.text("Besleme gurultusu DOGRUDAN faz gurultusune donusuyor.\\n"
       "Kendi LDO'su (01_power U6) + ferrit boncuk + ayri toprak adasi.\\n"
       "Olculen: 90.3 fs @50 MHz, 80 MHz'de <100 fs bekleniyor.\\n"
       "Vc GPSDO'dan (08_control), DAC ile suruluyor.", 16, 95, 1.3)

# ================================================================== arayuz
s.text("VCXO -> TAMPON ARAYUZU — seviye uyumu SART", 16, 125, 1.6)

# 3.3 V CMOS cikisi 1.8 V p-p sinira indiriliyor
s.sym(R, "R210", "220R", 60, 145, rot=90, fp=FR)
s.pin_label(R, "1", 60, 145, 90, "CLK80", "passive")
s.pin_label(R, "2", 60, 145, 90, "CLK80_DIV", "passive")
s.sym(R, "R211", "100R", 85, 158, rot=90, fp=FR)
s.pin_label(R, "1", 85, 158, 90, "CLK80_DIV", "passive")
s.pin_power(R, "2", 85, 158, 90, "GND")

s.sym(C, "C210", "100nF", 110, 145, rot=90, fp=FC)
s.pin_label(C, "1", 110, 145, 90, "CLK80_DIV", "passive")
s.pin_label(C, "2", 110, 145, 90, "BUFCLK_P", "passive")
s.sym(C, "C211", "100nF", 110, 170, rot=90, fp=FC)
s.pin_label(C, "1", 110, 170, 90, "BUFCLK_N", "passive")
s.pin_power(C, "2", 110, 170, 90, "GND")

# her iki giris VREF'e (VS/2 = 0.9 V) 1k ile bias
for i, net in enumerate(("BUFCLK_P", "BUFCLK_N")):
    s.sym(R, f"R{212 + i}", "1k", 145, 145 + i * 25, rot=90, fp=FR)
    s.pin_label(R, "1", 145, 145 + i * 25, 90, "CLK_VREF", "passive")
    s.pin_label(R, "2", 145, 145 + i * 25, 90, net, "passive")
s.sym(C, "C212", "100nF", 175, 158, rot=90, fp=FC)
s.pin_label(C, "1", 175, 158, 90, "CLK_VREF", "passive")
s.pin_power(C, "2", 175, 158, 90, "GND")

s.text("** BU BOLUM ILK PLANDA YOKTU. ** VCXO cikisi 3.3 V LVCMOS,\\n"
       "ADCLK846 girisinin AZAMI seviyesi 1.8 V p-p (Tablo 1):\\n"
       "'Larger voltage swings can turn on the protection diodes and\\n"
       "can degrade jitter performance.' Dogrudan baglansaydi koruma\\n"
       "diyotlari iletime girer, jitter bozulurdu — yani aletin manset\\n"
       "ozelligi ilk baglantida olurdu.\\n\\n"
       "220R/100R bolucu: 3.3 x 100/320 = 1.03 V p-p. Sinirin altinda.\\n"
       "Direncle bolmek kenar hizini bozmuyor, sadece olcekliyor —\\n"
       "veri sayfasi 'jitter improves with higher slew rate' diyor,\\n"
       "o yuzden RC yerine direnc bolucu.\\n\\n"
       "AC kuplaj + VREF (pin 1, VS/2 = 0.9 V) ile bias. CLK- ucu\\n"
       "100nF ile AC toprakta: tek uclu kaynagi diferansiyel girise\\n"
       "boyle veriyoruz. Giris hassasiyeti 150 mV p-p, 1.03 V bol bol.\\n"
       "VREF sadece +-500 uA verebiliyor: 1k'lar 0.9 mA cekmiyor cunku\\n"
       "iki uc de ayni gerilimde, net akim ~0.", 16, 190, 1.3)

# ================================================================== tampon
s.text("ADCLK846 — 1:6 LVDS", 300, 40, 2.0)
BX, BY = 340, 110
s.sym(B, "U15", "ADCLK846BCPZ", BX, BY, fp=FB, unit=1)
s.pin_label(B, "3", BX, BY, 0, "BUFCLK_P", "input", d=10.16)
s.pin_label(B, "2", BX, BY, 0, "BUFCLK_N", "input", d=15.24)
s.pin_label(B, "1", BX, BY, 0, "CLK_VREF", "output", d=20.32)
s.pin_power(B, "5", BX, BY, 0, "GND", d=25.4)      # CTRL_A = 0 -> LVDS
s.pin_power(B, "6", BX, BY, 0, "GND", d=30.48)     # CTRL_B = 0 -> LVDS
s.pin_power(B, "7", BX, BY, 0, "GND", d=35.56)     # SLEEP = 0 -> normal

outs = [("24", "23", "ADCLK_U20", "ADC-1"),
        ("21", "20", "ADCLK_U21", "ADC-2"),
        ("18", "17", "FPGA_PCLK", "FPGA"),
        ("15", "14", "DACCLK_LV1", "DAC-1 cevirici"),
        ("12", "11", "DACCLK_LV2", "DAC-2 cevirici"),
        ("9", "8", "CLKTEST", "test noktasi")]
for i, (a, b, net, what) in enumerate(outs):
    s.pin_label(B, a, BX, BY, 0, f"{net}_P", "output", d=10.16)
    s.pin_label(B, b, BX, BY, 0, f"{net}_N", "output", d=15.24)

# guc: 1.8 V, kendi rayi
s.sym(B, "U15", "ADCLK846BCPZ", 440, 230, fp=FB, unit=2)
for i, p in enumerate(("4", "10", "13", "16", "19", "22")):
    s.pin_label(B, p, 440, 230, 0, "+1V8_CLK", "input", d=5.08)
s.pin_power(B, "25", 440, 230, 0, "GND", d=5.08)
for i, v in enumerate(("100nF", "100nF", "100nF", "10uF")):
    s.sym(C, cnt("C"), v, 490 + i * 18, 230, rot=90, fp=FC)
    s.pin_label(C, "1", 490 + i * 18, 230, 90, "+1V8_CLK", "passive")
    s.pin_power(C, "2", 490 + i * 18, 230, 90, "GND")

s.text("** VS = 1.8 V, 3.3 V DEGIL. ** Veri sayfasinin basligi:\\n"
       "'1.8 V, 6 LVDS/12 CMOS Output Clock Fanout Buffer'.\\n"
       "Guc agacinda saat bolumu bastan 3.3 V varsayilmisti; tampona\\n"
       "kendi +1V8_CLK rayi eklendi (01_power U9, ADP150-1.8, +2V5'ten\\n"
       "besleniyor — 3.3'ten dusurmek gereksiz isi uretirdi).\\n\\n"
       "Acik ped (25) TOPRAGA, termal via dizisiyle. Veri sayfasi:\\n"
       "'EXPOSED PADDLE MUST BE CONNECTED TO GND.'\\n\\n"
       "CTRL_A = CTRL_B = 0 -> alti cikis da LVDS.\\n"
       "CMOS moduna alinabilirdi ama cikis 1.8 V CMOS olurdu ve\\n"
       "AD9767'nin lojik-1 esigi 2.1 V — yetmezdi. Onun icin DAC\\n"
       "saatleri LVDS cikip asagida cevriliyor.", 300, 265, 1.3)

# ================================================================== ADC yolu
s.text("ADC SAATLERI — LVDS, DOGRUDAN", 300, 200, 1.6)
for i, (net, ref) in enumerate([("ADCLK_U20", "R220"), ("ADCLK_U21", "R221")]):
    s.sym(R, ref, "100R", 320 + i * 40, 215, rot=90, fp=FR)
    s.pin_label(R, "1", 320 + i * 40, 215, 90, f"{net}_P", "passive")
    s.pin_label(R, "2", 320 + i * 40, 215, 90, f"{net}_N", "passive")
s.sym(R, "R222", "100R", 400, 215, rot=90, fp=FR)
s.pin_label(R, "1", 400, 215, 90, "FPGA_PCLK_P", "passive")
s.pin_label(R, "2", 400, 215, 90, "FPGA_PCLK_N", "passive")

s.text("Her LVDS ciftinin ucunda 100R sonlandirma, ALICIYA yakin.\\n"
       "AD9251 saat girisi PECL/LVDS/1.8V CMOS kabul ediyor (Rev.C),\\n"
       "cevirici gerekmiyor.\\n\\n"
       "** IKI YOL ES UZUNLUKTA. ** Cikislar arasi skew veri sayfasinda\\n"
       "65 ps (ayni parca uzerinde). Bu SABIT bir fark, kalibre edilebilir;\\n"
       "yol uzunlugu farki ise sicaklikla oynar, edilemez.", 300, 230, 1.3)

# ================================================================== DAC yolu
s.text("DAC SAATLERI — LVDS -> 3.3 V CMOS cevirici", 16, 300, 2.0)
for i, (net, ref, out) in enumerate([("DACCLK_LV1", "U16", "DAC1_CLK"),
                                     ("DACCLK_LV2", "U17", "DAC2_CLK")]):
    lx, ly = 60 + i * 130, 335
    s.sym(R, cnt("R"), "100R", lx - 25, ly, rot=90, fp=FR)
    s.pin_label(R, "1", lx - 25, ly, 90, f"{net}_P", "passive")
    s.pin_label(R, "2", lx - 25, ly, 90, f"{net}_N", "passive")
    s.sym(LV, ref, "SN65LVDS2DBVR", lx + 20, ly, fp=FLV)
    # SOT-23-5 dizilimi: 1 VCC, 2 GND, 3 A, 4 B, 5 R (cikis).
    s.pin_label(LV, "3", lx + 20, ly, 0, f"{net}_P", "input", d=10.16)
    s.pin_label(LV, "4", lx + 20, ly, 0, f"{net}_N", "input", d=15.24)
    s.pin_label(LV, "5", lx + 20, ly, 0, out, "output", d=10.16)
    s.pin_label(LV, "1", lx + 20, ly, 0, "+3V3", "input", d=15.24)
    s.pin_power(LV, "2", lx + 20, ly, 0, "GND", d=7.62)
    s.sym(C, cnt("C"), "100nF", lx + 55, ly, rot=90, fp=FC)
    s.pin_label(C, "1", lx + 55, ly, 90, "+3V3", "input")
    s.pin_power(C, "2", lx + 55, ly, 90, "GND")

s.text("SN65LVDS2DBVR — LVDS alici, LVTTL cikis, SOT-23-5.\\n"
       "LCSC C38204, $0.36, 1244 stok.\\n\\n"
       "NETLIST.md §10.2c bu ceviriciyi acik madde birakmisti; kapandi.\\n"
       "Neden FPGA'dan uretmedik: FPGA cikis jitter'i ps mertebesinde,\\n"
       "verilen sinyalin faz gurultusune dogrudan giriyor. 36 kurusluk\\n"
       "parca TX spektrumunu kurtariyor.\\n\\n"
       "DAC1_CLK cipin hem CLK1 hem CLK2 bacagina gidiyor (cift port,\\n"
       "iki kanal ayni saatte). DAC2 interleaved, tek IQCLK.",
       16, 355, 1.3)

# ================================================================== test
s.text("TEST NOKTASI", 300, 335, 1.6)
s.sym(R, "R230", "100R", 320, 350, rot=90, fp=FR)
s.pin_label(R, "1", 320, 350, 90, "CLKTEST_P", "passive")
s.pin_label(R, "2", 320, 350, 90, "CLKTEST_N", "passive")
s.text("Alti numarali cikis test icin sonlandirilmis. Bringup'ta\\n"
       "osiloskopla saatin gercekten 80 MHz oldugu buradan gorulur —\\n"
       "TASARIM.md §11 adim 2. Kart kenarina iki pad.", 300, 358, 1.3)

# ================================================================== butce
s.text("JITTER BUTCESI — artik tahmin degil", 460, 40, 1.6)
s.text("ADCLK846 eklemeli jitter (Tablo 1):\\n"
       "   54 fs rms   12 kHz - 20 MHz\\n"
       "   86 fs rms   10 Hz - 100 MHz\\n"
       "  150 fs rms   genis bant, 1 V/ns kenar hizinda\\n\\n"
       "VCXO 60 fs ile birlikte:\\n"
       "  dar bant   sqrt(60^2 + 54^2)  =  81 fs\\n"
       "  genis bant sqrt(60^2 + 150^2) = 162 fs\\n\\n"
       "SNR tavani = -20*log10(2*pi*f*tj):\\n"
       "   30 MHz @  81 fs  ->  96 dB    ADC'nin kendi SNR'i sinir\\n"
       "  500 MHz @  81 fs  ->  72 dB    sinirda\\n"
       "  500 MHz @ 162 fs  ->  66 dB    JITTER SINIRLIYOR\\n\\n"
       "SONUC: HF ve VHF'te ADC'nin kendi gurultusu sinir, saat degil.\\n"
       "UHF alt-orneklemede (500 MHz civari) saat jitter'i one geciyor.\\n"
       "Bu kacinilmaz degil ama bu parcayla kacinilmaz — daha iyisi\\n"
       "(LMK04828 sinifi) on kat pahali. UHF'te 66 dB SNR yine de\\n"
       "11 bit efektif demek; kabul.", 460, 50, 1.25)

# ================================================================== FPGA saati
# FPGA'YA HIC SAAT GIRMIYORDU.
# ADCLK846'nin FPGA'ya ayrilan cikisi (pin 18/17 -> FPGA_PCLK_P/N)
# 100R sonlandirmaya (R222) gidip BITIYORDU: agin uclari yalnizca
# R222 ve U15'ti, U10 hic yoktu. NETLIST.md §2 niyeti yazmis ama
# baglanti cizilmemis.
#
# VCXO_CLK saat sanilabilir, degil: adi yaniltici, o VCXO'nun
# varaktorunu suren SPI DAC'inin SCK'si, yani bir FPGA CIKISI.
#
# FPGA'ya giren saat-yetenekli baska sinyaller vardi (ADC1_DCO,
# ADC2_DCO, PHY_RXC, REF10_IN) ama hicbiri clk_sys degil. Yani
# clk_sys uzerinde kosan her sey olu: PLL, ethernet, DDC arkasi,
# paketleyici, kayit dosyasi, UART, DAC besleme.
#
# NEDEN ADC1_DCO'yu clk_sys yapmadik: o zaman FPGA'nin saati butun
# saat agacina bagimli olurdu. Agacta bir sorun cikarsa FPGA komple
# oluyor ve hicbir tanisi kalmiyor. Kart daha uretilmedi; dogru olan
# izi cizmek, kalani yazilimla kurtarmaya calismak degil.
#
# Cozum DAC saatlerindekiyle AYNI desen: LVDS'i tek uclu 3.3 V
# CMOS'a ceviren SN65LVDS2 (kartta zaten iki tane var, U16/U17).
# R222 sonlandirma olarak yerinde kaliyor.
s.text("FPGA SAATI — LVDS -> 3.3 V CMOS", 16, 400, 2.0)
FX, FY = 60, 435
s.sym(LV, "U18", "SN65LVDS2DBVR", FX, FY, fp=FLV)
s.pin_label(LV, "3", FX, FY, 0, "FPGA_PCLK_P", "input", d=10.16)
s.pin_label(LV, "4", FX, FY, 0, "FPGA_PCLK_N", "input", d=15.24)
s.pin_label(LV, "5", FX, FY, 0, "FPGA_CLK80", "output", d=10.16)
s.pin_label(LV, "1", FX, FY, 0, "+3V3", "input", d=15.24)
s.pin_power(LV, "2", FX, FY, 0, "GND", d=7.62)
s.sym(C, cnt("C"), "100nF", FX + 35, FY, rot=90, fp=FC)
s.pin_label(C, "1", FX + 35, FY, 90, "+3V3", "passive")
s.pin_power(C, "2", FX + 35, FY, 90, "GND")

s.text("U18 cikisi FPGA_CLK80 -> U10 ball K16 (PCLKT2_0, banka 2,\\n"
       "VCCIO +3V3). Gercek saat pini ve seviyesi birebir uyuyor.\\n"
       "K16 bosalsin diye LED_RX banka 8'e (R6) tasindi.\\n\\n"
       "U18 yerlesimde U15'e YAKIN durmali: aradaki LVDS cifti ne\\n"
       "kadar kisaysa o kadar az ortak mod gurultusu topluyor.\\n"
       "Sonlandirma R222 alicinin dibinde kaliyor.", 16, 455, 1.3)

s.write(os.path.join(HERE, "02_clock.kicad_sch"))
print("02_clock.kicad_sch yazildi")
