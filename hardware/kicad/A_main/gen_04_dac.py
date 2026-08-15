#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""04_dac: 2x AD9767, dort TX kanali. Kaynak: ../NETLIST.md §4."""
import json, os
from schlib import Sheet, unit_pins, yol_esle

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

D = "dogrudan-sdr:AD9767"
FD = "Package_QFP:LQFP-48_7x7mm_P0.5mm"
T = "dogrudan-sdr:ADT1-1WT"
FT = "RF_Mini-Circuits:Mini-Circuits_CD542_H2.84mm"
E = "dogrudan-sdr:ECP5-BGA256"
FE = ("Package_BGA:BGA-256_14.0x14.0mm_Layout16x16_P0.8mm_"
      "Ball0.45mm_Pad0.32mm_NSMD")
R, C, L = "Device:R", "Device:C", "Device:L"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
FL = "Inductor_SMD:L_0603_1608Metric"
CONN = "Connector:Conn_Coaxial"
FSMA = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"

s = Sheet("04_dac", "DAC x2", UU["04_dac"],
          "AD9767 x2, cift port (banka 2) + interleaved (banka 1)", paper="A1")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{399 + nr[0]}"


# ================================================================== DAC-1
s.text("DAC-1 — CIFT PORT (MODE = HIGH), banka 2", 16, 14, 2.0)

s.sym(D, "U30", "AD9767ASTZ", 60, 70, fp=FD, unit=1)
# PORT 1'IN BIT SIRASI TERSTI.
# Veri sayfasi Rev.C Tablo 6: pin 1 = DB13P1 (MSB) ... pin 14 = DB0P1.
# Bu depodaki sembol de boyle (lib/gen_symbols.py). Ama burada
# "DAC1_P1_D{13 - i}" yaziyordu, yani pin 1'e D0, pin 14'e D13 —
# port 1 ters, port 2 (asagida) dogru. AYNI CIPTE IKI PORT ZIT
# KONVANSIYONDA.
# Sonucu sessiz: LSB DAC'in MSB'sine gider, 14 bitlik kelime
# bit-ters permutasyona ugrar, cikis tam olcekli gurultu olur —
# ama butun hatlarda sinyal "var" gorunur, hicbir olcum eksik
# baglanti gostermez.
# Adi silikonla uyusturuyoruz, gateware'de telafi etmiyoruz:
# yalan soyleyen bir ag adi birakmak, sonraki kisiyi ayni tuzaga
# dusurur.
for i in range(14):
    s.pin_label(D, str(14 - i), 60, 70, 0, f"DAC1_P1_D{i}", "input", d=12.7)
s.pin_label(D, "17", 60, 70, 0, "DAC1_WRT1", "input", d=12.7)
# CLK1 SAAT AGACINDAN (02_clock), FPGA'dan DEGIL. Ilk cizimde
# ikisini de FPGA'ya baglamistim; o zaman TX saati RX saatiyle ayni
# kaynaktan gelmez ve faz uyumu — aletin butun ayirt edici ozelligi —
# kaybolurdu. WRT'ler FPGA'da kaliyor (veriyle senkron).
s.pin_label(D, "18", 60, 70, 0, "DAC1_CLK", "input", d=17.78)
s.pin_label(D, "16", 60, 70, 0, "+3V3", "input", d=22.86)
s.pin_power(D, "15", 60, 70, 0, "GND", d=7.62)

s.sym(D, "U30", "AD9767ASTZ", 60, 160, fp=FD, unit=2)
for i in range(14):
    s.pin_label(D, str(36 - i), 60, 160, 0, f"DAC1_P2_D{i}", "input", d=12.7)
s.pin_label(D, "20", 60, 160, 0, "DAC1_WRT2", "input", d=12.7)
s.pin_label(D, "19", 60, 160, 0, "DAC1_CLK", "input", d=17.78)
s.pin_label(D, "22", 60, 160, 0, "+3V3", "input", d=22.86)
s.pin_power(D, "21", 60, 160, 0, "GND", d=7.62)

s.text("CIFT PORT SECILDI. Interleaved veri yolunu 160 MHz'e cikariyor;\\n"
       "ADC'de cogullamaya EVET dedigimiz gerekcenin tersi burada gecerli:\\n"
       "orada pin butcesi zorluyordu, burada banka 2 zaten 32 pin veriyor.\\n"
       "32 hat @80 MHz, zamanlama rahat.", 16, 240, 1.35)

# ================================================================== DAC-2
s.text("DAC-2 — INTERLEAVED (MODE = LOW), banka 1", 200, 14, 2.0)

s.sym(D, "U31", "AD9767ASTZ", 250, 70, fp=FD, unit=1)
# U30 ile ayni ters siralama buradaydi — ayni duzeltme.
for i in range(14):
    s.pin_label(D, str(14 - i), 250, 70, 0, f"DAC2_D{i}", "input", d=12.7)
s.pin_label(D, "17", 250, 70, 0, "DAC2_IQWRT", "input", d=12.7)
s.pin_label(D, "18", 250, 70, 0, "DAC2_CLK", "input", d=17.78)
s.pin_label(D, "16", 250, 70, 0, "+3V3", "input", d=22.86)
s.pin_power(D, "15", 250, 70, 0, "GND", d=7.62)

s.sym(D, "U31", "AD9767ASTZ", 250, 160, fp=FD, unit=2)
s.pin_label(D, "19", 250, 160, 0, "DAC2_IQRESET", "input", d=12.7)
s.pin_label(D, "20", 250, 160, 0, "DAC2_IQSEL", "input", d=17.78)
s.pin_label(D, "22", 250, 160, 0, "+3V3", "input", d=22.86)
s.pin_power(D, "21", 250, 160, 0, "GND", d=7.62)
# interleaved modda ikinci port veri bacaklari kullanilmiyor
for i in range(14):
    s.nc(*s.P(D, str(36 - i), 250, 160))

s.text("INTERLEAVED: 18 pin (14 veri + IQWRT + IQCLK + IQRESET + IQSEL).\\n"
       "Cift port 32 pin isterdi, banka 1'de o kadar yer yok.\\n"
       "Bedeli: tek yol iki kanal tasiyor, 160 MHz'de suruluyor.\\n"
       "ECP5 -7'de yapilabilir ama zamanlama sikisik.\\n\\n"
       "IKINCI PORTUN VERI BACAKLARI (23-36) BOSTA — interleaved modda\\n"
       "kullanilmiyorlar. Yol cizilmiyor; rev B'de cift porta donulurse\\n"
       "banka plani bastan yapilir zaten.", 200, 240, 1.35)

# ================================================================== analog
s.text("ANALOG CIKIS VE REFERANS — birim 3", 400, 14, 2.0)


def analog(ref, x, y, n, mode_net):
    s.sym(D, ref, "AD9767ASTZ", x, y, fp=FD, unit=3)
    s.pin_label(D, "47", x, y, 0, "+3V3_A", "input", d=7.62)
    s.pin_power(D, "38", x, y, 0, "GND", d=7.62)          # ACOM
    s.pin_power(D, "42", x, y, 0, "GND", d=12.7)          # GAINCTRL -> ACOM
    s.pin_label(D, "48", x, y, 0, mode_net, "input", d=17.78)
    # SLEEP FPGA'dan DEGIL, ACOM'da. Ayni gerekce: guc-dusurme
    # kullanilmiyor, pin banka 0'da PA'ya acildi (08_control).
    s.pin_power(D, "37", x, y, 0, "GND", d=22.86)
    s.pin_label(D, "43", x, y, 0, f"REFIO_{ref}", "passive", d=27.94)
    s.pin_label(D, "44", x, y, 0, f"FSADJ1_{ref}", "passive", d=33.02)
    s.pin_label(D, "41", x, y, 0, f"FSADJ2_{ref}", "passive", d=38.1)
    s.pin_label(D, "46", x, y, 0, f"IOUT{n}A1", "output", d=7.62)
    s.pin_label(D, "45", x, y, 0, f"IOUT{n}B1", "output", d=12.7)
    s.pin_label(D, "39", x, y, 0, f"IOUT{n}A2", "output", d=17.78)
    s.pin_label(D, "40", x, y, 0, f"IOUT{n}B2", "output", d=22.86)

    bx = x + 30
    s.sym(C, cnt("C"), "100nF", bx, y + 45, fp=FC)
    s.pin_label(C, "1", bx, y + 45, 0, f"REFIO_{ref}", "passive")
    s.pin_power(C, "2", bx, y + 45, 0, "GND")
    for i, f in enumerate(("FSADJ1", "FSADJ2")):
        s.sym(R, cnt("R"), "1.92k 1%", bx + 20 + i * 22, y + 45, fp=FR)
        s.pin_label(R, "1", bx + 20 + i * 22, y + 45, 0, f"{f}_{ref}", "passive")
        s.pin_power(R, "2", bx + 20 + i * 22, y + 45, 0, "GND")


analog("U30", 430, 70, 1, "+3V3")
analog("U31", 430, 175, 2, "GND_MODE")

# DAC-2 MODE = LOW: interleaved. Toprak sembolu dogrudan pine degil,
# ag uzerinden — cift yonlu degistirilebilsin diye 0R ile.
s.sym(R, "R450", "0R", 430, 260, fp=FR)
s.pin_label(R, "1", 430, 260, 0, "GND_MODE", "passive")
s.pin_power(R, "2", 430, 260, 0, "GND")
s.text("DAC-2 MODE bacagi 0R ile toprakta. Dogrudan bakir yerine direnc:\\n"
       "cift porta donme karari cikarsa direnci +3V3'e almak yetiyor,\\n"
       "kart kesilmiyor.", 415, 268, 1.3)

s.text("IOUTFS = 32 x (1.2 / R_set).  20 mA icin R_set = 1.92k.\\n"
       "%1 direnc: %5 kullanilirsa cikis genligi %5 kayiyor ve iki DAC\\n"
       "arasinda dengesizlik olusuyor — MIMO'da genlik esitligi lazim.\\n\\n"
       "GAINCTRL ACOM'da = dahili 1.2 V referans, master modu.\\n"
       "REFIO 100nF ile ACOM'a.", 400, 300, 1.35)

# ------------------------------------------------------------------ cikis
s.text("CIKIS AGI — kanal basina", 200, 292, 1.6)


def output(ref, jref, x, y, ia, ib, ch):
    """Diferansiyel akim cikisi -> trafo -> 50 ohm -> SMA.
    Datasheet: cift sonlandirmali, trafo kuplajli."""
    # IKI SONLANDIRMA ALT ALTA, YAN YANA DEGIL. Yan yana koydugumda
    # (14 mm arayla) birinin GND saplamasi digerinin sinyal saplamasiyla
    # ayni yatay hatta bindi: IOUTxB1 dogrudan toprakla birlesti,
    # semada gorunmuyordu, netlist'te 133 pinlik dev bir ag olarak cikti.
    s.sym(R, cnt("R"), "50R 1%", x, y - 6.35, rot=90, fp=FR)
    s.pin_label(R, "1", x, y - 6.35, 90, ia, "passive")
    s.pin_power(R, "2", x, y - 6.35, 90, "GND")
    s.sym(R, cnt("R"), "50R 1%", x, y + 6.35, rot=90, fp=FR)
    s.pin_label(R, "1", x, y + 6.35, 90, ib, "passive")
    s.pin_power(R, "2", x, y + 6.35, 90, "GND")

    # Pin numaralari veri sayfasindan duzeltildi: orta uc 2, bos bacak 5.
    # (Once tersini yazmistim.) Burada orta uc topraga: DAC'in DC
    # bileseninin donus yolu.
    s.sym(T, ref, "ADT1-1WT+", x + 45, y, fp=FT)
    s.pin_label(T, "6", x + 45, y, 0, ia, "input", d=12.7)
    s.pin_label(T, "4", x + 45, y, 0, ib, "input", d=12.7)
    s.pin_power(T, "2", x + 45, y, 0, "GND", d=7.62)
    s.pin_label(T, "3", x + 45, y, 0, f"TX_{ch}", "output", d=12.7)
    s.pin_power(T, "1", x + 45, y, 0, "GND", d=17.78)
    s.nc(*s.P(T, "5", x + 45, y))

    s.sym(CONN, jref, f"SMA TX{ch}", x + 90, y, fp=FSMA)
    s.pin_label(CONN, "1", x + 90, y, 0, f"TX_{ch}", "input")
    s.pin_power(CONN, "2", x + 90, y, 0, "GND")


for i, (ia, ib, ch) in enumerate([("IOUT1A1", "IOUT1B1", "1"),
                                  ("IOUT1A2", "IOUT1B2", "2"),
                                  ("IOUT2A1", "IOUT2B1", "3"),
                                  ("IOUT2A2", "IOUT2B2", "4")]):
    output(f"T{10 + i}", f"J{30 + i}", 210, 305 + i * 28, ia, ib, ch)

s.text("Rekonstruksiyon filtresi (36 MHz LPF) ve surucu C KARTINDA.\\n"
       "Burada sadece 50R cift sonlandirma + trafo kuplaj var — datasheet\\n"
       "onerdigi cikis agi. Filtre bant secimine bagli, o yuzden ayri kartta;\\n"
       "TX bandi degistirilirse burasi degismiyor.", 200, 425, 1.35)

# ================================================================== FPGA
s.text("FPGA BANKA 2 — DAC-1 cift port", 16, 285, 2.0)
B2X, B2Y = 75, 350
s.sym(E, "U10", "LFE5U-25F-7BG256I", B2X, B2Y, fp=FE, unit=4)
B2 = unit_pins(E, 4)
nets2 = ([f"DAC1_P1_D{i}" for i in range(14)] +
         [f"DAC1_P2_D{i}" for i in range(14)] +
         ["DAC1_WRT1", "DAC1_WRT2"] +
         # Banka 2'nin iki bos pini: biri durum LED'i, biri SISTEM
         # SAATININ GIRISI.
         # Once ikisi de LED'di (LED_STATUS, LED_RX) ve FPGA'ya hic
         # saat girmiyordu — ADCLK846'nin FPGA cikisi sonlandirma
         # direncinde bitiyordu (bkz. gen_02_clock.py, U18).
         # LED_RX banka 8'e (R6) tasindi; bosalan ball K16 saate
         # verildi. K16 = PCLKT2_0, yani bankanin GERCEK saat pini;
         # bir LED'i orada tutup saati baska yere koymak, saat
         # yetenegi olan tek ball'i cope atmak olurdu.
         ["LED_STATUS", "FPGA_CLK80"])
io2 = sorted(n for n, nm in B2.items() if nm.startswith("PR"))
assert len(io2) == 32 and len(nets2) == 32, (len(io2), len(nets2))
for p, net in yol_esle(io2, nets2, "DAC1_P1", "DAC1_P2", "DAC2"):
    # SAAT GIRIS, GERISI CIKIS. Hepsini "output" yazarsak FPGA_CLK80
    # uzerinde iki surucu gorunur (U18 pin 5 ve U10 K16) ve ERC
    # bunu cakisma sayar.
    yon = "input" if net == "FPGA_CLK80" else "output"
    s.pin_label(E, p, B2X, B2Y, 0, net, yon, d=7.62)
for p in io2[len(nets2):]:
    s.nc(*s.P(E, p, B2X, B2Y))
for n, nm in sorted(B2.items()):
    if nm.startswith("VCCIO"):
        s.pin_label(E, n, B2X, B2Y, 0, "+3V3", "input", d=15.24)

s.text("BANKA 2: 28 veri + 2 yazma = 30/32, iki pin BOS.\\n"
       "Saat pinleri buradan cikti — DAC saatleri 02_clock'tan geliyor.\\n"
       "VCCIO2 = +3V3 — AD9767'nin lojik-1 esigi DVDD 3.3 V'ta 2.1 V,\\n"
       "1.8 V bankadan surulemez. ADC tarafinin tersine burada 3.3 V sart.\\n"
       "CLK1/CLK2 saat-yetenekli pine dusmeli; Lattice pinout CSV'siyle\\n"
       "bu liste yeniden siralanacak.", 16, 293, 1.35)

# ---- pin basina ayristirma
s.text("AYRISTIRMA", 200, 455, 1.6)
s.decaps("+3V3_A", 2, "100nF", 205, 470, 460, per_row=4)   # AVDD x2 cip
s.decaps("+3V3", 4, "100nF", 250, 470, 470, per_row=4)     # DVDD1/2 x2 cip
s.decaps("+3V3_A", 2, "10uF", 340, 470, 480, per_row=2)
s.text("AVDD (47) her cipte 1, DVDD1/DVDD2 (16, 22) her cipte 2.\\n"
       "AVDD +3V3_A'dan (kendi LDO'su), DVDD ana +3V3'ten — DAC'in\\n"
       "dijital anahtarlamasi analog tarafa kuplemasin.", 205, 492, 1.3)

s.write(os.path.join(HERE, "04_dac.kicad_sch"))
print("04_dac.kicad_sch yazildi")
