#!/usr/bin/env python3
"""REFERANS ARALIGI — BU DOSYA: RS1-RS4, U20-U29 (DAC),
U31-U39 (INA240 akim olcum), U41-U49 (LM358 integrator).
Aralik listesinin tamami gen_02_final.py basinda.

03_bias: A sinifi bias servosu, cihaz basina bir tane.
Kaynak: ../../PA_TASARIM.md §2 ve §3."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

INA = "dogrudan-sdr:INA240A1"
FINA = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
OPA = "Amplifier_Operational:LM358"
FOPA = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
DAC = "Analog_DAC:MCP4922"
FDAC = "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm"
R, C = "Device:R", "Device:C"
FR = "Resistor_SMD:R_0603_1608Metric"
FRS = "Resistor_SMD:R_2512_6332Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"

s = Sheet("03_bias", "Bias servosu", UU["03_bias"],
          "INA240 + integrator x4, MCP4922 kurulum DAC'i", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{299 + nr[0]}"


s.text("BIAS SERVOSU — tasarimin kalbi", 16, 14, 2.2)
s.text("'AYARLI A SINIFI' demek, bias'in guc kademesiyle BIRLIKTE degismesi\\n"
       "demek. A sinifinda DC cekisi sabittir, cikis gucune bakmaz: bias'i\\n"
       "100 W icin kurup 5 W verirsen yine 333 W yakarsin.\\n\\n"
       "  ayar    Idq @50 V     DC      isi\\n"
       "   5 W      0.33 A     17 W    12 W\\n"
       "  10 W      0.67 A     33 W    23 W\\n"
       "  25 W      1.67 A     83 W    58 W\\n"
       "  50 W      3.33 A    167 W   117 W\\n"
       "  75 W      5.00 A    250 W   175 W\\n"
       " 100 W      6.67 A    333 W   233 W        Idq = Pout / (0.3 x Vcc)\\n\\n"
       "NEDEN KAPALI CEVRIM: MOSFET'in gecit gerilimi-akim iliskisi\\n"
       "sicaklikla ciddi kayar. Sabit gecit gerilimi verirsen isindikca\\n"
       "akim kacar, A sinifi bozulur, en kotu halde termal kacis olur.\\n"
       "Akimi olcup geri besleyince sicaklik telafisi BEDAVA geliyor.",
       16, 22, 1.35)

# ---------------------------------------------------------------- kurulum DAC'i
s.text("KURULUM DAC'i — ORTAK SERI YOLDAN", 16, 130, 1.8)
for i in range(2):
    x = 60 + i * 120
    s.sym(DAC, f"U{20 + i}", "MCP4922-E/SL", x, 165, fp=FDAC)
    s.pin_label(DAC, "4", x, 165, 0, "ATT_CLK", "input", d=7.62)
    s.pin_label(DAC, "5", x, 165, 0, "ATT_DATA", "input", d=12.7)
    s.pin_label(DAC, "3", x, 165, 0, f"BIAS_CS{i + 1}", "input", d=17.78)
    s.pin_label(DAC, "8", x, 165, 0, "+3V3", "input", d=22.86)    # ~LDAC
    s.pin_label(DAC, "9", x, 165, 0, "+3V3", "input", d=27.94)    # ~SHDN
    s.pin_label(DAC, "1", x, 165, 0, "+3V3", "input", d=5.08)     # VDD
    s.pin_power(DAC, "12", x, 165, 0, "GND", d=5.08)              # VSS
    s.pin_label(DAC, "13", x, 165, 0, "+3V3", "input", d=33.02)   # VrefA
    s.pin_label(DAC, "11", x, 165, 0, "+3V3", "input", d=38.1)    # VrefB
    s.pin_label(DAC, "14", x, 165, 0, f"VSET{2 * i + 1}", "output", d=7.62)
    s.pin_label(DAC, "10", x, 165, 0, f"VSET{2 * i + 2}", "output", d=12.7)
    for pn in ("2", "6", "7"):
        s.nc(*s.P(DAC, pn, x, 165))
    s.sym(C, cnt("C"), "100nF", x + 45, 165, rot=90, fp=FC)
    s.pin_label(C, "1", x + 45, 165, 90, "+3V3", "input")
    s.pin_power(C, "2", x + 45, 165, 90, "GND")

s.text("Iki cift DAC = dort kanal, cihaz basina bir kurulum gerilimi.\\n"
       "12 bit, referans +3V3 -> adim 0.8 mV. Idq 0.33-6.67 A araliginda\\n"
       "olcu direncinin cikisina cevrildiginde cozunurluk fazlasiyla yeter.",
       16, 205, 1.35)

# ---------------------------------------------------------------- servo x4
s.text("SERVO — CIHAZ BASINA BIR TANE", 16, 235, 1.8)


def servo(n, x, y):
    """Bir cihazin bias servosu: olcu direnci -> INA240 -> integrator -> gecit."""
    # olcu direnci, kaynak bacaginda
    s.sym(R, f"RS{n}", "0.01R 2W", x, y, rot=90, fp=FRS)
    s.pin_label(R, "1", x, y, 90, f"SRC{n}", "passive")
    s.pin_power(R, "2", x, y, 90, "GND")

    s.sym(INA, f"U{30 + n}", "INA240A1DR", x + 45, y, fp=FINA)
    s.pin_label(INA, "8", x + 45, y, 0, f"SRC{n}", "input", d=7.62)
    s.pin_power(INA, "1", x + 45, y, 0, "GND", d=12.7)
    s.pin_power(INA, "7", x + 45, y, 0, "GND", d=17.78)    # REF1
    s.pin_power(INA, "3", x + 45, y, 0, "GND", d=22.86)    # REF2
    s.pin_label(INA, "5", x + 45, y, 0, f"IMEAS{n}", "output", d=7.62)
    s.pin_label(INA, "6", x + 45, y, 0, "+5V", "input", d=5.08)
    s.pin_power(INA, "2", x + 45, y, 0, "GND", d=5.08)
    s.nc(*s.P(INA, "4", x + 45, y))

    # hata integratoru: VSET ile IMEAS'i karsilastir, gecidi sur
    # LM358 iki birimli: dort servo icin IKI paket. Birimi bos
    # birakirsak KiCad "missing_unit" diyor ve gercekten de bosta
    # kalan op-amp girisi salinim yapar.
    pkg, unit = (41, 1) if n <= 2 else (42, 1)
    if n % 2 == 0:
        unit = 2
    pkg = 41 if n <= 2 else 42
    pins3 = {1: ("3", "2", "1"), 2: ("5", "6", "7")}[unit]
    s.sym(OPA, f"U{pkg}", "LM358", x + 95, y, fp=FOPA, unit=unit)
    s.pin_label(OPA, pins3[0], x + 95, y, 0, f"VSET{n}", "input", d=12.7)
    s.pin_label(OPA, pins3[1], x + 95, y, 0, f"IFB{n}", "input", d=7.62)
    s.pin_label(OPA, pins3[2], x + 95, y, 0, f"VG{n}", "output", d=7.62)
    if unit == 1:
        s.sym(OPA, f"U{pkg}", "LM358", x + 95, y, fp=FOPA, unit=3)
        s.pin_label(OPA, "8", x + 95, y, 0, "+12V", "input", d=7.62)
        s.pin_power(OPA, "4", x + 95, y, 0, "GND", d=7.62)
    s.sym(R, cnt("R"), "10k", x + 95, y + 22, rot=90, fp=FR)
    s.pin_label(R, "1", x + 95, y + 22, 90, f"IMEAS{n}", "passive")
    s.pin_label(R, "2", x + 95, y + 22, 90, f"IFB{n}", "passive")
    s.sym(C, cnt("C"), "1uF", x + 118, y + 22, rot=90, fp=FC)
    s.pin_label(C, "1", x + 118, y + 22, 90, f"IFB{n}", "passive")
    s.pin_label(C, "2", x + 118, y + 22, 90, f"VG{n}", "passive")

    # gecit surme: seri direnc + asagi cekme (guvenli varsayilan)
    s.sym(R, cnt("R"), "100R", x + 150, y, rot=90, fp=FR)
    s.pin_label(R, "1", x + 150, y, 90, f"VG{n}", "passive")
    s.pin_label(R, "2", x + 150, y, 90, f"GATE{n}", "output")
    s.sym(R, cnt("R"), "10k", x + 172, y, rot=90, fp=FR)
    s.pin_label(R, "1", x + 172, y, 90, f"GATE{n}", "passive")
    s.pin_power(R, "2", x + 172, y, 90, "GND")


for i in range(4):
    servo(i + 1, 40, 265 + i * 40)

s.text("OLCU DIRENCI 0.01R kaynak bacaginda. 6.67 A / 4 cihaz = 1.67 A\\n"
       "cihaz basina -> 16.7 mV dusum, INA240 x20 kazancla 334 mV.\\n"
       "Direncte harcanan 28 mW; 2512 govde rahat.\\n\\n"
       "INTEGRATOR: hata sifirlanana kadar gecidi surer. RC = 10k x 1uF\\n"
       "= 10 ms, bias donguSU RF'ten cok yavas — modulasyonu takip etmez,\\n"
       "sadece calisma noktasini tutar. Daha hizli olsaydi sinyalin\\n"
       "kendisini bastirir, kazanci bozardi.\\n\\n"
       "GECIDIN ASAGI CEKMESI (10k) GUVENLIK: FPGA kalkmadan, DAC\\n"
       "yazilmadan ya da op-amp beslemesi yokken gecit toprakta, cihaz\\n"
       "kapali. Bias asla 'varsayilan olarak acik' olmamali.\\n\\n"
       "HER CIHAZA AYRI SERVO: paralel MOSFET'lerde esiklerin farki akim\\n"
       "paylasimini bozar, biri akimin cogunu ceker ve olur. Dort ayri\\n"
       "servo her cihazi kendi 1.67 A'sinde tutuyor.", 250, 265, 1.35)

s.write(os.path.join(HERE, "03_bias.kicad_sch"))
print("03_bias.kicad_sch yazildi")
