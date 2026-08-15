#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""02_protect: koruma + T/R rolesi, dort kanal. Kaynak: ../NETLIST_C.md §3."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

K = "dogrudan-sdr:G6K-2F-Y"        # T/R KILITLENMEYEN, bkz sembol notu
Q = "Transistor_FET:Q_NMOS_GSD"
FQ = "Package_TO_SOT_SMD:SOT-23"
DFW = "Device:D"
FDFW = "Diode_SMD:D_SOD-323"
FK = "Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y"
GDT = "Device:GDT_2Pin"
# GDT AYAK IZI YEREL — PED NUMARALARI YUZUNDEN.
# Device:GDT_2Pin sembolunun pinleri 1 ve 3 (uc kutuplu GDT'den
# turetilmis, ortadaki elektrot yok). Varistor:RV_Disc'in pedleri
# ise 1 ve 2. Numaralar tutmayinca "GND" pin 3'e yaziliyor, kartta
# karsiligi olmuyor ve ped 2 AGSIZ kaliyor.
#
# Dort kanalin dordunde de oyleydi: anten girisindeki gaz desarj
# tupunun bir ucu havadaydi, yani yildirim/statik korumasi hic
# yoktu. Semada bagli gorunuyor, ERC de temiz — bu hatanin
# gorunecegi tek yer kartin kendisi.
FGDT = "dogrudan-sdr:GDT_Disc_D12mm_W3.9mm_P7.5mm"
TVS = "Device:D_TVS"
FSMB = "Diode_SMD:D_SMB"
D = "Device:D"
FSOD = "Diode_SMD:D_SOD-323"
R, C = "Device:R", "Device:C"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
CONN = "Connector:Conn_Coaxial"
FSMA = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"

s = Sheet("02_protect", "Koruma + T/R", UU["02_protect"],
          "gaz desarj + TVS + limitleyici + T/R rolesi, x4 kanal", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{99 + nr[0]}"


s.text("KORUMA VE T/R — kanal basina ozdes zincir", 16, 14, 2.0)
s.text("Dort zincir BIREBIR AYNI. Faz uyumu antende basliyor: yollarin\\n"
       "genlik ve faz cevabi ayni degilse gurultu iptali, yon bulma ve\\n"
       "isin sekillendirme calismaz. Bu yuzden 'birine su, otekine bu'\\n"
       "yok — ne yapiliyorsa dort kere yapiliyor.", 16, 20, 1.35)


def kanal(ch, x, y):
    ant = f"ANT{ch}"
    s.sym(CONN, f"J{ch}", f"SMA anten {ch}", x, y, fp=FSMA)
    s.pin_label(CONN, "1", x, y, 0, ant, "passive")
    s.pin_power(CONN, "2", x, y, 0, "GND")

    # --- katman 1: gaz desarj tupu, kilovoltlari topraga
    s.sym(GDT, cnt("E"), "GDT 90V", x + 22, y + 14, rot=90, fp=FGDT)
    s.pin_label(GDT, "1", x + 22, y + 14, 90, ant, "passive")
    s.pin_power(GDT, "3", x + 22, y + 14, 90, "GND")

    # --- katman 2: TVS, nanosaniye gecicileri
    s.sym(TVS, cnt("D"), "SMBJ20A", x + 42, y + 14, rot=90, fp=FSMB)
    s.pin_label(TVS, "1", x + 42, y + 14, 90, ant, "passive")
    s.pin_power(TVS, "2", x + 42, y + 14, 90, "GND")

    # --- T/R rolesi: anten ya RX zincirine ya TX'e
    kref = f"KT{ch}"
    s.sym(K, kref, "G6K-2F-Y", x + 75, y, fp=FK)
    s.pin_label(K, "3", x + 75, y, 0, ant, "passive", d=7.62)
    s.pin_label(K, "2", x + 75, y, 0, f"RX{ch}_ANT", "passive", d=7.62)
    s.pin_label(K, "4", x + 75, y, 0, f"TX{ch}", "passive", d=12.7)
    # ikinci kutup: TX sirasinda RX girisini TOPRAGA baglar
    s.pin_label(K, "6", x + 75, y, 0, f"RX{ch}_GRD", "passive", d=17.78)
    s.pin_label(K, "7", x + 75, y, 0, f"RX{ch}_GRD", "passive", d=22.86)
    s.pin_power(K, "5", x + 75, y, 0, "GND", d=27.94)
    # bobin: +5V ile MOSFET arasinda, ustune sonumleme diyodu
    s.pin_label(K, "1", x + 75, y, 0, "+5V", "input", d=17.78)
    s.pin_label(K, "8", x + 75, y, 0, f"KT{ch}_LO", "passive", d=22.86)
    s.sym(DFW, cnt("D"), "1N4148WS", x + 108, y - 16, rot=90, fp=FDFW)
    s.pin_label(DFW, "1", x + 108, y - 16, 90, f"KT{ch}_LO", "passive")
    s.pin_label(DFW, "2", x + 108, y - 16, 90, "+5V", "input")
    s.sym(Q, f"QT{ch}", "2N7002", x + 108, y + 34, fp=FQ)
    s.pin_label(Q, "2", x + 108, y + 34, 0, f"KT{ch}_LO", "passive", d=7.62)
    s.pin_power(Q, "3", x + 108, y + 34, 0, "GND", d=7.62)
    s.sym(R, cnt("R"), "1k", x + 85, y + 34, rot=90, fp=FR)
    s.pin_label(R, "1", x + 85, y + 34, 90, f"TR{ch}", "input")
    s.pin_label(R, "2", x + 85, y + 34, 90, f"KT{ch}_G", "passive")
    s.link(s.P(R, "2", x + 85, y + 34, 90), s.P(Q, "1", x + 108, y + 34))
    s.sym(R, cnt("R"), "100k", x + 96, y + 50, rot=90, fp=FR)
    s.pin_label(R, "1", x + 96, y + 50, 90, f"KT{ch}_G", "passive")
    s.pin_power(R, "2", x + 96, y + 50, 90, "GND")

    # --- katman 3: sirt sirta diyot limitleyici, yakindaki verici
    # Iki ayri 1N4148WS, ters paralel. Tek govdeli seri cift (BAV99)
    # de olurdu ama ayri diyot hem daha ucuz hem semada ne yaptigi
    # bakinca anlasiliyor.
    for j, (a, b) in enumerate([("1", "2"), ("2", "1")]):
        dx = x + 128 + j * 14
        s.sym(D, cnt("D"), "1N4148WS", dx, y + 14, rot=90, fp=FSOD)
        s.pin_label(D, a, dx, y + 14, 90, f"RX{ch}_ANT", "passive")
        s.pin_power(D, b, dx, y + 14, 90, "GND")

    # --- filtre bankasina
    # rot=90 (YATAY). Device:R rot=0'da dikey ciziliyor; 14 mm arayla
    # duran iki direncin saplamalari ust uste bindi ve RX_B1_IN ile
    # RX_GRD tek ag oldu — alis yolu dogrudan topraga baglanmis olurdu.
    s.sym(R, cnt("R"), "0R", x + 160, y, rot=90, fp=FR)
    s.pin_label(R, "1", x + 160, y, 90, f"RX{ch}_ANT", "passive")
    s.pin_label(R, "2", x + 160, y, 90, f"RX{ch}_B1_IN", "passive")
    s.sym(R, cnt("R"), "0R", x + 160, y + 14, rot=90, fp=FR)
    s.pin_label(R, "1", x + 160, y + 14, 90, f"RX{ch}_GRD", "passive")
    s.pin_label(R, "2", x + 160, y + 14, 90, f"RX{ch}_B1_OUT", "passive")


for i in range(4):
    kanal(i + 1, 30, 55 + i * 62)

s.text("UC KATMAN, UC FARKLI ZAMAN OLCEGI\\n"
       "  1 gaz desarj tupu  yildirim/statik, kilovolt, mikrosaniye\\n"
       "  2 TVS              hizli gecici, nanosaniye, surekli guc TASIMAZ\\n"
       "  3 diyot limitleyici yakindaki verici, SUREKLI calisir, kilovolt gorurse olur\\n\\n"
       "Biri digerinin yerine gecmiyor. Okul istasyonunda kendi vericimiz\\n"
       "ayni catida; ucu de gerekli.\\n\\n"
       "T/R rolesinin IKINCI kutbu bosta durmuyor: verirken RX girisini\\n"
       "topraga baglıyor. 100 W verirken komsu kanalin on ucunu korumanin\\n"
       "en ucuz yolu — ek parca yok, zaten 2 Form C.", 16, 305, 1.35)

s.text("T/R ROLESI KILITLENMEYEN — GUVENLIK\\n"
       "Filtre bankasindaki roleler kilitlenen (guc butcesi icin). T/R'da\\n"
       "tam tersi gerekiyor: kilitlenen role gucsuz kaldigi konumu KORUR,\\n"
       "yani guc kesilse ya da firmware cokse anten PA'ya bagli kalir ve\\n"
       "alici girisine 100 W dusebilir.\\n\\n"
       "G6K-2F-Y (kilitlenmeyen) birakildiginda kendiliginden RX konumuna\\n"
       "doner. Guvenlik varsayilan durumdan gelmeli, yazilimdan degil.\\n"
       "Bedeli: verirken 5 V / 28 mA = 140 mW. Ayni anda tek port verdigi\\n"
       "icin tek bobin. Kabul.\\n\\n"
       "100k geciti asagi cekiyor: FPGA henuz kalkmamisken bile MOSFET\\n"
       "kapali, role RX'te.", 300, 200, 1.35)

s.text("** BU KART MILIVAT TARAFI **\\n"
       "G6KU sinyal rolesi: 0.3 A / 30 V. 100 W'ta 50 ohm'da 70 V rms ve\\n"
       "1.4 A var — bu role onu anahtarlayamaz, kontaklari yapisir.\\n\\n"
       "PA cikisindaki anten anahtari AYRI ve GUCLU, D2 kartinda.\\n"
       "Buradaki T/R sadece milivat seviyesindeki DAC cikisini ve alis\\n"
       "yolunu anahtarliyor. PA'li porta gelince o portun T/R'i PA'nin\\n"
       "icinde oluyor. PA_TASARIM.md §6.", 300, 305, 1.35)

s.write(os.path.join(HERE, "02_protect.kicad_sch"))
print("02_protect.kicad_sch yazildi")
