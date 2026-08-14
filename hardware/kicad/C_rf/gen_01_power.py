#!/usr/bin/env python3
"""01_power: C karti guc. Kaynak: ../NETLIST_C.md §6."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

BUCK = "Regulator_Switching:TPS62130"
FBUCK = "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm"
R, C, L = "Device:R", "Device:C", "Device:L"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
FL = "Inductor_SMD:L_Taiyo-Yuden_NR-30xx"

s = Sheet("01_power", "Guc", UU["01_power"],
          "VIN_PROT -> +5V buck (role bobinleri), +3V3 A kartindan")

s.text("C KARTI GUCU", 16, 14, 2.0)
s.text("Iki ray geliyor: VIN_PROT (9-18 V) ve +3V3, ikisi de A kartindan\\n"
       "kart arasi bagliktan. Burada uretilen tek sey role bobinlerinin\\n"
       "+5V'u.", 16, 20, 1.35)

# ---------------------------------------------------------------- +5V buck
s.text("+5V — role bobinleri", 16, 45, 1.6)
x, y = 60, 80
s.sym(BUCK, "U80", "TPS62130", x, y, fp=FBUCK)
s.pin_label(BUCK, "10", x, y, 0, "VIN_PROT", "input", d=15.24)
s.pin_label(BUCK, "13", x, y, 0, "VIN_PROT", "input", d=20.32)   # EN
s.pin_power(BUCK, "6", x, y, 0, "GND", d=8.89)
s.pin_power(BUCK, "7", x, y, 0, "GND", d=8.89)     # FSW sabit
s.pin_power(BUCK, "8", x, y, 0, "GND", d=13.97)    # DEF ayarlanabilir
s.nc(*s.P(BUCK, "9", x, y))                        # SS/TR dahili
s.nc(*s.P(BUCK, "4", x, y))                        # PG
s.pin_label(BUCK, "14", x, y, 0, "+5V", "input", d=25.4)         # VOS
s.pin_label(BUCK, "5", x, y, 0, "FB_U80", "input", d=30.48)

sw = s.P(BUCK, "1", x, y)
lx, ly = sw[0] + 15, sw[1]
s.sym(L, "L80", "2.2uH", lx, ly, rot=90, fp=FL)
s.link(sw, s.P(L, "1", lx, ly, 90))
out = s.P(L, "2", lx, ly, 90)
s.wire(out[0], out[1], out[0] + 12, out[1])
s.glabel("+5V", out[0] + 12, out[1], "output")
# +5V bobinden geciyor, bobin pasif: ERC bu rayda guc kaynagi goremiyor.
s.glabel("+5V", 40, 140, "input")
s.wire(40, 140, 40, 133.65)
s.pwr_flag(40, 133.65)

for i, v in enumerate(("22uF", "22uF", "100nF")):
    s.sym(C, f"C8{i}", v, 120 + i * 17.78, 105, rot=90, fp=FC)
    s.pin_label(C, "1", 120 + i * 17.78, 105, 90, "+5V", "input")
    s.pin_power(C, "2", 120 + i * 17.78, 105, 90, "GND")

# geri besleme boleni: 5 V icin oran 0.8 x (1 + R/R) = 5 -> R1/R2 = 5.25
fx, fy = 200, 80
s.sym(R, "R80", "105k", fx, fy, rot=90, fp=FR)
s.pin_label(R, "1", fx, fy, 90, "+5V", "input")
s.pin_label(R, "2", fx, fy, 90, "FB_U80", "passive")
s.sym(R, "R81", "20k", fx, fy + 20, rot=90, fp=FR)
s.pin_label(R, "1", fx, fy + 20, 90, "FB_U80", "passive")
s.pin_power(R, "2", fx, fy + 20, 90, "GND")

s.text("Vout = 0.8 x (1 + R80/R81).  5 V icin oran 5.25 -> 105k / 20k.\\n\\n"
       "NEDEN BUCK, LDO DEGIL: girisin tavani 18 V. LDO ile 18->5\\n"
       "dusurmek 13 V x akim kadar isi demek. Kilitlenen role akimi\\n"
       "darbeli ama darbe aninda 32 bobinden biri 21 mA cekiyor,\\n"
       "ve firmware istese ard arda darbeleyebilir.", 16, 135, 1.35)

# ---------------------------------------------------------------- gelen raylar
s.text("A KARTINDAN GELEN RAYLAR", 16, 180, 1.6)
for i, (net, aciklama) in enumerate([
        ("VIN_PROT", "9-18 V, A kartinda ters polarite korumali"),
        ("+3V3", "PE4312 VDD, 74HC595 ve DRV8833 lojik")]):
    yy = 200 + i * 20
    s.glabel(net, 40, yy, "input")
    s.wire(40, yy, 40, yy - 6.35)
    s.pwr_flag(40, yy - 6.35)
    s.text(aciklama, 70, yy - 2, 1.3)

# Toprak da kart arasi bagliktan geliyor; bu kartta toprak ureten bir
# pin yok. GND_HDR uzerindeki 0R pasif, ERC surucu goremiyor.
s.power("GND", 200, 205)
s.wire(200, 205, 200, 198.65)
s.pwr_flag(200, 198.65)

s.text("Bayraklar gercek baglanti degil: raylar konnektorden geliyor,\\n"
       "bu kartta bir guc kaynagi pini yok, ERC onu boyle ogreniyor.",
       16, 245, 1.3)

# ---------------------------------------------------------------- butce
s.text("GUC BUTCESI", 16, 275, 1.6)
s.text("SUREKLI:\\n"
       "  PE4312 x4      4 x 0.6 mA @3V3  =  2.4 mA   ~8 mW\\n"
       "  74HC595 x8     ihmal edilebilir\\n"
       "  DRV8833 x16    uyku disi ~2 mA  = 32 mA     ~106 mW\\n"
       "  TOPLAM                                       ~115 mW\\n\\n"
       "DARBELI (role anahtarlama, ~20 ms):\\n"
       "  bir bobin  5 V / 21 mA = 105 mW\\n"
       "  firmware tek tek darbeliyor, es zamanli degil\\n\\n"
       "KILITLENEN ROLENIN KAZANCI: normal role olsaydi dort kanalda\\n"
       "bir bant secili tutmak icin dort bobin SUREKLI cekili kalirdi:\\n"
       "4 x 12 V x 30 mA = 1.44 W. A kartinin toplam butcesi 2.8 W idi.\\n"
       "Sadece filtre secimi butcenin yarisini yiyordu.", 16, 285, 1.35)

s.write(os.path.join(HERE, "01_power.kicad_sch"))
print("01_power.kicad_sch yazildi")
