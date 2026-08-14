#!/usr/bin/env python3
"""06_power: 50V dagitim, koruma, kontrol arayuzu.
Kaynak: ../../PA_TASARIM.md §7, §9, §10."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

BUCK = "Regulator_Switching:TPS62130"
FBUCK = "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm"
SR = "74xx:74HC595"
FSR = "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"
TMP = "Sensor_Temperature:MCP9700Ax-ETT"
FTMP = "Package_TO_SOT_SMD:SOT-23"
Q = "Transistor_FET:Q_PMOS_GSD"
FQP = "Package_TO_SOT_THT:TO-220-3_Vertical"
QN = "Transistor_FET:Q_NMOS_GDS"
FQN = "Package_TO_SOT_SMD:SOT-23"
R, C, L = "Device:R", "Device:C", "Device:L"
FR = "Resistor_SMD:R_0603_1608Metric"
FRP = "Resistor_SMD:R_2512_6332Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
FCP = "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"
FL = "Inductor_SMD:L_Taiyo-Yuden_NR-30xx"
HDR = "Connector_Generic:Conn_02x10_Odd_Even"
HDR6 = "Connector_Generic:Conn_01x06"
FHDR6 = "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"
FHDR = "Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Vertical"
CONN = "Connector_Generic:Conn_01x02"
FCONN = "TerminalBlock_CUI:TerminalBlock_CUI_TB007-508-02_1x02_P5.08mm_Horizontal"

s = Sheet("06_power", "Guc ve koruma", UU["06_power"],
          "50V dagitim, ters polarite, SWR ve sicaklik kesme", paper="A1")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{599 + nr[0]}"


s.text("GUC VE KORUMA", 16, 14, 2.2)
s.text("final       50 V / 6.7 A = 333 W     (A sinifi 100 W)\\n"
       "surucu 2    12 V / 1.0 A =  12 W\\n"
       "lojik+lojik 5 V ve 3.3 V =   5 W\\n"
       "                          --------\\n"
       "toplam                     ~350 W", 16, 22, 1.4)

# ---------------------------------------------------------------- giris
s.sym(CONN, "J30", "50V giris", 45, 75, fp=FCONN)
s.pin_label(CONN, "1", 45, 75, 0, "VIN50", "input")
s.pin_power(CONN, "2", 45, 75, 0, "GND")
# Kart disindan gelen raylar icin bayrak: bu kartta 50 V ve 3.3 V
# ureten bir pin yok, ERC surucu goremiyor.
for _n, _x in (("+50V", 200), ("+3V3", 240), ("GND", 280)):
    if _n == "GND":
        s.power("GND", _x, 110)
        s.wire(_x, 110, _x, 103.65)
        s.pwr_flag(_x, 103.65)
    else:
        s.glabel(_n, _x, 110, "input")
        s.wire(_x, 110, _x, 103.65)
        s.pwr_flag(_x, 103.65)

s.sym(Q, "Q30", "IRF9540N", 85, 72, fp=FQP)
s.pin_label(Q, "3", 85, 72, 0, "VIN50", "passive", d=7.62)
s.pin_label(Q, "2", 85, 72, 0, "+50V", "output", d=7.62)
s.sym(R, cnt("R"), "100k", 85, 98, rot=90, fp=FR)
s.pin_label(R, "1", 85, 98, 90, "VIN50_G", "passive")
s.pin_power(R, "2", 85, 98, 90, "GND")
s.pin_label(Q, "1", 85, 72, 0, "VIN50_G", "passive", d=12.7)
s.sym("Device:D_Zener", "D30", "15V", 108, 98, rot=90, fp="Diode_SMD:D_SOD-323")
s.pin_label("Device:D_Zener", "2", 108, 98, 90, "VIN50_G", "passive")
s.pin_power("Device:D_Zener", "1", 108, 98, 90, "GND")
for i, v in enumerate(("470uF", "470uF")):
    s.sym(C, cnt("C"), v, 135 + i * 22, 75, rot=90, fp=FCP)
    s.pin_label(C, "1", 135 + i * 22, 75, 90, "+50V", "input")
    s.pin_power(C, "2", 135 + i * 22, 75, 90, "GND")

s.text("Ters polarite: P-MOSFET, A kartindakinin ayni mantigi ama\\n"
       "buyugu. 6.7 A gectigi icin TO-220 ve dusuk Rds(on).\\n"
       "Zener Vgs'i 15 V'ta sinirliyor (50 V rayda -50 V gorurdu).",
       16, 120, 1.35)

# ---------------------------------------------------------------- turev raylar
# GUC AGACI DUZELTILDI:  50 V --LM5164--> 12 V --TPS62130--> 5 V
# Ilk cizimde turev raylari 50 V'tan ve 24 V'tan TPS62130 ile aliyordum.
# O parcanin giris tavani 17 V — ikisi de yanlisti, kart ilk aciliste
# olurdu. 24 V rayi tamamen kalkti; surucu 2 artik 12 V'tan calisiyor
# (8 W cikis icin yeterli) ve bir donusum kati eksildi.
s.text("TUREV RAYLAR", 16, 150, 1.8)

HVB = "Regulator_Switching:LM5164DDA"
FHVB = "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm_ThermalVias"
x12, y12 = 60, 190
s.sym(HVB, "U50", "LM5164DDAR", x12, y12, fp=FHVB)
s.pin_label(HVB, "2", x12, y12, 0, "+50V", "input", d=10.16)
s.pin_label(HVB, "3", x12, y12, 0, "+50V", "input", d=15.24)
s.pin_power(HVB, "1", x12, y12, 0, "GND", d=10.16)
s.pin_power(HVB, "9", x12, y12, 0, "GND", d=15.24)
s.pin_label(HVB, "5", x12, y12, 0, "FB_12V", "input", d=20.32)
s.pin_label(HVB, "4", x12, y12, 0, "RON_12V", "passive", d=25.4)
s.nc(*s.P(HVB, "6", x12, y12))
s.pin_label(HVB, "7", x12, y12, 0, "BST_12V", "passive", d=7.62)
s.pin_label(HVB, "8", x12, y12, 0, "SW_12V", "output", d=12.7)
s.sym(C, cnt("C"), "100nF", x12 + 45, y12 - 22, rot=90, fp=FC)
s.pin_label(C, "1", x12 + 45, y12 - 22, 90, "BST_12V", "passive")
s.pin_label(C, "2", x12 + 45, y12 - 22, 90, "SW_12V", "passive")
s.sym(R, cnt("R"), "100k", x12 + 45, y12 + 28, rot=90, fp=FR)
s.pin_label(R, "1", x12 + 45, y12 + 28, 90, "RON_12V", "passive")
s.pin_power(R, "2", x12 + 45, y12 + 28, 90, "GND")
s.sym(L, "L50", "47uH", x12 + 80, y12, rot=90, fp=FL)
s.pin_label(L, "1", x12 + 80, y12, 90, "SW_12V", "passive")
s.pin_label(L, "2", x12 + 80, y12, 90, "+12V", "output")
for k, v in enumerate(("22uF", "100nF")):
    s.sym(C, cnt("C"), v, x12 + 110 + k * 20, y12, rot=90, fp=FC)
    s.pin_label(C, "1", x12 + 110 + k * 20, y12, 90, "+12V", "input")
    s.pin_power(C, "2", x12 + 110 + k * 20, y12, 90, "GND")
s.glabel("+12V", x12 + 10, y12 + 55, "input")
s.wire(x12 + 10, y12 + 55, x12 + 10, y12 + 48.65)
s.pwr_flag(x12 + 10, y12 + 48.65)
for k, (rr, hi) in enumerate((("140k", True), ("10k", False))):
    rx, ry = x12 + 165, y12 + 12 + k * 22
    s.sym(R, cnt("R"), rr, rx, ry, rot=90, fp=FR)
    if hi:
        s.pin_label(R, "1", rx, ry, 90, "+12V", "input")
        s.pin_label(R, "2", rx, ry, 90, "FB_12V", "passive")
    else:
        s.pin_label(R, "1", rx, ry, 90, "FB_12V", "passive")
        s.pin_power(R, "2", rx, ry, 90, "GND")

x5, y5 = 60, 265
s.sym(BUCK, "U51", "TPS62130", x5, y5, fp=FBUCK)
s.pin_label(BUCK, "10", x5, y5, 0, "+12V", "input", d=15.24)
s.pin_label(BUCK, "13", x5, y5, 0, "+12V", "input", d=20.32)
s.pin_power(BUCK, "6", x5, y5, 0, "GND", d=8.89)
s.pin_power(BUCK, "7", x5, y5, 0, "GND", d=8.89)
s.pin_power(BUCK, "8", x5, y5, 0, "GND", d=13.97)
s.nc(*s.P(BUCK, "9", x5, y5))
s.nc(*s.P(BUCK, "4", x5, y5))
s.pin_label(BUCK, "14", x5, y5, 0, "+5V", "input", d=25.4)
s.pin_label(BUCK, "5", x5, y5, 0, "FB_5V", "input", d=30.48)
sw5 = s.P(BUCK, "1", x5, y5)
s.sym(L, "L51", "2.2uH", sw5[0] + 15, sw5[1], rot=90, fp=FL)
s.link(sw5, s.P(L, "1", sw5[0] + 15, sw5[1], 90))
o5 = s.P(L, "2", sw5[0] + 15, sw5[1], 90)
s.wire(o5[0], o5[1], o5[0] + 12, o5[1])
s.glabel("+5V", o5[0] + 12, o5[1], "output")
s.glabel("+5V", x5 + 10, y5 + 40, "input")
s.wire(x5 + 10, y5 + 40, x5 + 10, y5 + 33.65)
s.pwr_flag(x5 + 10, y5 + 33.65)
for k, (rr, hi) in enumerate((("105k", True), ("20k", False))):
    rx, ry = x5 + 80, y5 + 12 + k * 22
    s.sym(R, cnt("R"), rr, rx, ry, rot=90, fp=FR)
    if hi:
        s.pin_label(R, "1", rx, ry, 90, "+5V", "input")
        s.pin_label(R, "2", rx, ry, 90, "FB_5V", "passive")
    else:
        s.pin_label(R, "1", rx, ry, 90, "FB_5V", "passive")
        s.pin_power(R, "2", rx, ry, 90, "GND")
for k, v in enumerate(("22uF", "100nF")):
    s.sym(C, cnt("C"), v, x5 + 140 + k * 20, y5, rot=90, fp=FC)
    s.pin_label(C, "1", x5 + 140 + k * 20, y5, 90, "+5V", "input")
    s.pin_power(C, "2", x5 + 140 + k * 20, y5, 90, "GND")

s.text("50 V --LM5164--> 12 V --TPS62130--> 5 V\\n\\n"
       "Ilk cizimde turev raylar 50 V ve 24 V'tan TPS62130 ile aliniyordu.\\n"
       "O parcanin giris tavani 17 V; ikisi de yanlisti ve kart ilk\\n"
       "aciliste olurdu. 24 V rayi kalkti, surucu 2 artik 12 V'tan.\\n\\n"
       "LM5164: 100 V giris, 1 A, sabit acik-zamanli. RON direnci\\n"
       "anahtarlama frekansini belirliyor.", 300, 190, 1.3)

# ---------------------------------------------------------------- koruma
s.text("KORUMA — donanimda, yazilimda degil", 300, 150, 1.8)
s.sym(TMP, "U55", "MCP9700AT", 340, 190, fp=FTMP)
s.pin_label(TMP, "1", 340, 190, 0, "+3V3", "input", d=7.62)
s.pin_label(TMP, "2", 340, 190, 0, "FLANGE_T", "output", d=7.62)
s.pin_power(TMP, "3", 340, 190, 0, "GND", d=7.62)

# DPD ornekleme rolesi surucusu (04_detect'teki K20)
s.sym(QN, "Q32", "2N7002", 400, 250, fp=FQN)
s.pin_label(QN, "1", 400, 250, 0, "DPD_EN", "input", d=7.62)
s.pin_label(QN, "2", 400, 250, 0, "DPD_EN_LO", "passive", d=7.62)
s.pin_power(QN, "3", 400, 250, 0, "GND", d=12.7)
s.sym(R, cnt("R"), "100k", 378, 272, rot=90, fp=FR)
s.pin_label(R, "1", 378, 272, 90, "DPD_EN", "passive")
s.pin_power(R, "2", 378, 272, 90, "GND")
s.sym("Device:D", cnt("D"), "1N4148WS", 424, 272, rot=90,
      fp="Diode_SMD:D_SOD-323")
s.pin_label("Device:D", "1", 424, 272, 90, "DPD_EN_LO", "passive")
s.pin_label("Device:D", "2", 424, 272, 90, "+5V", "input")

s.sym(QN, "Q31", "2N7002", 400, 190, fp=FQN)
s.pin_label(QN, "1", 400, 190, 0, "PA_INHIBIT", "input", d=7.62)
s.pin_label(QN, "2", 400, 190, 0, "DRV_EN_LO", "passive", d=7.62)
s.pin_power(QN, "3", 400, 190, 0, "GND", d=12.7)
s.sym(R, cnt("R"), "100k", 380, 212, rot=90, fp=FR)
s.pin_label(R, "1", 380, 212, 90, "PA_INHIBIT", "passive")
s.pin_power(R, "2", 380, 212, 90, "GND")

s.text("TMP235 FLANSTA, cihazlarin dibinde. 10 mV/C, FPGA ADC'siyle\\n"
       "okunuyor. 233 W dagitan bir kartta sicaklik olcumu tercih degil.\\n\\n"
       "PA_INHIBIT hatti: FPGA sifirlaninca ya da besleme yokken 100k\\n"
       "asagi cekiyor, MOSFET kapali, surucu ETKIN DEGIL. Guvenlik\\n"
       "varsayilan durumdan gelmeli.\\n\\n"
       "KESME SARTLARI (FPGA'da, ama hepsi olculen deger uzerinden):\\n"
       "  yansiyan guc esigi asildi     -> SWR korumasi (04_detect)\\n"
       "  flans sicakligi > 85 C        -> kademe dusur, > 100 C kes\\n"
       "  Idq kurulan degerden %20 sapti-> bias servosu bozuk, kes\\n"
       "  DRV8833 ~FAULT (C karti)      -> role surucusu arizali",
       300, 220, 1.35)

# ---------------------------------------------------------------- LPF surucu
s.text("LPF ROLE SURUCUSU", 16, 300, 1.8)
s.sym(SR, "U56", "74HC595D", 60, 345, fp=FSR)
s.pin_label(SR, "14", 60, 345, 0, "RLY_SER_OUT", "input", d=7.62)
s.pin_label(SR, "11", 60, 345, 0, "RLY_SRCLK", "input", d=12.7)
s.pin_label(SR, "12", 60, 345, 0, "RLY_RCLK", "input", d=17.78)
s.pin_label(SR, "10", 60, 345, 0, "+3V3", "input", d=22.86)
s.pin_power(SR, "13", 60, 345, 0, "GND", d=27.94)
s.pin_label(SR, "16", 60, 345, 0, "+3V3", "input", d=5.08)
s.pin_power(SR, "8", 60, 345, 0, "GND", d=5.08)
s.nc(*s.P(SR, "9", 60, 345))
for j, pn in enumerate(("15", "1", "2", "3", "4", "5", "6")):
    s.pin_label(SR, pn, 60, 345, 0, f"LQ{j}", "output", d=5.08)
s.nc(*s.P(SR, "7", 60, 345))
s.sym(C, cnt("C"), "100nF", 105, 345, rot=90, fp=FC)
s.pin_label(C, "1", 105, 345, 90, "+3V3", "input")
s.pin_power(C, "2", 105, 345, 90, "GND")

# yedi role, her biri bir MOSFET + sonumleme diyodu
for j in range(7):
    qx, qy = 150 + j * 30, 345
    s.sym(QN, f"QL{j + 1}", "2N7002", qx, qy, fp=FQN)
    s.pin_label(QN, "1", qx, qy, 0, f"LQ{j}", "input", d=12.7)
    s.pin_label(QN, "2", qx, qy, 0, f"KL{j + 1}_LO", "passive", d=7.62)
    s.pin_power(QN, "3", qx, qy, 0, "GND", d=12.7)
    s.sym("Device:D", cnt("D"), "1N4148WS", qx, qy - 22, rot=90,
          fp="Diode_SMD:D_SOD-323")
    s.pin_label("Device:D", "1", qx, qy - 22, 90, f"KL{j + 1}_LO", "passive")
    s.pin_label("Device:D", "2", qx, qy - 22, 90, "+12V", "input")

s.text("Yedi LPF rolesi kilitlenmeyen G2RL-2, 12 V bobin. Kilitlenen\\n"
       "DEGIL: guc kesilince bypass'a donmeli, filtre yanlis bantta\\n"
       "kalmamali. Bobin akimi ~30 mA, 2N7002 rahat.\\n\\n"
       "Sonumleme diyodu SART: bobin kesilince endüktif vurus MOSFET'i\\n"
       "deler. 74HC595 cikislari MOSFET geçidini suruyor, akimi\\n"
       "MOSFET veriyor.\\n\\n"
       "ZINCIRE EKLENDI: bu yazmac C kartindaki yedi 74HC595'in\\n"
       "sekizinci halkasi. RLY_SER_OUT C'nin son yazmacinin QH' cikisi,\\n"
       "saat ve mandal ortak. D kartina ayri seri hat cekilmedi.",
       16, 380, 1.35)

# ---------------------------------------------------------------- yerel ADC
# Uc analog olcum (flans sicakligi, ileri ve yansiyan guc) A kartina
# GITMIYOR: orada banka dolu ve uc analog hattin kart arasi bagliktan
# gecmesi zaten kotu fikir. Yerel 12 bit ADC ayni seri yolu paylasiyor.
ADC = "Analog_ADC:MCP3208"
FADC = "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"
s.text("YEREL OLCUM ADC'si", 620, 300, 1.8)
s.sym(ADC, "U57", "MCP3208T-CI/SL", 670, 345, fp=FADC)
s.pin_label(ADC, "1", 670, 345, 0, "FLANGE_T", "input", d=7.62)
s.pin_label(ADC, "2", 670, 345, 0, "FWD_LOG", "input", d=12.7)
s.pin_label(ADC, "3", 670, 345, 0, "REV_LOG", "input", d=17.78)
s.pin_label(ADC, "4", 670, 345, 0, "IMEAS1", "input", d=22.86)
s.pin_label(ADC, "5", 670, 345, 0, "IMEAS2", "input", d=27.94)
s.pin_label(ADC, "6", 670, 345, 0, "IMEAS3", "input", d=33.02)
s.pin_label(ADC, "7", 670, 345, 0, "IMEAS4", "input", d=38.1)
s.pin_power(ADC, "8", 670, 345, 0, "GND", d=43.18)
s.pin_label(ADC, "11", 670, 345, 0, "ATT_DATA", "input", d=7.62)
s.pin_label(ADC, "12", 670, 345, 0, "ADC_SDIO", "output", d=12.7)
s.pin_label(ADC, "13", 670, 345, 0, "ATT_CLK", "input", d=17.78)
s.pin_label(ADC, "10", 670, 345, 0, "PA_ADC_CS", "input", d=22.86)
s.pin_label(ADC, "16", 670, 345, 0, "+3V3", "input", d=27.94)
s.pin_label(ADC, "15", 670, 345, 0, "+3V3", "input", d=33.02)
s.pin_power(ADC, "9", 670, 345, 0, "GND", d=5.08)
s.pin_power(ADC, "14", 670, 345, 0, "GND", d=10.16)
s.sym(C, cnt("C"), "100nF", 735, 345, rot=90, fp=FC)
s.pin_label(C, "1", 735, 345, 90, "+3V3", "input")
s.pin_power(C, "2", 735, 345, 90, "GND")

s.text("Sekiz kanaldan yedisi kullaniliyor: flans sicakligi, ileri ve\\n"
       "yansiyan guc, ve DORT CIHAZIN DRAIN AKIMI.\\n\\n"
       "Akim olcumlerini de buraya baglamak bedavaydi ve degerli: bias\\n"
       "servosu kapali cevrim calisiyor ama FPGA'nin gercek akimi\\n"
       "GORMESI gerekiyor — servo bozulsa, bir cihaz akimin cogunu\\n"
       "cekse ya da termal kacis baslasa fark edilmeli.\\n\\n"
       "Ayni seri yolu paylasiyor: ATT_DATA/ATT_CLK ortak, PA_ADC_CS\\n"
       "ile seciliyor. Uc analog hat yerine bir sayisal secme hatti.",
       620, 400, 1.35)

# ---------------------------------------------------------------- kontrol
s.text("KONTROL ARAYUZU — A kartina", 420, 150, 1.8)
s.sym(HDR, "J31", "A kartina", 450, 200, fp=FHDR)
# A kartinin J66'siyla PIN PIN AYNI olmali (arayuz_kontrol.py denetliyor).
pairs = [("1", "+3V3"), ("2", "GND_HDR"), ("3", "ATT_DATA"), ("4", "GND_HDR"),
         ("5", "ATT_CLK"), ("6", "GND_HDR"), ("7", "PA_ATT_LE"), ("8", "GND_HDR"),
         ("9", "BIAS_CS1"), ("10", "GND_HDR"), ("11", "BIAS_CS2"),
         ("12", "GND_HDR"), ("13", "PA_ADC_CS"), ("14", "GND_HDR"),
         ("15", "PA_INHIBIT"), ("16", "GND_HDR"), ("17", "ADC_SDIO"),
         ("18", "GND_HDR"), ("19", "GND_HDR"), ("20", "GND_HDR")]
for p, net in pairs:
    s.pin_label(HDR, p, 450, 200, 0, net, "passive", d=7.62)

# C kartindan gelen yazmac zinciri
s.sym(HDR6, "J32", "C kartindan", 450, 285, fp=FHDR6)
for p_, net in [("1", "RLY_SER_OUT"), ("2", "RLY_SRCLK"), ("3", "RLY_RCLK"),
                ("4", "+3V3")]:
    s.pin_label(HDR6, p_, 450, 285, 0, net, "passive", d=10.16)
s.pin_power(HDR6, "5", 450, 285, 0, "GND", d=10.16)
s.pin_power(HDR6, "6", 450, 285, 0, "GND", d=15.24)

s.sym(R, "R690", "0R", 520, 258, rot=90, fp=FR)
s.pin_label(R, "1", 520, 258, 90, "GND_HDR", "passive")
s.pin_power(R, "2", 520, 258, 90, "GND")

s.text("** A KARTINDA YER YOK. **\\n"
       "Banka 0 ve 1 dolu (bkz 08_control). PA'nin istedigi 12 hat\\n"
       "icin uc secenek:\\n"
       "  1 C kartindaki kaydirmali yazmac zincirini uzat — PA'nin\\n"
       "    ayar hatlari zaten yavas, seri gitmesinde sakinca yok\\n"
       "  2 FLANGE_T, FWD_LOG, REV_LOG icin A kartina kucuk bir ADC\\n"
       "    (MCP3208 sinifi) ekle, SPI'i paylas\\n"
       "  3 rev B'de daha buyuk ECP5 (LFE5U-45F, ayni ayak izi)\\n\\n"
       "1 ve 2 birlikte A kartini DEGISTIRMEDEN cozuyor: uc analog\\n"
       "olcum ADC'ye, gerisi yazmac zincirine. Rev A'da bu yol\\n"
       "seciliyor; sema yerlesimden once guncellenecek.", 420, 275, 1.35)

s.write(os.path.join(HERE, "06_power.kicad_sch"))
print("06_power.kicad_sch yazildi")
