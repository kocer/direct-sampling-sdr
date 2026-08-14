#!/usr/bin/env python3
"""06_iface: kart arasi. Kaynak: ../NETLIST_C.md §7."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

HDR = "Connector_Generic:Conn_02x10_Odd_Even"
FHDR = "Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Vertical"
HDR6 = "Connector_Generic:Conn_01x06"
FHDR6 = "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"
CONN = "Connector:Conn_Coaxial"
FSMA = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"
R = "Device:R"
FR = "Resistor_SMD:R_0603_1608Metric"

s = Sheet("06_iface", "Kart arasi", UU["06_iface"],
          "A kartina baslik + koaks kuyruk", paper="A2")

s.text("KART ARASI — A <-> C", 16, 14, 2.0)
s.text("Dijital hatlar baslikta, RF koaks kuyrukla. Baslikla RF gecirmek\\n"
       "kart arasi empedansi bozar ve komsu hatlara kuple olur.", 16, 20, 1.35)

# ------------------------------------------------------------ ana baslik
s.text("J80 — ana baslik (A kartindaki J63'un karsisi)", 16, 45, 1.6)
s.sym(HDR, "J80", "A kartina", 60, 90, fp=FHDR)
pairs = [("1", "+3V3"), ("2", "GND_HDR"), ("3", "RLY_SER"), ("4", "GND_HDR"),
         ("5", "RLY_SRCLK"), ("6", "GND_HDR"), ("7", "RLY_RCLK"), ("8", "GND_HDR"),
         ("9", "TR1"), ("10", "GND_HDR"), ("11", "TR2"), ("12", "GND_HDR"),
         ("13", "TR3"), ("14", "GND_HDR"), ("15", "TR4"), ("16", "GND_HDR"),
         ("17", "ATT_DATA"), ("18", "ATT_CLK"), ("19", "ATT1_LE"),
         ("20", "VIN_PROT")]
for p, net in pairs:
    s.pin_label(HDR, p, 60, 90, 0, net, "passive", d=7.62)

s.sym(R, "R90", "0R", 130, 145, rot=90, fp=FR)
s.pin_label(R, "1", 130, 145, 90, "GND_HDR", "passive")
s.pin_power(R, "2", 130, 145, 90, "GND")

# ------------------------------------------------------------ ikinci baslik
s.text("J81 — ikinci baslik (A kartindaki J65)", 16, 175, 1.6)
s.sym(HDR6, "J81", "A kartina #2", 60, 200, fp=FHDR6)
for p, net in [("1", "ATT2_LE"), ("2", "ATT3_LE"), ("3", "ATT4_LE"),
               ("4", "VIN_PROT"), ("5", "+3V3")]:
    s.pin_label(HDR6, p, 60, 200, 0, net, "passive", d=10.16)
s.pin_power(HDR6, "6", 60, 200, 0, "GND", d=15.24)

s.text("A KARTI GUNCELLENDI — arayuz artik eslesiyor.\\n"
       "Onceden A'da ATT1_DATA/CLK/LE + ATT2_DATA/CLK/LE vardi (iki\\n"
       "zayiflatici varsayimi). Dort zayiflatici olunca veri ve saat\\n"
       "ortaklasti, LE'ler ayrildi. Hat sayisi ayni (6), anlami degisti.\\n"
       "A kartinda 08_control bu sayfaya gore yeniden yazildi.",
       16, 225, 1.35)

# ------------------------------------------------------------ D kartina zincir
s.text("YAZMAC ZINCIRI -> D KARTI", 16, 250, 1.6)
s.sym(HDR6, "J90", "D kartina", 60, 275, fp=FHDR6)
for p_, net in [("1", "RLY_SER_OUT"), ("2", "RLY_SRCLK"), ("3", "RLY_RCLK"),
                ("4", "+3V3")]:
    s.pin_label(HDR6, p_, 60, 275, 0, net, "passive", d=10.16)
s.pin_power(HDR6, "5", 60, 275, 0, "GND", d=10.16)
s.pin_power(HDR6, "6", 60, 275, 0, "GND", d=15.24)

s.text("C kartindaki yedi 74HC595'in sonuncusunun QH' cikisi D kartinin\\n"
       "LPF yazmacina gidiyor: tek zincir, sekiz yazmac, 64 bit.\\n"
       "Saat ve mandal hatlari ortak. D kartina ayri seri hat cekmeye\\n"
       "gerek yok; ikisi de yavas role kontrolu.", 16, 300, 1.3)

# ------------------------------------------------------------ RF kuyruklar
s.text("RF — koaks kuyruk, baslik DEGIL", 300, 45, 1.6)
for i in range(4):
    y = 70 + i * 26
    s.sym(CONN, f"J8{2 + i}", f"RX{i + 1} -> A", 340, y, fp=FSMA)
    s.pin_label(CONN, "1", 340, y, 0, f"RX{i + 1}_OUT", "passive")
    s.pin_power(CONN, "2", 340, y, 0, "GND")
for i in range(4):
    y = 180 + i * 26
    s.sym(CONN, f"J8{6 + i}", f"TX{i + 1} <- A", 340, y, fp=FSMA)
    s.pin_label(CONN, "1", 340, y, 0, f"TX{i + 1}", "passive")
    s.pin_power(CONN, "2", 340, y, 0, "GND")

s.text("Dort alis cikisi (zayiflaticidan sonra) A kartinin SMA girislerine,\\n"
       "dort veris girisi A kartinin DAC cikislarindan.\\n\\n"
       "SMA kart-arasi pahali ama sinyal butunlugu icin dogru secim:\\n"
       "2.54 mm baslikta empedans kontrolu yok, dort kanalin faz uyumu\\n"
       "orada bozulur. Kisa RG316 kuyruklar, ES BOY kesilmis.\\n\\n"
       "** ES BOY SART. ** Dort koaksin uzunluk farki dogrudan kanallar\\n"
       "arasi faz farki demek. 1 cm fark 30 MHz'te ~0.5 derece.",
       300, 290, 1.35)

# ------------------------------------------------------------ D kartina
s.text("D KARTINA (PA) — ileride", 16, 300, 1.6)
s.text("PA gelince TX1 yolu C kartindan gecmeyecek: DAC -> D karti surucu\\n"
       "-> final -> D kartinin kendi anten anahtari -> anten.\\n"
       "C kartinin T/R'i o portta devre disi kalir (milivat rolesi 100 W\\n"
       "anahtarlayamaz, NETLIST_C.md §3 notu).\\n\\n"
       "DPD geri besleme yolu buradan gececek: D kartindaki kuplor ->\\n"
       "zayiflatici -> C kartinda bir role -> RX4 girisi. Bir koaks,\\n"
       "bir role. PA_TASARIM.md §6b.", 16, 310, 1.35)

s.write(os.path.join(HERE, "06_iface.kicad_sch"))
print("06_iface.kicad_sch yazildi")
