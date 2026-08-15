#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""05_sdram: W9825G6KH-6I 32 MB, banka 7 + 0. Kaynak: ../NETLIST.md §4b."""
import json, os
from schlib import Sheet, unit_pins, yol_esle

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

M = "dogrudan-sdr:W9825G6KH"
FM = "Package_SO:TSOP-II-54_22.2x10.16mm_P0.8mm"
E = "dogrudan-sdr:ECP5-BGA256"
FE = ("Package_BGA:BGA-256_14.0x14.0mm_Layout16x16_P0.8mm_"
      "Ball0.45mm_Pad0.32mm_NSMD")
R, C = "Device:R", "Device:C"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"

s = Sheet("05_sdram", "SDRAM", UU["05_sdram"],
          "W9825G6KH-6I 32MB, veri banka 7, komut banka 0", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{499 + nr[0]}"


s.text("SDRAM — W9825G6KH-6I, 32 MB", 16, 14, 2.0)
s.text("Patlama yakalama icin. ECP5'in dahili blok RAM'i 1008 kbit = 126 KB,\\n"
       "tam hizda 0.79 ms eder — meteor olayinin sadece on kenarini yakalar.\\n"
       "32 MB / 160 MB/s = 200 ms. 250 kat.\\n\\n"
       "DDR3 DEGIL, SDR. Kasten: DDR3'un fly-by yonlendirmesi, ODT'si ve\\n"
       "kalibrasyonu rev A'ya agir yuk. SDR tek cip, duz yonlendirme,\\n"
       "LiteDRAM destekliyor.", 16, 20, 1.35)

# ------------------------------------------------------------------ veri
s.text("VERI YOLU — birim 1, banka 7", 16, 60, 1.6)
MX, MY = 70, 110
s.sym(M, "U50", "W9825G6KH-6I", MX, MY, fp=FM, unit=1)
for i in range(16):
    s.pin_label(M, str([2, 4, 5, 7, 8, 10, 11, 13,
                        42, 44, 45, 47, 48, 50, 51, 53][i]),
                MX, MY, 0, f"SD_DQ{i}", "bidirectional", d=7.62)
s.pin_label(M, "15", MX, MY, 0, "SD_LDQM", "input", d=7.62)
s.pin_label(M, "39", MX, MY, 0, "SD_UDQM", "input", d=12.7)

# ------------------------------------------------------------------ komut
s.text("ADRES VE KOMUT — birim 2", 16, 165, 1.6)
CXX, CYY = 70, 215
s.sym(M, "U50", "W9825G6KH-6I", CXX, CYY, fp=FM, unit=2)
for a, num in enumerate([23, 24, 25, 26, 29, 30, 31, 32, 33, 34, 22, 35, 36]):
    s.pin_label(M, str(num), CXX, CYY, 0, f"SD_A{a}", "input", d=7.62)
for num, net, d in [("20", "SD_BA0", 7.62), ("21", "SD_BA1", 12.7),
                    ("19", "SD_nCS", 17.78), ("18", "SD_nRAS", 22.86),
                    ("17", "SD_nCAS", 27.94), ("16", "SD_nWE", 33.02),
                    ("37", "SD_CKE", 38.1), ("38", "SD_CLK", 43.18)]:
    s.pin_label(M, num, CXX, CYY, 0, net, "input", d=d)
s.nc(*s.P(M, "40", CXX, CYY))

# ------------------------------------------------------------------ guc
s.text("GUC", 16, 285, 1.6)
GX, GY = 80, 310
s.sym(M, "U50", "W9825G6KH-6I", GX, GY, fp=FM, unit=3)
for num in ("1", "14", "27"):
    s.pin_label(M, num, GX, GY, 0, "+3V3", "input", d=5.08)
for num in ("3", "9", "43", "49"):
    s.pin_label(M, num, GX, GY, 0, "+3V3", "input", d=10.16)
for num in ("28", "41", "54"):
    s.pin_power(M, num, GX, GY, 0, "GND", d=5.08)
for num in ("6", "12", "46", "52"):
    s.pin_power(M, num, GX, GY, 0, "GND", d=10.16)

for i in range(6):
    s.sym(C, cnt("C"), "100nF", 150 + i * 20, 330, fp=FC)
    s.pin_label(C, "1", 150 + i * 20, 330, 0, "+3V3", "input")
    s.pin_power(C, "2", 150 + i * 20, 330, 0, "GND")
s.sym(C, cnt("C"), "10uF", 150 + 6 * 20, 330, fp=FC)
s.pin_label(C, "1", 150 + 6 * 20, 330, 0, "+3V3", "input")
s.pin_power(C, "2", 150 + 6 * 20, 330, 0, "GND")

s.text("VDD ve VDDQ ayni +3V3 rayindan. Ayristirma: her VDD/VDDQ ciftine\\n"
       "bir 100nF (alti adet) + toplu 10uF. 166 MHz'de akim adimlari\\n"
       "keskin; kondansatorler bacaga en yakin, viasi dogrudan duzleme.",
       150, 348, 1.35)

# ------------------------------------------------------------------ CLK
s.text("SAAT SONLANDIRMA", 16, 375, 1.6)
s.sym(R, "R550", "22R", 60, 392, fp=FR)
s.pin_label(R, "1", 60, 392, 0, "SD_CLK_FPGA", "input")
s.pin_label(R, "2", 60, 392, 0, "SD_CLK", "output")
s.text("CLK hattinda 22R SERI sonlandirma, FPGA cikisina yakin.\\n"
       "Tek yuk oldugu icin seri sonlandirma yetiyor; yansimasi\\n"
       "kaynaga donunce sonuyor. 166 MHz'de yol uzunlugu farki\\n"
       "setup marjini yiyor — CLK ile DQ grubunu es boy cek.",
       16, 400, 1.35)

# ------------------------------------------------------------------ FPGA
s.text("FPGA BANKA 7 — veri yolu", 300, 14, 2.0)
B7X, B7Y = 360, 90
s.sym(E, "U10", "LFE5U-25F-7BG256I", B7X, B7Y, fp=FE, unit=7)
B7 = unit_pins(E, 7)
nets7 = ([f"SD_DQ{i}" for i in range(16)] +
         [f"SD_A{i}" for i in range(9)] +
         ["SD_nCS", "SD_nRAS", "SD_nCAS", "SD_nWE", "SD_CKE",
          "SD_CLK_FPGA", "SD_LDQM"])
io7 = sorted(n for n, nm in B7.items() if nm.startswith("PL"))
assert len(nets7) == 32 and len(io7) == 32, (len(nets7), len(io7))
for p, net in yol_esle(io7, nets7, "SDRAM_B7"):
    s.pin_label(E, p, B7X, B7Y, 0, net, "bidirectional", d=7.62)
for n, nm in sorted(B7.items()):
    if nm.startswith("VCCIO"):
        s.pin_label(E, n, B7X, B7Y, 0, "+3V3", "input", d=15.24)

s.text("BANKA 7 TAM DOLU: 16 DQ + 9 adres + 6 komut + CLK = 32/32.\\n"
       "VERI YOLU VE STROBE TEK BANKADA. Zamanlama acisindan onemli olan bu:\\n"
       "aynı banka = ayni IO gerilimi, ayni surucu gecikmesi, ayni sicaklik\\n"
       "davranisi. Adresin bir kismini bankaya sigmadigi icin banka 0'a\\n"
       "tasidik — adres hatlarinin skew'i komut cevriminde tolere ediliyor,\\n"
       "veri yolununki edilmiyor.", 300, 24, 1.35)

s.text("BANKA 0'a TASAN 7 SINYAL", 300, 200, 2.0)
s.text("SD_A9, SD_A10, SD_A11, SD_A12, SD_BA0, SD_BA1, SD_UDQM\\n\\n"
       "ECP5 sembolunun banka 0 birimi BU SAYFADA DEGIL, 08_control'de.\\n"
       "KiCad'de cok birimli bir sembolun her birimi projede BIR KEZ\\n"
       "yerlestirilebiliyor; birimi buraya da koyunca kalan 17 pini\\n"
       "'baglanmamis' diye isaretledi. Sinyaller etiketle gidiyor,\\n"
       "cizim 08_control'de kapaniyor.\\n\\n"
       "Neden banka 0'a tasti: banka 7'nin 32 pini DQ + 9 adres + komut\\n"
       "ile doldu. Adres skew'i komut cevriminde tolere ediliyor, veri\\n"
       "yolununki edilmiyor — o yuzden tasan taraf ADRES oldu.",
       300, 212, 1.35)

s.write(os.path.join(HERE, "05_sdram.kicad_sch"))
print("05_sdram.kicad_sch yazildi")
