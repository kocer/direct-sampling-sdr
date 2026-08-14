#!/usr/bin/env python3
"""02_final: 4 x IRFP250N push-pull-paralel, geri beslemeli.
Kaynak: ../../PA_TASARIM.md §0 ve §1."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

Q = "Transistor_FET:Q_NMOS_GDS"
FQ = "Package_TO_SOT_THT:TO-247-3_Vertical"
T = "Device:Transformer_1P_1S"
# TRAFO AYAK IZI, BOBIN DEGIL. Once L_Toroid_T50_Vertical
# kullaniyordum: o 2 PEDLI bir bobin ayak izi. Trafo sembolunun
# 3. ve 4. bacaklari (ikincil) inecek bakir bulamadi ve sessizce
# yok oldu — final cikis trafosunun PA_OUT'u, kuplorlerin
# detektore giden ornegi, hepsi kopuktu.
FT = "dogrudan-sdr:XFMR_Toroid_4P_Vertical"
R, C, L = "Device:R", "Device:C", "Device:L"
FR = "Resistor_SMD:R_0603_1608Metric"
FRP = "Resistor_SMD:R_2512_6332Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
FCP = "Capacitor_SMD:C_1206_3216Metric"
FL = "dogrudan-sdr:L_Toroid_T50_Vertical"

s = Sheet("02_final", "Final kat", UU["02_final"],
          "IRFP250N x4 push-pull-paralel, 1.8-30 MHz duz 100 W", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{199 + nr[0]}"


s.text("FINAL KAT — 4 x IRFP250N, A sinifi push-pull-paralel", 16, 14, 2.2)
s.text("Verici 1.8-30 MHz (DAC 80 MSPS -> birinci Nyquist 40 MHz).\\n"
       "RF LDMOS'un parasi VHF/UHF kazancina gidiyor; bizim tavanimiz\\n"
       "30 MHz. HF'te dalga boyu 10-100 m, govde parazitikleri onemsiz —\\n"
       "siradan anahtarlama MOSFET'i gercekten calisiyor.\\n\\n"
       "4 x IRFP250N = $1.96.  2 x MRF300 = $250-400.  200 kat.\\n\\n"
       "DORT ADET ISI ICIN: her biri 58 W -> Tj = 70 + 58 x 0.65 = 108 C.\\n"
       "Iki adet olsa her biri 117 W -> Tj = 146 C, 150 sinirina yapisik.",
       16, 22, 1.35)

# ---------------------------------------------------------------- giris
s.text("GIRIS — 7:1 dusuren trafo + bastirma direnci", 16, 90, 1.8)
s.sym(T, "T10", "BN43-202 3:1", 70, 130, fp=FT)
s.pin_label(T, "1", 70, 130, 0, "DRV_OUT", "input", d=10.16)
s.pin_power(T, "2", 70, 130, 0, "GND", d=10.16)
s.pin_label(T, "3", 70, 130, 0, "GIN_A", "output", d=10.16)
s.pin_label(T, "4", 70, 130, 0, "GIN_B", "output", d=10.16)

for i, net in enumerate(("GIN_A", "GIN_B")):
    s.sym(R, cnt("R"), "1R", 115, 118 + i * 24, rot=90, fp=FRP)
    s.pin_label(R, "1", 115, 118 + i * 24, 90, net, "passive")
    s.pin_power(R, "2", 115, 118 + i * 24, 90, "GND")

s.text("BASTIRMA DIRENCI 1R: Ciss'in reaktansi 30 MHz'te 1.02 ohm.\\n"
       "Ayni mertebede direnc girisi frekanstan bagimsiz kiliyor, surucu\\n"
       "sabit yuk goruyor. Harcadigi 88 mW.\\n\\n"
       "Gecit salinimi sadece 0.42 V tepe: A sinifinda buyuk bir durgun\\n"
       "akimin etrafinda yuksek egimle modulasyon var (gm ~8 S kol basina),\\n"
       "kol basina 3.35 A tepe icin 0.42 V yetiyor. Anahtarlama modunun\\n"
       "5 V'luk gecit salinimi ile karistirilmamali.", 16, 175, 1.35)

# ---------------------------------------------------------------- cihazlar
s.text("CIHAZLAR — kol basina iki, paralel", 16, 235, 1.8)
for i in range(4):
    kol = "A" if i < 2 else "B"
    x = 55 + i * 60
    y = 285
    s.sym(Q, f"Q{10 + i}", "IRFP250N", x, y, fp=FQ)
    # her gecide AYRI seri direnc: parazit osilasyon sondurme
    s.sym(R, cnt("R"), "10R", x - 22, y, rot=90, fp=FR)
    s.pin_label(R, "1", x - 22, y, 90, f"GIN_{kol}", "passive")
    s.pin_label(R, "2", x - 22, y, 90, f"G{10 + i}", "passive")
    s.pin_label(Q, "1", x, y, 0, f"G{10 + i}", "input", d=7.62)
    # bias servosu gecidi suruyor (03_bias)
    s.sym(R, cnt("R"), "1k", x - 22, y + 26, rot=90, fp=FR)
    s.pin_label(R, "1", x - 22, y + 26, 90, f"GATE{i + 1}", "input")
    s.pin_label(R, "2", x - 22, y + 26, 90, f"G{10 + i}", "passive")
    s.pin_label(Q, "2", x, y, 0, f"DRN_{kol}", "passive", d=7.62)
    s.pin_label(Q, "3", x, y, 0, f"SRC{i + 1}", "passive", d=12.7)

s.text("HER GECIDE AYRI 10R: paralel MOSFET'ler arasinda parazit\\n"
       "osilasyon olur; seri direnc Q'yu dusurup sonduruyor. Bunu atlayan\\n"
       "her tasarim 100+ MHz'te osilasyon yasar.\\n\\n"
       "GATE1..4 03_bias'tan geliyor, her cihaza AYRI servo. SRC1..4\\n"
       "olcu direnclerine gidiyor — akim paylasimi cihaz basina olculuyor.",
       16, 325, 1.35)

# ---------------------------------------------------------------- cikis
s.text("CIKIS — 1:4 yukselten trafo", 300, 235, 1.8)
s.sym(T, "T11", "BN43-3312 2:4", 350, 285, fp=FT)
s.pin_label(T, "1", 350, 285, 0, "DRN_A", "input", d=10.16)
s.pin_label(T, "2", 350, 285, 0, "DRN_B", "input", d=10.16)
s.pin_label(T, "3", 350, 285, 0, "PA_OUT", "output", d=10.16)
s.pin_power(T, "4", 350, 285, 0, "GND", d=10.16)

# besleme: orta uctan, RF bogucu ile
s.sym(L, "L10", "10uH bogucu", 350, 250, rot=90, fp=FL)
s.pin_label(L, "1", 350, 250, 90, "+50V", "input")
s.pin_label(L, "2", 350, 250, 90, "DRN_CT", "passive")
for i, v in enumerate(("100nF", "1uF", "100uF")):
    s.sym(C, cnt("C"), v, 400 + i * 20, 250, rot=90, fp=FCP)
    s.pin_label(C, "1", 400 + i * 20, 250, 90, "DRN_CT", "passive")
    s.pin_power(C, "2", 400 + i * 20, 250, 90, "GND")

# ---------------------------------------------------------------- geri besleme
s.text("GERI BESLEME — 1.8-30 MHz duz kazancin sirri", 300, 90, 1.8)
for i, kol in enumerate(("A", "B")):
    x = 340 + i * 90
    s.sym(R, cnt("R"), "820R", x, 130, rot=90, fp=FRP)
    s.pin_label(R, "1", x, 130, 90, f"DRN_{kol}", "passive")
    s.pin_label(R, "2", x, 130, 90, f"FB_{kol}", "passive")
    s.sym(C, cnt("C"), "1nF", x, 152, rot=90, fp=FCP)
    s.pin_label(C, "1", x, 152, 90, f"FB_{kol}", "passive")
    s.pin_label(C, "2", x, 152, 90, f"GIN_{kol}", "passive")

s.text("Drainden gecide RC negatif geri besleme. Kazanc artik CIHAZIN\\n"
       "gm'i ile degil GERI BESLEME AGI ile belirleniyor: cihaz kazanci\\n"
       "frekansla duserken geri besleme orani sabit kaldigi icin toplam\\n"
       "kazanc duz cikiyor.\\n\\n"
       "Motorola AN758/EB104 bu sekilde 2-30 MHz duz calisir.\\n"
       "30 MHz'te 14 dB hedefleyip alcak bantlardaki fazlayi geri\\n"
       "beslemeyle asagi cekiyoruz.\\n\\n"
       "Seri kondansator DC'yi bloklar: gecit bias'i servodan geliyor,\\n"
       "geri besleme onu bozmamali.\\n\\n"
       "820R / 1nF baslangic degeri. Bringup'ta bant bant kazanc olculup\\n"
       "duzlenecek — bu iki parca ayarlanacak tek yer.", 300, 155, 1.35)

s.text("SARIMLAR — manyetik_hesap.py\\n"
       "T11 cikis: BN43-3312, birincil 2 sarim ORTA UCLU, ikincil 4.\\n"
       "  R_dd = Vcc^2/(2*Pout) = 12.5 ohm, yuk 50 -> 1:4 empedans.\\n"
       "  Sarim sayisi iki sarttan buyugu: endüktans (0.9) ve DOYMA (1.4).\\n"
       "  2 sarimda B = 34.6 mT, ferrit-43'un 50 mT sinirinin altinda.\\n"
       "  Birincil akim 2.8 A rms -> AWG 18.\\n"
       "  IKI YARIM SARIM SIMETRIK: asimetri cift harmonik iptalini\\n"
       "  bozar, push-pull'un tek kazandirdigi sey o.\\n\\n"
       "T10 giris: BN43-202, birincil 3 sarim, ikincil 1.\\n"
       "  50 ohm -> 1 ohm (bastirma direnciyle ayarlanan gecit yuku).\\n\\n"
       "BESLEME ORTA UCTAN, RF BOGUCU UZERINDEN\\n"
       "10uH bogucu 1.8 MHz'te 113 ohm, RF'i besleme hattina kacirmiyor.\\n"
       "Uc kademe ayristirma: 100nF (yuksek frekans), 1uF (orta),\\n"
       "100uF (modulasyon zarfi). A sinifinda DC cekisi sabit oldugu icin\\n"
       "zarf akimi kucuk, ama tepe akim 6.7 A — 100uF'i dusuk ESR sec.",
       300, 320, 1.35)

s.write(os.path.join(HERE, "02_final.kicad_sch"))
print("02_final.kicad_sch yazildi")
