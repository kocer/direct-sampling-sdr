#!/usr/bin/env python3
"""
dogrudan-sdr / eksik KiCad sembollerini uretir.

Her sembol datasheet pin tablosundan elle girildi. Pin numaralari ve
isimleri DOGRULANDI; kaynak sayfa her sembolun basinda yazili.

Cok birimli yapiyoruz: analog / kanal A / kanal B / kontrol ayri birim.
Boylece semayi sayfalara bolebiliyoruz (ECP5 sembolunun yaptigi gibi).
"""
import os

# pin tipi: input output bidirectional tri_state passive power_in power_out
#           open_collector open_emitter unconnected no_connect free

# Kutu sinirlari pinlerden HESAPLANIR. Elle yazilirsa pin govdesi kutu
# icinde kalabiliyor ve o pine tel baglanamiyor (ilk denemede oldu).
LEN = 2.54
def pin(num, name, typ="passive", side="L", idx=0, unit=1, off=0.0):
    """side: L sol, R sag, T ust, B alt. idx 0'dan baslar.
    off: o kenarin govde hizasi (build() dolduruyor)."""
    return (unit, typ, side, idx, rot_of(side), name, str(num), typ)

def rot_of(side):
    return {"L":0, "R":180, "T":270, "B":90}[side]

def place(pins_u):
    """Bir birimin pinlerini yerlestir, kutuyu hesapla, (kutu, yerlesikler) don.
    Kutu boyutu PIN ISIMLERININ uzunlugundan da hesaplanir; yoksa govde
    icindeki yazilar birbirine giriyor (ikinci denemede oldu)."""
    CH = 1.15   # 1.27 punto karakter genisligi, yaklasik
    by = {}
    for p in pins_u:
        by.setdefault(p[2], []).append(p)
    def cnt(sd): return len(by.get(sd, []))
    def mx(sd):  return max([len(q[5]) for q in by.get(sd, [])] or [0])

    w = max(cnt("T"), cnt("B"), 3) * 2.54 + (mx("L") + mx("R")) * CH + 5.08
    h = max(cnt("L"), cnt("R"), 2) * 2.54 + (mx("T") + mx("B")) * CH + 5.08
    # 2.54'un KATI olmali: h/2 ile pin konumu hesaplaniyor, tek kat
    # olursa pinler YARIM izgaraya dusuyor ve tel pine degmiyor.
    w = round(w / 2.54) * 2.54
    h = round(h / 2.54) * 2.54
    x1, y1, x2, y2 = -w/2, h/2, w/2, -h/2

    out = []
    for side, lst in by.items():
        lst = sorted(lst, key=lambda q: q[3])
        n = len(lst)
        if side in ("L", "R"):
            span = (n - 1) * 2.54
            y0 = span / 2                      # dikeyde ortala
            for i, p in enumerate(lst):
                unit, typ, sd, idx, rot, nm, num, _ = p
                y = round((y0 - i * 2.54) / 1.27) * 1.27
                x = x1 - LEN if side == "L" else x2 + LEN
                out.append((unit, typ, x, y, rot, nm, num, LEN))
        else:
            span = (n - 1) * 2.54
            x0 = -span / 2                     # yatayda ortala
            for i, p in enumerate(lst):
                unit, typ, sd, idx, rot, nm, num, _ = p
                x = round((x0 + i * 2.54) / 1.27) * 1.27
                y = y1 + LEN if side == "T" else y2 - LEN
                out.append((unit, typ, x, y, rot, nm, num, LEN))
    return (x1, y1, x2, y2), out

def build(name, ref, footprint, desc, mpn, pins, unit_boxes=None):
    out = [f'  (symbol "{name}" (pin_names (offset 0.762)) (in_bom yes) (on_board yes)']
    out.append(f'    (property "Reference" "{ref}" (at 0 5.08 0) (effects (font (size 1.27 1.27))))')
    out.append(f'    (property "Value" "{name}" (at 0 2.54 0) (effects (font (size 1.27 1.27))))')
    out.append(f'    (property "Footprint" "{footprint}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    out.append(f'    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    out.append(f'    (property "Description" "{desc}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    out.append(f'    (property "MPN" "{mpn}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    units = sorted(set(p[0] for p in pins))
    for u in units:
        (x1, y1, x2, y2), placed = place([p for p in pins if p[0] == u])
        out.append(f'    (symbol "{name}_{u}_1"')
        out.append(f'      (rectangle (start {x1} {y1}) (end {x2} {y2})')
        out.append(f'        (stroke (width 0.254) (type default)) (fill (type background)))')
        for (pu, typ, x, y, rot, pname, pnum, ln) in placed:
            out.append(f'      (pin {typ} line (at {x} {y} {rot}) (length {ln})')
            out.append(f'        (name "{pname}" (effects (font (size 1.27 1.27))))')
            out.append(f'        (number "{pnum}" (effects (font (size 1.27 1.27))))')
            out.append(f'      )')
        out.append('    )')
    out.append('  )')
    return "\n".join(out)


# ====================================================================
# AD9251  — datasheet Rev.C sayfa 11-12, Table 8
# ====================================================================
def ad9251():
    P = []
    # --- birim 1: ANALOG
    an = [("1","CLK+","input"),("2","CLK-","input"),
          ("51","VIN+A","input"),("52","VIN-A","input"),
          ("61","VIN-B","input"),("62","VIN+B","input")]
    for i,(n,nm,t) in enumerate(an):
        P.append(pin(n,nm,t,"L",i+1,1))
    ref = [("55","VREF","passive"),("56","SENSE","input"),
           ("57","VCM","output"),("58","RBIAS","passive")]
    for i,(n,nm,t) in enumerate(ref):
        P.append(pin(n,nm,t,"R",i+1,1))
    for i,n in enumerate(["49","50","53","54","59","60","63","64"]):
        P.append(pin(n,"AVDD","power_in","T",i,1))
    P.append(pin("0","GND","power_in","B",0,1))     # exposed paddle
    # --- birim 2: KANAL A dijital
    for i in range(14):
        num = ["27","29","30","31","32","33","34","35","36","38","39","40","41","42"][i]
        P.append(pin(num, f"D{i}A", "output", "R", i+1, 2))
    P.append(pin("24","DCOA","output","R",16,2))
    P.append(pin("43","ORA","output","R",17,2))
    # --- birim 3: KANAL B dijital
    for i in range(14):
        num = ["6","7","8","9","11","12","13","14","15","16","17","18","20","21"][i]
        P.append(pin(num, f"D{i}B", "output", "R", i+1, 3))
    P.append(pin("23","DCOB","output","R",16,3))
    P.append(pin("22","ORB","output","R",17,3))
    # --- birim 4: KONTROL + dijital besleme
    ctl = [("3","SYNC","input"),("44","SDIO/DCS","bidirectional"),
           ("45","SCLK/DFS","input"),("46","~{CSB}","input"),
           ("47","~{OEB}","input"),("48","PDWN","input")]
    for i,(n,nm,t) in enumerate(ctl):
        P.append(pin(n,nm,t,"L",i+1,4))
    for i,n in enumerate(["10","19","28","37"]):
        P.append(pin(n,"DRVDD","power_in","T",i,4))
    for i,n in enumerate(["4","5","25","26"]):
        P.append(pin(n,"NC","no_connect","R",i+1,4))
    return build("AD9251","U",
        "Package_DFN_QFN:QFN-64-1EP_9x9mm_P0.5mm_EP3.8x3.8mm_ThermalVias",
        "Dual 14-bit 80 MSPS ADC, 1.8V, LFCSP-64","AD9251BCPZ-80",P)


# ====================================================================
# ABLNO-V  — Abracon ultra-low noise VCXO
# ====================================================================
def ablno():
    P=[pin("1","VC","input","L",1,1),
       pin("2","GND","power_in","L",2,1),
       pin("3","OUT","output","R",1,1),
       pin("4","VDD","power_in","R",2,1)]
    return build("ABLNO-V","X","dogrudan-sdr:Oscillator_Abracon_ABLNO_4pad_14.3x8.7mm",
        "Ultra-low noise VCXO 80.00MHz, <100fs jitter, LVCMOS","ABLNO-V-80.000MHZ",
        P)


# ====================================================================
# AD9767 — datasheet Rev.G sayfa 9-10, Figure 5 + Table 6
# Cift 14-bit 125 MSPS TxDAC, 48-lead LQFP
# ====================================================================
def ad9767():
    P = []
    # --- birim 1: PORT 1 veri (DB13P1 pin1 MSB ... DB0P1 pin14 LSB)
    for i in range(14):                       # i=0 -> DB0 (LSB, pin 14)
        P.append(pin(str(14 - i), f"DB{i}P1", "input", "L", i, 1))
    for i, (n, nm) in enumerate([("17","WRT1/IQWRT"),("18","CLK1/IQCLK")]):
        P.append(pin(n, nm, "input", "R", i, 1))
    P.append(pin("16","DVDD1","power_in","T",0,1))
    P.append(pin("15","DCOM1","power_in","B",0,1))
    # --- birim 2: PORT 2 veri (DB13P2 pin23 MSB ... DB0P2 pin36 LSB)
    for i in range(14):
        P.append(pin(str(36 - i), f"DB{i}P2", "input", "L", i, 2))
    for i, (n, nm) in enumerate([("20","WRT2/IQSEL"),("19","CLK2/IQRESET")]):
        P.append(pin(n, nm, "input", "R", i, 2))
    P.append(pin("22","DVDD2","power_in","T",0,2))
    P.append(pin("21","DCOM2","power_in","B",0,2))
    # --- birim 3: ANALOG cikis + referans
    for i,(n,nm) in enumerate([("46","IOUTA1"),("45","IOUTB1"),
                               ("39","IOUTA2"),("40","IOUTB2")]):
        P.append(pin(n, nm, "output", "R", i, 3))
    for i,(n,nm,t) in enumerate([("43","REFIO","passive"),("44","FSADJ1","passive"),
                                 ("41","FSADJ2","passive"),("42","GAINCTRL","input"),
                                 ("48","MODE","input"),("37","SLEEP","input")]):
        P.append(pin(n, nm, t, "L", i, 3))
    P.append(pin("47","AVDD","power_in","T",0,3))
    P.append(pin("38","ACOM","power_in","B",0,3))
    return build("AD9767","U","Package_QFP:LQFP-48_7x7mm_P0.5mm",
        "Dual 14-bit 125 MSPS TxDAC, LQFP-48","AD9767ASTZ",P)


# ====================================================================
# RTL8211F  — datasheet Rev.1.1, Tablo 1-9 (PDF s.14-17)
# Gigabit Ethernet PHY, RGMII, 40-pin QFN 5x5 + exposed pad
# Not: 22-27 ve 32-34 cift islevli (reset aninda strap)
# ====================================================================
def rtl8211f():
    P = []
    # --- birim 1: RGMII + yonetim (MAC tarafi)
    rg = [("20","TXC","input"),("18","TXD0","input"),("17","TXD1","input"),
          ("16","TXD2","input"),("15","TXD3","input"),("19","TXCTL","input")]
    for i,(n,nm,t) in enumerate(rg): P.append(pin(n,nm,t,"L",i,1))
    rx = [("27","RXC/PHYAD1","output"),("25","RXD0/RXDLY","output"),
          ("24","RXD1/TXDLY","output"),("23","RXD2/PLLOFF","output"),
          ("22","RXD3/PHYAD0","output"),("26","RXCTL/PHYAD2","output")]
    for i,(n,nm,t) in enumerate(rx): P.append(pin(n,nm,t,"R",i,1))
    mg = [("13","MDC","input"),("14","MDIO","bidirectional"),
          ("12","~{PHYRSTB}","input"),("31","~{INTB}/~{PMEB}","open_collector")]
    for i,(n,nm,t) in enumerate(mg): P.append(pin(n,nm,t,"L",i+7,1))
    P.append(pin("28","DVDD_RG","power_in","T",0,1))
    # --- birim 2: analog + saat + guc
    md = [("1","MDIP0"),("2","MDIN0"),("4","MDIP1"),("5","MDIN1"),
          ("6","MDIP2"),("7","MDIN2"),("9","MDIP3"),("10","MDIN3")]
    for i,(n,nm) in enumerate(md): P.append(pin(n,nm,"bidirectional","L",i,2))
    ck = [("36","XTAL_IN","input"),("37","XTAL_OUT/EXT_CLK","output"),
          ("35","CLKOUT","output"),("39","RSET","passive"),("30","REG_OUT","output"),
          ("32","LED0/CFG_EXT","output"),("33","LED1/CFG_LDO0","output"),
          ("34","LED2/CFG_LDO1","output")]
    for i,(n,nm,t) in enumerate(ck): P.append(pin(n,nm,t,"R",i,2))
    for i,(n,nm) in enumerate([("29","DVDD33"),("21","DVDD10"),
                               ("11","AVDD33"),("40","AVDD33"),
                               ("3","AVDD10"),("8","AVDD10"),("38","AVDD10")]):
        P.append(pin(n,nm,"power_in","T",i,2))
    P.append(pin("41","GND","power_in","B",0,2))       # exposed pad
    return build("RTL8211F","U",
        "Package_DFN_QFN:QFN-40-1EP_5x5mm_P0.4mm_EP3.6x3.6mm",
        "Gigabit Ethernet PHY, RGMII, QFN-40","RTL8211FI-CG",P)


# ====================================================================
# PE4312 — datasheet DOC-81482-4.01 s.15, Tablo 9
# 0-31.5 dB sayisal adim zayiflatici, 20-lead QFN 4x4 + exposed pad
# ====================================================================
def pe4312():
    P = []
    for i,(n,nm,t) in enumerate([("2","RF1","passive"),("14","RF2","passive")]):
        P.append(pin(n,nm,t,"L",i,1))
    ctl = [("3","Data","input"),("4","Clock","input"),("5","LE","input"),
           ("13","P/S","input"),("7","PUP1","input"),("8","PUP2","input")]
    for i,(n,nm,t) in enumerate(ctl): P.append(pin(n,nm,t,"L",i+3,1))
    at = [("1","C16"),("15","C8"),("16","C4"),("17","C2"),("19","C1"),("20","C0.5")]
    for i,(n,nm) in enumerate(at): P.append(pin(n,nm,"input","R",i,1))
    P.append(pin("12","VSS_EXT/GND","input","R",7,1))
    for i,n in enumerate(["6","9"]): P.append(pin(n,"VDD","power_in","T",i,1))
    for i,n in enumerate(["10","11","18","Pad"]):
        P.append(pin(n,"GND","power_in","B",i,1))
    return build("PE4312","U",
        "Package_DFN_QFN:TQFN-20-1EP_4x4mm_P0.5mm_EP2.1x2.1mm",
        "0-31.5dB digital step attenuator, QFN-20","PE4312C-Z",P)


# ====================================================================
# ADP150 — datasheet Rev.E s.6, Tablo 5. 5-lead TSOT
# ====================================================================
def adt1_1wt():
    """ADT1-1WT+ — Mini-Circuits 1:1 RF trafo, CD542, Rev.G veri sayfasi.

    PIN CONNECTIONS (s.2):
        3  PRIMARY DOT      1  PRIMARY
        6  SECONDARY DOT    4  SECONDARY
        2  SECONDARY CT     5  NOT USED

    ** ILK HALINDE ORTA UC YANLISTI. ** Tahminle 5'e koymustum, gercekte
    2. Tam da "yanlissa Auto-MDIX kurtarmaz" dedigim sinif hata: orta uc
    yanlis yere gitseydi VCM ADC'nin ortak modunu hic basmayacak, dort
    RX kanali da calismayacakti.

    DIKKAT: bu parca 75 ohm. Empedans orani 1:1 oldugu icin 50 ohm
    sistemde de calisiyor ama uyumsuzluk var — bkz. NETLIST.md §10.14."""
    P = [pin("3", "PRI_DOT", "passive", "L", 0, 1),
         pin("1", "PRI", "passive", "L", 1, 1),
         pin("6", "SEC_DOT", "passive", "R", 0, 1),
         pin("4", "SEC", "passive", "R", 1, 1),
         pin("2", "SEC_CT", "passive", "B", 0, 1),
         pin("5", "NC", "no_connect", "R", 2, 1)]
    return build("ADT1-1WT", "T", "RF_Mini-Circuits:Mini-Circuits_CD542_H2.84mm",
        "1:1 RF trafo 75ohm 0.4-800MHz, tek-uc/diferansiyel", "ADT1-1WT+", P)


def xfmr_ct():
    """Birincili ORTA UCLU itme-cekme trafosu — 5 bacak.

    ** NEDEN VAR: IKI KATIN DA BESLEMESI YOKTU. **
    Device:Transformer_1P_1S dort bacakli ve orta ucu YOK. Itme-cekme
    kati beslemesini birincilin ORTA UCUNDAN alir; semada o dugum
    (D2_CT ve DRN_CT) ciziliydi, bogucusu ve baypas kondansatorleri
    de vardi, ama trafoda BAGLANACAK BACAK OLMADIGI ICIN havada
    kaliyordu. Netlistten olculdu:
        D2_CT  = {L11.2, C110.1}      -> iki parca, trafoya gitmiyor
        DRN_CT = {L20.2, C210..C212}  -> ayni durum
    Yani surucu katinin 12 V'u ve FINAL KATININ 50 V'u cihazlarin
    drainlerine hic ulasmiyordu. Kart basilsa iki kat da olu olurdu
    ve hicbir DRC/ERC bunu gormez: iki ag da en az iki pedli, yani
    "bagli" sayiliyor.

    Bacaklar:  1,2 birincil uclari   5 birincil ORTA UC   3,4 ikincil
    Ayak izi 5 pedli (lib/dogrudan-sdr.pretty/XFMR_Toroid_5P_Vertical).
    Fiziksel karsiligi: iki turlu bifilar birincilin orta noktasindaki
    tel eki — BN43-3312'de standart uygulama."""
    P = [pin("1", "PRI_A", "passive", "L", 0, 1),
         pin("5", "PRI_CT", "passive", "L", 1, 1),
         pin("2", "PRI_B", "passive", "L", 2, 1),
         pin("3", "SEC_A", "passive", "R", 0, 1),
         pin("4", "SEC_B", "passive", "R", 1, 1)]
    return build("XFMR_CT", "T", "dogrudan-sdr:XFMR_Toroid_5P_Vertical",
        "Orta uclu birincilli itme-cekme trafosu, toroid/binokuler",
        "XFMR_CT", P)


def hr911130a():
    """HR911130A — Hanrun gigabit RJ45, dahili manyetik + iki LED.
    Veri sayfasi Rev.A s.1 (semadan okundu), 14 bacak.

    ** ONCEKI PARCA (HR911105A) GIGABIT DEGILDI. ** Kapaginda
    "for 10/100Base-T NIC Applications" yaziyordu ve semasinda sadece
    iki cift sargi vardi. Iki GbE portu 100 Mbit'e duserdi.

    ** BACAK SAYISI 12 DEGIL 14. ** Ayak izi de degisti.

    Cift eslesmesi SIRALI DEGIL, ic ice:
        MDI0  P2 / P3      MDI1  P4 / P7
        MDI2  P5 / P6      MDI3  P8 / P9
    P1  = cip tarafi orta uclarin ORTAK dugumu
    P10 = govde/Bob Smith (icerideki 1000pF 2kV uzerinden)"""
    P = [pin("2", "MDI0+", "passive", "L", 0, 1),
         pin("3", "MDI0-", "passive", "L", 1, 1),
         pin("4", "MDI1+", "passive", "L", 2, 1),
         pin("7", "MDI1-", "passive", "L", 3, 1),
         pin("5", "MDI2+", "passive", "L", 4, 1),
         pin("6", "MDI2-", "passive", "L", 5, 1),
         pin("8", "MDI3+", "passive", "L", 6, 1),
         pin("9", "MDI3-", "passive", "L", 7, 1),
         pin("1", "CT_COM", "passive", "B", 0, 1),
         pin("10", "CHS", "passive", "B", 1, 1),
         pin("11", "LEDG_A", "passive", "R", 0, 1),
         pin("12", "LEDG_K", "passive", "R", 1, 1),
         pin("14", "LEDY_A", "passive", "R", 2, 1),
         pin("13", "LEDY_K", "passive", "R", 3, 1),
         # KALKAN PEDLERI SEMBOLDE YOKTU. Ayak izinde SH1-SH4 var
         # (iki 3.25 mm montaj kulagi + iki 1.63 mm tirnak) ama
         # sembolde karsiliklari olmadigi icin netlist onlara ag
         # atamiyordu: dort delik kartta AGSIZ bakir olarak duruyordu.
         # Sonuc, kablo ekraninin gidecek yeri olmamasi — ekran
         # konnektorun govdesinde bitiyor ve gurultu icin anten gibi
         # calisiyor. Dordu de CHASSIS'e baglanacak.
         pin("SH1", "SHIELD", "passive", "T", 0, 1),
         pin("SH2", "SHIELD", "passive", "T", 1, 1),
         pin("SH3", "SHIELD", "passive", "T", 2, 1),
         pin("SH4", "SHIELD", "passive", "T", 3, 1)]
    return build("HR911130A", "J", "dogrudan-sdr:RJ45_Hanrun_HR911130A",
        "RJ45 dahili manyetik + LED, 1000Base-T, 14 bacak", "HR911130A", P)


def w9825g6kh():
    """W9825G6KH-6I — Winbond 256Mbit (16Mx16) SDR SDRAM, TSOP-54.

    Dizilim JEDEC'in 54 bacakli x16 SDRAM standardi. Winbond bu
    standarda uyuyor; yine de kart basilmadan once veri sayfasiyla
    karsilastirilacak (ozellikle 40. bacak: bazi ureticilerde NC,
    bazilarinda ikinci CKE).

    Birim 1: veri yolu (DQ0-15 + DQM). Birim 2: adres + komut.
    Birim 3: guc. Boylece 05_sdram sayfasinda veri yolu ile komut
    yolu ayri cizilebiliyor — banka 7 / banka 0 bolunmesi de oyle."""
    dq = {2:0, 4:1, 5:2, 7:3, 8:4, 10:5, 11:6, 13:7,
          42:8, 44:9, 45:10, 47:11, 48:12, 50:13, 51:14, 53:15}
    P = []
    for i, (num, bit) in enumerate(sorted(dq.items(), key=lambda z: z[1])):
        P.append(pin(num, f"DQ{bit}", "bidirectional", "L" if bit < 8 else "R",
                     bit % 8, 1))
    P.append(pin(15, "LDQM", "input", "B", 0, 1))
    P.append(pin(39, "UDQM", "input", "B", 1, 1))

    addr = {23:0, 24:1, 25:2, 26:3, 29:4, 30:5, 31:6, 32:7,
            33:8, 34:9, 22:10, 35:11, 36:12}
    for num, a in sorted(addr.items(), key=lambda z: z[1]):
        P.append(pin(num, f"A{a}", "input", "L", a, 2))
    for i, (num, nm) in enumerate([(20, "BA0"), (21, "BA1"), (19, "~{CS}"),
                                   (18, "~{RAS}"), (17, "~{CAS}"), (16, "~{WE}"),
                                   (37, "CKE"), (38, "CLK")]):
        P.append(pin(num, nm, "input", "R", i, 2))
    P.append(pin(40, "NC", "no_connect", "R", 8, 2))

    for i, num in enumerate([1, 14, 27]):
        P.append(pin(num, "VDD", "power_in", "T", i, 3))
    for i, num in enumerate([3, 9, 43, 49]):
        P.append(pin(num, "VDDQ", "power_in", "T", i + 3, 3))
    for i, num in enumerate([28, 41, 54]):
        P.append(pin(num, "VSS", "power_in", "B", i, 3))
    for i, num in enumerate([6, 12, 46, 52]):
        P.append(pin(num, "VSSQ", "power_in", "B", i + 3, 3))
    return build("W9825G6KH", "U", "Package_SO:TSOP-II-54_22.2x10.16mm_P0.8mm",
        "256Mbit (16Mx16) SDR SDRAM 166MHz, TSOP-54", "W9825G6KH-6I", P)


def adclk846():
    """ADCLK846 — ADI 1:6 LVDS/12 CMOS saat dagitim tamponu, LFCSP-24.
    Veri sayfasi Rev.C, Tablo 7 (s.7).

    ** VS = 1.8 V. ** Baslikta yaziyor: "1.8 V, 6 LVDS/12 CMOS Output
    Clock Fanout Buffer". Guc agacinda saat bolumu 3.3 V varsayilmisti,
    tamponun kendi 1.8 V rayi gerekiyor.

    Birim 1: giris + kontrol + alti diferansiyel cikis.
    Birim 2: alti VS bacagi + acik ped (toprak)."""
    P = [pin("1", "VREF", "output", "L", 0, 1),
         pin("3", "CLK+", "input", "L", 1, 1),
         pin("2", "CLK-", "input", "L", 2, 1),
         pin("5", "CTRL_A", "input", "L", 3, 1),
         pin("6", "CTRL_B", "input", "L", 4, 1),
         pin("7", "SLEEP", "input", "L", 5, 1)]
    outs = [(24, 23, 0), (21, 20, 1), (18, 17, 2),
            (15, 14, 3), (12, 11, 4), (9, 8, 5)]
    for i, (a, b, n) in enumerate(outs):
        P.append(pin(a, f"OUT{n}A", "output", "R", i * 2, 1))
        P.append(pin(b, f"OUT{n}B", "output", "R", i * 2 + 1, 1))
    for i, num in enumerate([4, 10, 13, 16, 19, 22]):
        P.append(pin(num, "VS", "power_in", "T", i, 2))
    P.append(pin("25", "EPAD", "power_in", "B", 0, 2))
    return build("ADCLK846", "U",
        "Package_DFN_QFN:HVQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm",
        "1:6 LVDS saat dagitim tamponu 1.8V, LFCSP-24",
        "ADCLK846BCPZ-REEL7", P)


def g6ku():
    """G6KU-2F-Y — Omron 2 Form C, TEK SARIMLI KILITLENEN role, 5 VDC.
    Veri sayfasi (en-g6k) s.7 terminal dizilimi, TOP VIEW.

        8   7   6   5          6 ve 3 ORTAK uclar (blade)
        [bobin S/R]            7/5 ve 2/4 sabit kontaklar
        1   2   3   4

    Tek sarim: bobine verilen GERILIMIN YONU konumu belirliyor.
    Bir yon = SET, ters yon = RESET. Bu yuzden acik drenaj surucu
    YETMIYOR, H koprusu gerekiyor (bkz 05_driver).

    Kilitlenen: akim sadece darbe sirasinda akiyor. Guc butcesi
    hesabi NETLIST_C.md §1'de — normal role dort kanalda 1.44 W
    cekiyordu, A kartinin toplam butcesi 2.8 W.

    Bobin: 5 VDC, 21.1 mA, 237 ohm, ~100 mW darbe sirasinda.
    RF: VSWR < 1.25 @ 100 MHz'e kadar (veri sayfasi s.5 grafigi)."""
    P = [pin("1", "COIL_S", "passive", "L", 0, 1),
         pin("8", "COIL_R", "passive", "L", 1, 1),
         pin("3", "COM1", "passive", "L", 3, 1),
         pin("2", "N1A", "passive", "R", 0, 1),
         pin("4", "N1B", "passive", "R", 1, 1),
         pin("6", "COM2", "passive", "L", 4, 1),
         pin("7", "N2A", "passive", "R", 2, 1),
         pin("5", "N2B", "passive", "R", 3, 1)]
    return build("G6KU-2F-Y", "K", "Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y",
        "2 Form C tek sarimli kilitlenen role 5V, RF", "G6KU-2F-Y-TR DC5", P)


def g2rl():
    """G2RL-2 12V — Omron 2 Form C, 8 A guc rolesi, THT.

    NEDEN AYRI SEMBOL: LPF bankasi G6K sembolunu G2RL-2 AYAK IZIYLE
    kullaniyordu. G6K'nin pinleri 1..8, G2RL-2 ayak izininki IEC
    konvansiyonunda 11/12/14/21/22/24/A1/A2. Isimler tutmayinca aglar
    pedlere hic inmedi: yedi rolenin 56 pedi de bagsizdi ve ERC bunu
    gormedi, cunku semada her sey baglanmisti.

    Ayrica G6K yanlis parcaydi. Sinyal rolesi, 1 A / 30 VDC. 100 W'ta
    50 ohm'da akim 1.4 A ve tepe gerilim 100 V — kontak hem akimda hem
    gerilimde asiliyor, ilk anahtarlamada yapisir. G2RL-2 8 A / 250 VAC.

    Kilitlenmiyor: LPF bandi verirken surekli cekili kalir. Bobin
    12 V / 33 mA = 400 mW, tek bant aktif oldugu icin bir role.
    Kilitlenen tipi secmedik cunku bant degisimi sirasinda iki bandin
    ayni anda kapali kalmasi RF'i aciga birakir.
    """
    P = [pin("A1", "COIL+", "passive", "L", 0, 1),
         pin("A2", "COIL-", "passive", "L", 1, 1),
         pin("11", "COM1", "passive", "L", 3, 1),
         pin("12", "NC1", "passive", "R", 0, 1),
         pin("14", "NO1", "passive", "R", 1, 1),
         pin("21", "COM2", "passive", "L", 4, 1),
         pin("22", "NC2", "passive", "R", 2, 1),
         pin("24", "NO2", "passive", "R", 3, 1)]
    return build("G2RL-2-12V", "K", "Relay_THT:Relay_DPDT_Omron_G2RL-2",
        "2 Form C guc rolesi 12V 8A, LPF bankasi", "G2RL-2 DC12", P)


def g6k():
    """G6K-2F-Y — Omron 2 Form C, TEK TARAFLI KARARLI (kilitlenmeyen).
    G6KU ile ayni govde ve ayni terminal dizilimi; fark bobinde.

    T/R ROLESI NEDEN KILITLENMEYEN:
    Kilitlenen role gucsuz kaldigi konumu KORUR. T/R'da bu tehlikeli —
    guc kesilse ya da firmware cokse anten PA'ya bagli kalir, alici
    girisine 100 W dusebilir. Kilitlenmeyen role birakildiginda
    kendiliginden RX konumuna doner. Guvenlik varsayilan durumdan
    gelmeli, yazilimdan degil.

    Bedeli: verirken bobin surekli cekili, 5 V / 28 mA = 140 mW.
    Ayni anda tek port verdigi icin bir bobin. Kabul.
    Filtre bankasinda ise durum tersi: orada surekli cekili kalmak
    guc butcesini yiyordu, o yuzden oralar KILITLENEN (G6KU)."""
    P = [pin("1", "COIL+", "passive", "L", 0, 1),
         pin("8", "COIL-", "passive", "L", 1, 1),
         pin("3", "COM1", "passive", "L", 3, 1),
         pin("2", "NC1", "passive", "R", 0, 1),
         pin("4", "NO1", "passive", "R", 1, 1),
         pin("6", "COM2", "passive", "L", 4, 1),
         pin("7", "NC2", "passive", "R", 2, 1),
         pin("5", "NO2", "passive", "R", 3, 1)]
    return build("G6K-2F-Y", "K", "Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y",
        "2 Form C tek tarafli kararli role 5V, RF", "G6K-2F-Y DC5", P)


def ina240():
    """INA240A1DR — TI akim algilama yukselteci, SOIC-8.
    Veri sayfasi Tablo 6-1 (SOIC sutunu).

    PA bias servosunda drain akimini olcuyor. Ortak mod -4..+80 V,
    yani 50 V rayin ust tarafindan olcum yapabiliyor. Kazanc A1 = 20 V/V.
    Gerilim vurusu bastirmali (PWM icin tasarlanmis) — bizde DC ama
    zarari yok."""
    P = [pin("8", "IN+", "input", "L", 0, 1),
         pin("1", "IN-", "input", "L", 1, 1),
         pin("7", "REF1", "input", "L", 3, 1),
         pin("3", "REF2", "input", "L", 4, 1),
         pin("5", "OUT", "output", "R", 0, 1),
         pin("4", "NC", "no_connect", "R", 2, 1),
         pin("6", "V+", "power_in", "T", 0, 1),
         pin("2", "GND", "power_in", "B", 0, 1)]
    return build("INA240A1", "U", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "akim algilama yukselteci, 80V ortak mod, kazanc 20", "INA240A1DR", P)


def pga103():
    """PGA-103+ — Mini-Circuits monolitik yukseltec, SOT-89-4.
    Veri sayfasi s.2: 1 RF-IN, 2 GROUND, 3 RF-OUT ve DC-IN, 4 GND.

    Besleme RF cikisindan veriliyor (bias tee): 3 numarali bacak hem
    RF cikisi hem DC girisi. Aralarina RF boguculu bir bobin ve
    ayirici kondansator gerekiyor — bu tur monolitik yukselteclerde
    standart. Pin 3'te azami DC 6 V."""
    P = [pin("1", "RF_IN", "passive", "L", 0, 1),
         pin("3", "RF_OUT_DC_IN", "passive", "R", 0, 1),
         pin("2", "GND", "power_in", "B", 0, 1),
         pin("4", "GND_TAB", "power_in", "B", 1, 1)]
    return build("PGA-103", "U", "Package_TO_SOT_SMD:SOT-89-3",
        "monolitik yukseltec 0.05-4 GHz, +22 dB", "PGA-103+", P)


def ad8318():
    """AD8318 — ADI logaritmik detektor, LFCSP-16. Rev.E Tablo 3.

    ** ILK SEMBOL TAMAMEN YANLISTI. ** Veri sayfasi indirilemedigi icin
    bacaklari tahmin etmis ve "PINOUT DOGRULANMADI" diye isaretlemistim.
    Veri sayfasi gelince dokuz bacagin HICBIRI tutmadi. Tahmini
    isaretlemek dogru karardi; isaretlemeseydik kart basilirdi.

    Gercek dizilim:
      1,2,11,12  CMIP   giris tarafi toprak
      3,4        VPSI   giris tarafi besleme 4.5-5.5 V
      5          CLPF   dongu filtresi
      6          VOUT   olcum/kontrol cikisi
      7          VSET   olcum modunda VOUT'a baglanir
      8          CMOP   cikis tarafi toprak
      9          VPSO   cikis tarafi besleme (VPSI ile ESIT olmali)
      10         TADJ   sicaklik telafisi
      13         TEMP   sicaklik sensoru cikisi
      14         INHI   RF girisi, -60..0 dBm, AC kuplajli
      15         INLO   RF ortak, AC kuplajli
      16         ENBL   VPSI'ye baglanirsa calisir
      EPAD              CMIP'e dahili bagli, TOPRAGA lehimlenmeli"""
    P = [pin("14", "INHI", "input", "L", 0, 1),
         pin("15", "INLO", "input", "L", 1, 1),
         pin("5", "CLPF", "passive", "L", 3, 1),
         pin("7", "VSET", "input", "L", 4, 1),
         pin("16", "ENBL", "input", "L", 5, 1),
         pin("6", "VOUT", "output", "R", 0, 1),
         pin("13", "TEMP", "output", "R", 1, 1),
         pin("10", "TADJ", "input", "R", 3, 1),
         pin("3", "VPSI", "power_in", "T", 0, 1),
         pin("4", "VPSI2", "power_in", "T", 1, 1),
         pin("9", "VPSO", "power_in", "T", 2, 1),
         pin("1", "CMIP", "power_in", "B", 0, 1),
         pin("2", "CMIP2", "power_in", "B", 1, 1),
         pin("11", "CMIP3", "power_in", "B", 2, 1),
         pin("12", "CMIP4", "power_in", "B", 3, 1),
         pin("8", "CMOP", "power_in", "B", 4, 1),
         pin("17", "EPAD", "power_in", "B", 5, 1)]
    return build("AD8318", "U",
        "Package_DFN_QFN:NXP_VQFN-16-1EP_4x4mm_P0.65mm_EP2.1x2.1mm",
        "logaritmik detektor 1 MHz-8 GHz, 70 dB araLik",
        "AD8318ACPZ-REEL7", P)


def adp150():
    P = [pin("1","VIN","power_in","L",0,1),
         pin("3","EN","input","L",1,1),
         pin("5","VOUT","power_out","R",0,1),
         pin("4","NC","no_connect","R",1,1),
         pin("2","GND","power_in","B",0,1)]
    return build("ADP150","U","Package_TO_SOT_SMD:TSOT-23-5",
        "150mA ultralow noise LDO, TSOT-5","ADP150AUJZ",P)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    # ECP5 sembolu Lattice pinout CSV'sinden ayri uretildi, elle
    # tutulan tek blok. Onu koru, gerisini HER SEFERINDE sifirdan yaz.
    # Once dosyanin sonuna ekliyordum: ikinci calistirmada butun
    # semboller ciftlendi, KiCad ilk kopyayi alip digerini sessizce
    # yok saydi. Uretecin idempotent olmasi sart.
    path = os.path.join(here, "dogrudan-sdr.kicad_sym")
    keep = ""
    if os.path.exists(path):
        s = open(path, encoding="utf-8").read()
        i = s.find('  (symbol "ECP5-BGA256"')
        if i >= 0:
            depth, j = 0, i
            while j < len(s):
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            keep = s[i:j] + "\n"
    gens = [ad9251, ad9767, rtl8211f, pe4312, adp150, ablno, adt1_1wt, xfmr_ct,
            hr911130a, w9825g6kh, adclk846, g6ku, g6k, g2rl, ina240, pga103, ad8318]
    body = "\n".join(g() for g in gens)
    open(path, "w", encoding="utf-8").write(
        "(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n"
        + keep + body + "\n)\n")
    print(f"{len(gens) + (1 if keep else 0)} sembol uretildi")
