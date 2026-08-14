#!/usr/bin/env python3
"""04_atten: PE4312 x4, ortak seri yol, ayri LE. Kaynak: ../NETLIST_C.md §4."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

A = "dogrudan-sdr:PE4312"
FA = "Package_DFN_QFN:QFN-20-1EP_4x4mm_P0.5mm_EP2.6x2.6mm_ThermalVias"
R, C = "Device:R", "Device:C"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0402_1005Metric"

s = Sheet("04_atten", "Zayiflaticilar", UU["04_atten"],
          "PE4312 x4, 0-31.5 dB, ortak seri yol", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{399 + nr[0]}"


s.text("ZAYIFLATICILAR — PE4312 x4, 0-31.5 dB", 16, 14, 2.0)
s.text("DORT KANAL, DORT ZAYIFLATICI. Sartnamede iki taneydi; faz uyumu\\n"
       "zincirlerin ozdes olmasini sart kosuyor, iki kanal zayiflatilip\\n"
       "ikisi zayiflatilmadan birakilamaz.\\n\\n"
       "A kartinda ayrilan hat sayisi degismedi: Data ve Clock DORT CIPTE\\n"
       "DE ORTAK, LE'ler ayri. 2 + 4 = 6 hat — ilk planda iki cipe ucer\\n"
       "hat olarak ayrilan sayinin aynisi. A karti degismiyor.", 16, 20, 1.35)


def atten(ref, x, y, n):
    s.sym(A, ref, "PE4312C-Z", x, y, fp=FA)
    # seri arayuz: Data ve Clock ORTAK, LE cipe ozel
    s.pin_label(A, "3", x, y, 0, "ATT_DATA", "input", d=7.62)
    s.pin_label(A, "4", x, y, 0, "ATT_CLK", "input", d=12.7)
    s.pin_label(A, "5", x, y, 0, f"ATT{n}_LE", "input", d=17.78)
    # P/S = HIGH -> SERI mod (veri sayfasi s.5)
    s.pin_label(A, "13", x, y, 0, "+3V3", "input", d=22.86)
    # PUP1/PUP2 seri modda etkisiz (Tablo 5 yalniz P/S=0 icin)
    s.pin_power(A, "7", x, y, 0, "GND", d=27.94)
    s.pin_power(A, "8", x, y, 0, "GND", d=33.02)
    # RF yolu
    s.pin_label(A, "2", x, y, 0, f"RX{n}_FILT", "passive", d=27.94)
    s.pin_label(A, "14", x, y, 0, f"RX{n}_OUT", "passive", d=33.02)
    # guc ve toprak
    for p in ("6", "9"):
        s.pin_label(A, p, x, y, 0, "+3V3", "input", d=5.08)
    for p in ("10", "11", "18", "Pad"):
        s.pin_power(A, p, x, y, 0, "GND", d=5.08)
    s.pin_power(A, "12", x, y, 0, "GND", d=10.16)
    # ALTI C BACAGI 10k ILE YUKARI -> acilista 31.5 dB
    for i, p in enumerate(("1", "15", "16", "17", "19", "20")):
        rx, ry = x + 75, y - 30 + i * 12
        s.sym(R, cnt("R"), "10k", rx, ry, rot=90, fp=FR)
        s.pin_label(R, "1", rx, ry, 90, "+3V3", "input")
        s.pin_label(R, "2", rx, ry, 90, f"ATT{n}_C{i}", "passive")
        s.pin_label(A, p, x, y, 0, f"ATT{n}_C{i}", "input", d=7.62)
    # besleme ayristirma
    for i in range(2):
        s.sym(C, cnt("C"), "100nF", x + 110 + i * 17.78, y, rot=90, fp=FC)
        s.pin_label(C, "1", x + 110 + i * 17.78, y, 90, "+3V3", "input")
        s.pin_power(C, "2", x + 110 + i * 17.78, y, 90, "GND")


for i in range(4):
    atten(f"U{40 + i}", 75 + (i % 2) * 250, 90 + (i // 2) * 130, i + 1)

s.text("ACILIS DURUMU — KRITIK\\n"
       "Veri sayfasi s.6: 'When the attenuator powers up in serial mode\\n"
       "(P/S = 1), the six control bits are set to whatever data is present\\n"
       "on the six parallel data inputs (C0.5 to C16).'\\n\\n"
       "Yani SERI modda bile acilis zayiflatmasini o alti bacak belirliyor.\\n"
       "Bos birakilsalardi tanimsiz olurdu. Altisi da 10k ile yukari:\\n"
       "Tablo 4'e gore hepsi 1 = 31.5 dB, EN COK zayiflatma.\\n\\n"
       "Alici acilista en sagir halinde. FPGA flash'tan kalkip seri hatti\\n"
       "yazana kadar (yuz milisaniyeler) on uc korunuyor. Tersi 0 dB\\n"
       "demekti — okulun kendi HF vericisi yanibasindayken her acilista\\n"
       "ADC'yi doyurmak.\\n\\n"
       "24 direnc (4 cip x 6). Ucuz sigorta.", 16, 300, 1.35)

s.text("P/S = +3V3 -> SERI mod.\\n"
       "Paralel modda alti C bacagini surmek gerekirdi: dort cip icin\\n"
       "24 hat. Seri hatta uc hat yetiyor (Data, Clock ortak + LE).\\n\\n"
       "Data ve Clock ortak oldugu icin dort cip ayni veriyi goruyor;\\n"
       "hangisine yazilacagini LE belirliyor. Firmware sirayla LE\\n"
       "darbeliyor. Dort kanal ayni zayiflatmaya kurulacaksa dort LE\\n"
       "birden darbelenip tek yazma ile hepsi ayarlanabilir — faz\\n"
       "uyumu icin zaten istenen bu.", 300, 300, 1.35)

s.write(os.path.join(HERE, "04_atten.kicad_sch"))
print("04_atten.kicad_sch yazildi")
