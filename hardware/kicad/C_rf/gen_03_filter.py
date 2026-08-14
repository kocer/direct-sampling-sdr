#!/usr/bin/env python3
"""03_filter: 7 pozisyonlu bant filtresi bankasi x 4 kanal.
Kaynak: ../NETLIST_C.md §2, degerler filtre_hesap.py'den."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

K = "dogrudan-sdr:G6KU-2F-Y"
FK = "Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y"
L, C = "Device:L", "Device:C"
FL = "Inductor_SMD:L_0805_2012Metric"
FLT = "dogrudan-sdr:L_Toroid_T50_Vertical"
FC = "Capacitor_SMD:C_0603_1608Metric"

s = Sheet("03_filter", "Filtre bankasi", UU["03_filter"],
          "7 pozisyon x 4 kanal, G6KU kilitlenen role", paper="A1")

# filtre_hesap.py ciktisi. (ad, L nH, Crez pF, Ckuplaj pF, Cuc pF, bobin tipi)
BANTLAR = [
    ("160m",   16000, 430, 62,  270, "toroid"),
    ("80_60m",  7500, 180, 82,  390, "smd"),
    ("40_30m",  3900,  91, 33,  160, "smd"),
    ("20_17m",  2000,  51, 13,   56, "smd"),
    ("15_10m",  1300,  30, 10,   47, "smd"),
    ("6m",       620,  15, 1.3, 5.6, "toroid"),
]

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{999 + nr[0]}"


def deger(x, birim):
    return f"{x:g}{birim}"


def bolum(ch, bant, x, y, idx):
    """Bir kanalin bir bant bolumu: role + uc rezonatorlu bant geciren.

    Role 2 Form C: BIR role hem girisi hem cikisi anahtarliyor.
    COM1 girise, COM2 cikisa; N1B/N2B filtreye, N1A/N2A bir sonraki
    bolume (zincir) gidiyor.
    """
    ad, Ln, Cr, Ck, Cu, tip = bant
    net_in = f"RX{ch}_B{idx}_IN"
    net_out = f"RX{ch}_B{idx}_OUT"
    nxt_in = f"RX{ch}_B{idx + 1}_IN"
    nxt_out = f"RX{ch}_B{idx + 1}_OUT"

    kref = f"K{ch}{idx}"
    s.sym(K, kref, "G6KU-2F-Y", x, y, fp=FK)
    s.pin_label(K, "3", x, y, 0, net_in, "passive", d=7.62)
    s.pin_label(K, "6", x, y, 0, net_out, "passive", d=12.7)
    s.pin_label(K, "2", x, y, 0, nxt_in, "passive", d=7.62)     # zincir
    s.pin_label(K, "7", x, y, 0, nxt_out, "passive", d=12.7)
    s.pin_label(K, "4", x, y, 0, f"F{ch}{idx}_A", "passive", d=17.78)
    s.pin_label(K, "5", x, y, 0, f"F{ch}{idx}_B", "passive", d=22.86)
    s.pin_label(K, "1", x, y, 0, f"K{ch}{idx}_S", "input", d=17.78)
    s.pin_label(K, "8", x, y, 0, f"K{ch}{idx}_R", "input", d=22.86)

    # ---- uc rezonatorlu tepeden kuplajli bant geciren
    fx = x + 55
    fl = FLT if tip == "toroid" else FL
    # uc kondansatorleri
    s.sym(C, cnt("C"), deger(Cu, "pF"), fx, y, rot=90, fp=FC)
    s.pin_label(C, "1", fx, y, 90, f"F{ch}{idx}_A", "passive")
    s.pin_label(C, "2", fx, y, 90, f"N{ch}{idx}_1", "passive")
    s.sym(C, cnt("C"), deger(Cu, "pF"), fx + 100, y, rot=90, fp=FC)
    s.pin_label(C, "1", fx + 100, y, 90, f"N{ch}{idx}_3", "passive")
    s.pin_label(C, "2", fx + 100, y, 90, f"F{ch}{idx}_B", "passive")
    # kuplaj kondansatorleri
    for j in (1, 2):
        s.sym(C, cnt("C"), deger(Ck, "pF"), fx + 25 + (j - 1) * 50, y, rot=90, fp=FC)
        s.pin_label(C, "1", fx + 25 + (j - 1) * 50, y, 90, f"N{ch}{idx}_{j}", "passive")
        s.pin_label(C, "2", fx + 25 + (j - 1) * 50, y, 90, f"N{ch}{idx}_{j + 1}", "passive")
    # uc rezonator: L ve C paralel, topraga
    for j in (1, 2, 3):
        rx = fx + 12 + (j - 1) * 50
        s.sym(L, cnt("L"), deger(Ln / 1000 if Ln >= 1000 else Ln,
                                 "uH" if Ln >= 1000 else "nH"),
              rx, y + 20, rot=90, fp=fl)
        s.pin_label(L, "1", rx, y + 20, 90, f"N{ch}{idx}_{j}", "passive")
        s.pin_power(L, "2", rx, y + 20, 90, "GND")
        s.sym(C, cnt("C"), deger(Cr, "pF"), rx + 20, y + 20, rot=90, fp=FC)
        s.pin_label(C, "1", rx + 20, y + 20, 90, f"N{ch}{idx}_{j}", "passive")
        s.pin_power(C, "2", rx + 20, y + 20, 90, "GND")


s.text("BANT FILTRESI BANKASI — 7 pozisyon x 4 kanal", 16, 14, 2.2)
s.text("Roleler ZINCIRLI: her role kendi bandini secmezse sinyali bir\\n"
       "sonraki bolume geciriyor (N1A/N2A). Hicbiri secilmezse sinyal\\n"
       "zincirin sonundaki BYPASS'a dusuyor. Tek anda tek role cekili.\\n\\n"
       "Bir role 2 Form C: HEM girisi HEM cikisi anahtarliyor. Ayri\\n"
       "giris/cikis rolesi kullansaydik adet iki katina cikardi.",
       16, 22, 1.4)

for ch in range(1, 5):
    ybase = 60 + (ch - 1) * 130
    s.text(f"KANAL {ch}", 16, ybase - 8, 1.8)
    for idx, bant in enumerate(BANTLAR, start=1):
        bolum(ch, bant, 55 + ((idx - 1) % 3) * 190,
              ybase + ((idx - 1) // 3) * 55, idx)

# ---------------------------------------------------------------- bypass
s.text("BYPASS — 7. pozisyon", 640, 14, 1.8)
for ch in range(1, 5):
    y = 40 + (ch - 1) * 30
    s.sym(K, f"K{ch}7", "G6KU-2F-Y", 680, y, fp=FK)
    s.pin_label(K, "3", 680, y, 0, f"RX{ch}_B7_IN", "passive", d=7.62)
    s.pin_label(K, "6", 680, y, 0, f"RX{ch}_B7_OUT", "passive", d=12.7)
    s.pin_label(K, "2", 680, y, 0, f"RX{ch}_FILT", "passive", d=7.62)
    s.pin_label(K, "7", 680, y, 0, f"RX{ch}_FILT", "passive", d=12.7)
    s.pin_label(K, "4", 680, y, 0, f"RX{ch}_FILT", "passive", d=17.78)
    s.pin_label(K, "5", 680, y, 0, f"RX{ch}_FILT", "passive", d=22.86)
    s.pin_label(K, "1", 680, y, 0, f"K{ch}7_S", "input", d=17.78)
    s.pin_label(K, "8", 680, y, 0, f"K{ch}7_R", "input", d=22.86)

s.text("Bypass rolesinin iki konumu da RX_FILT'e gidiyor: bu pozisyon\\n"
       "filtre YOK demek, dogrudan gecis. VHF/UHF alt-ornekleme, uydu,\\n"
       "radiosonde ve genel tarama buradan.\\n\\n"
       "Zincirin sonu oldugu icin hicbir bant secilmediginde de sinyal\\n"
       "buraya dusuyor — yani varsayilan durum GENIS BANT. Acilista\\n"
       "roleler bilinmeyen konumda olabilir; firmware ilk is olarak\\n"
       "hepsini RESET'liyor.", 640, 170, 1.35)

# ---------------------------------------------------------------- notlar
s.text("DEGERLER — filtre_hesap.py", 640, 230, 1.8)
s.text("Uc rezonatorlu, tepeden kapasitif kuplajli Chebyshev 0.1 dB.\\n"
       "Rezonator reaktansi 200 ohm hedeflendi (once kapasiteyi sabit\\n"
       "tutmustum, 160m'de 68 uH cikmisti — o degerde RF bobini yok).\\n\\n"
       "bant      f0     BW     L      Crez  Ckup  Cuc   IL\\n"
       "160m     1.89   0.30   16uH   430p   62p  270p  3.5/0.5 dB\\n"
       "80/60m   4.32   2.10   7.5uH  180p   82p  390p  0.96\\n"
       "40/30m   8.43   3.40   3.9uH   91p   33p  160p  0.86\\n"
       "20/17m  15.95   4.40   2.0uH   51p   13p   56p  1.01\\n"
       "15/10m  24.96   8.90   1.3uH   30p   10p   47p  0.71\\n"
       "6m      51.94   5.00   620nH   15p  1.3p  5.6p  2.4/1.2 dB",
       640, 240, 1.3)

s.text("** 160m VE 6m TOROID **\\n"
       "O iki bantta SMD bobinin Q'su cokuyor (160m'de 16 uH'lik parca\\n"
       "ferrit cekirdekli guc bobini, Q=25 -> 3.5 dB ekleme kaybi).\\n"
       "Alicida on yukseltec YOK, kayip dogrudan duyarliliktan dusuyor.\\n"
       "Toz demir toroid (T50-2/T50-6) Q=180 veriyor, kayip 0.5 dB'ye\\n"
       "iniyor. Diger dort bantta SMD 1 dB altinda, sorun yok.\\n\\n"
       "TOROID BEDELI: elde sarilir, kanaldan kanala DEGISIR. Faz uyumu\\n"
       "dort kanalin ozdes olmasini sart kosuyor. Cozum: 30 tane sarip\\n"
       "LCR ile olcup en yakin dortlulere ayirmak. Satin alinamayan tek\\n"
       "sey bu — ve tam bir kulup isi.\\n\\n"
       "Ayak izi toroid icin THT, SMD icin 0805. Ikisi de cizildi;\\n"
       "hangi bantta hangisi kullanilacagi yukaridaki tabloda.",
       640, 300, 1.35)

s.text("ROLE SURUCUSU — 05_driver\\n"
       "G6KU TEK SARIMLI kilitlenen: bobine verilen gerilimin YONU\\n"
       "konumu belirliyor. Acik drenaj surucu yetmiyor, H koprusu sart.\\n"
       "Her role icin K__S ve K__R hatti, DRV8833'un iki girisi.\\n\\n"
       "28 role (7 pozisyon x 4 kanal) + 4 T/R = 32 role\\n"
       "32 role x 2 hat = 64 hat -> 8 x 74HC595\\n"
       "32 bobin -> 16 x DRV8833 (her biri cift H koprusu)",
       640, 380, 1.35)

s.write(os.path.join(HERE, "03_filter.kicad_sch"))
print("03_filter.kicad_sch yazildi")
