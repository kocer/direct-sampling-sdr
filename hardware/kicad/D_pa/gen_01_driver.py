#!/usr/bin/env python3
"""01_driver: surucu katlari. Kaynak: ../../PA_TASARIM.md §1."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

A = "dogrudan-sdr:PE4312"
# ACIK PED 2.6 -> 2.1 mm — bkz. C_rf/gen_04_atten.py, ayni gerekce:
# veri sayfasi (DOC-81482 Sekil 26) acik pedi 2.15 +-0.05 mm kare
# veriyor, onerilen lehim alani 2.20 mm. 2.6 mm her kenarda 0.2 mm
# fazla bakir birakiyordu.
# TERMAL VIA'LAR KALDIRILDI — OLCULDU, GEREKMIYOR VE ZARARLI.
# KiCad'in "_ThermalVias" surumu acik pedin icine DELIKLI (PTH) via
# koyuyor. Olculen sonuc: bu via'lar ile komsu sinyal pedi arasindaki
# bosluk 0.201 mm. Yonlendirici DSN sinif kurallarinda guc aglarini
# 300 um'de tutuyor, yani bu ciftler HER TURDA ihlal sayiliyor ve
# ihlal geometriden geldigi icin COZULEMIYOR: D kartinin
# yonlendirme gunlugunde ihlal sayisi turdan tura sabit
# (152, 152, 152) kalirken yonlendirilmemis ag sayisi duşuyor.
#
# Via'lar zaten gerekmiyor: acik ped GND'ye bagli ve F.Cu'da GND
# dokumu var, yani ped dokume oturuyor. PE4312 0.43 mW harciyor.
# Dokumun ulasamadigi yere kisa toprak sapi gerekirse onu
# yonlendirmeden SONRA dikis.py ekliyor — sabit izgarali footprint
# via'sindan daha esnek.
FA = "Package_DFN_QFN:TQFN-20-1EP_4x4mm_P0.5mm_EP2.1x2.1mm"
G = "dogrudan-sdr:PGA-103"
FG = "Package_TO_SOT_SMD:SOT-89-3"
Q = "Transistor_FET:Q_NMOS_GDS"
FQ = "Package_TO_SOT_THT:TO-220-3_Vertical"
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
FL = "Inductor_SMD:L_0805_2012Metric"
CONN = "Connector:Conn_Coaxial"
FSMA = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"

s = Sheet("01_driver", "Surucu katlari", UU["01_driver"],
          "PE4312 + PGA-103+ + IRF530N cifti", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{99 + nr[0]}"


s.text("SURUCU KATLARI — +0.5 dBm'den +39 dBm'e", 16, 14, 2.2)
s.text("AD9767 cikisi              +0.5 dBm\\n"
       "PE4312 zayiflatici        -1.5 .. -15 dB   ince seviye ayari\\n"
       "PGA-103+                  +22 dB\\n"
       "IRF530N cifti             +18 dB\\n"
       "                          ---------\\n"
       "final girisine            +39 dBm (8 W)\\n\\n"
       "ZAYIFLATICI DAC'IN ONUNDE DEGIL, BURADA. DAC tam olcege yakin\\n"
       "calisirsa SFDR'i en iyi; seviyeyi sayisal kismak bit kaybettirir.\\n"
       "Analog tarafta kismak DAC'i tam olcekte tutuyor.", 16, 22, 1.35)

# ---------------------------------------------------------------- giris
s.sym(CONN, "J10", "A kartindan TX1", 45, 95, fp=FSMA)
s.pin_label(CONN, "1", 45, 95, 0, "TX_IN", "input")
s.pin_power(CONN, "2", 45, 95, 0, "GND")

# ---------------------------------------------------------------- zayiflatici
s.text("SEVIYE AYARI — PE4312", 16, 120, 1.8)
s.sym(A, "U10", "PE4312C-Z", 80, 165, fp=FA)
s.pin_label(A, "2", 80, 165, 0, "TX_IN", "passive", d=7.62)
s.pin_label(A, "14", 80, 165, 0, "ATT_OUT", "passive", d=12.7)
# PIN 3'E SERI 10k — veri sayfasi s.5 "Resistors on pins 1 and 3".
# Bu direnc olmadan veri sayfasindaki zayiflatma dogrulugu gecerli
# degil (RF giris pini ile iki dijital giris arasindaki paket
# rezonansini kiriyor). Pin 1'de acilis cekme direnci zaten var.
s.sym(R, "R99", "10k", 45, 165, rot=90, fp=FR)
s.pin_label(R, "1", 45, 165, 90, "ATT_DATA", "input")
s.pin_label(R, "2", 45, 165, 90, "ATT_DAT_Q", "passive")
s.pin_label(A, "3", 80, 165, 0, "ATT_DAT_Q", "input", d=17.78)
s.pin_label(A, "4", 80, 165, 0, "ATT_CLK", "input", d=22.86)
s.pin_label(A, "5", 80, 165, 0, "PA_ATT_LE", "input", d=27.94)
s.pin_label(A, "13", 80, 165, 0, "+3V3", "input", d=33.02)     # P/S seri
s.pin_power(A, "7", 80, 165, 0, "GND", d=38.1)
s.pin_power(A, "8", 80, 165, 0, "GND", d=43.18)
for p in ("6", "9"):
    s.pin_label(A, p, 80, 165, 0, "+3V3", "input", d=5.08)
# ACIK PED "21", "Pad" DEGIL — bkz. C_rf/gen_04_atten.py
for p in ("10", "11", "18", "21"):
    s.pin_power(A, p, 80, 165, 0, "GND", d=5.08)
s.pin_power(A, "12", 80, 165, 0, "GND", d=10.16)
# alti C bacagi yukari: acilista 31.5 dB, EN SAGIR
for i, p in enumerate(("1", "15", "16", "17", "19", "20")):
    rx, ry = 155, 135 + i * 12
    s.sym(R, cnt("R"), "10k", rx, ry, rot=90, fp=FR)
    s.pin_label(R, "1", rx, ry, 90, "+3V3", "input")
    s.pin_label(R, "2", rx, ry, 90, f"PA_C{i}", "passive")
    s.pin_label(A, p, 80, 165, 0, f"PA_C{i}", "input", d=7.62)

# PE4312 BESLEME AYIRMA — D KARTINDA HIC YOKTU.
# C kartinda dort zayiflaticinin her birine iki adet 100nF konmus;
# D'deki tek zayiflatici (U10) atlanmis. Iki VDD bacagi var (6 ve 9),
# her birine bir tane. Cipin icinde negatif gerilim ureteci calisiyor
# (pin 12 topraga bagli, normal mod) ve o pompa besleme rayina
# anahtarlama gurultusu biniyor — ayirma kondansatoru bu yuzden
# yalnizca "iyi uygulama" degil, cipin kendi gurultusunu kendi
# rayinda tutmanin yolu.
for i, cy in enumerate((140, 156)):
    s.sym(C, "C11%d" % i, "100nF", 230, cy, rot=90, fp=FC)
    s.pin_label(C, "1", 230, cy, 90, "+3V3", "input")
    s.pin_power(C, "2", 230, cy, 90, "GND")

s.text("ACILISTA 31.5 dB — EN COK ZAYIFLATMA.\\n"
       "Veri sayfasi s.6: seri modda bile acilis durumunu C0.5-C16\\n"
       "bacaklarindaki seviye belirliyor. Altisi da yukari = 31.5 dB.\\n"
       "PA acilista en sagir halinde; firmware kademeyi yazana kadar\\n"
       "final surulmuyor. Tersi 0 dB demekti — acilista tam guc.",
       16, 215, 1.35)

# ---------------------------------------------------------------- surucu 1
s.text("SURUCU 1 — PGA-103+, +22 dB", 300, 120, 1.8)
s.sym(C, "C10", "100nF", 330, 150, fp=FC)
s.pin_label(C, "1", 330, 150, 0, "ATT_OUT", "passive")
s.pin_label(C, "2", 330, 150, 0, "D1_IN", "passive")
s.sym(G, "U11", "PGA-103+", 375, 150, fp=FG)
s.pin_label(G, "1", 375, 150, 0, "D1_IN", "input", d=7.62)
s.pin_label(G, "3", 375, 150, 0, "D1_OUT", "output", d=7.62)
s.pin_power(G, "2", 375, 150, 0, "GND", d=5.08)
s.pin_power(G, "4", 375, 150, 0, "GND", d=10.16)
# bias tee: besleme RF cikisindan
s.sym(L, "L10", "1uH bogucu", 420, 130, rot=90, fp=FL)
s.pin_label(L, "1", 420, 130, 90, "D1_OUT", "passive")
s.pin_label(L, "2", 420, 130, 90, "PGA_BIAS", "passive")
s.sym(R, "R10", "56R 1W", 445, 130, rot=90, fp=FRP)
s.pin_label(R, "1", 445, 130, 90, "DRV_EN_LO", "input")
s.pin_label(R, "2", 445, 130, 90, "PGA_BIAS", "passive")
s.sym(C, "C11", "100nF", 468, 130, rot=90, fp=FC)
s.pin_label(C, "1", 468, 130, 90, "PGA_BIAS", "passive")
s.pin_power(C, "2", 468, 130, 90, "GND")
s.sym(C, "C12", "100nF", 420, 170, fp=FC)
s.pin_label(C, "1", 420, 170, 0, "D1_OUT", "passive")
s.pin_label(C, "2", 420, 170, 0, "D2_IN", "passive")

s.text("PGA-103+ BESLEMESI PA_INHIBIT ILE KESILIYOR.\n"
       "56R'nin ust ucu +5V'a degil DRV_EN_LO'ya bagli (06_power'daki\n"
       "MOSFET). FPGA kalkmadan, SWR korumasi attiginda ya da flans\n"
       "sicakligi asildiginda surucu beslemesiz kalir ve final surulmez.\n"
       "Kesme donanimda; yazilimin dogru davranmasina guvenmiyoruz.\n\n"
       "PGA-103+ beslemesi RF CIKISINDAN (bias tee): 3 numarali bacak\\n"
       "hem RF cikisi hem DC girisi. Bogucu RF'i besleme hattina\\n"
       "kacirmiyor, 56R akimi sinirliyor (5V - 5V cihaz dususu).\\n"
       "Pin 3'te azami DC 6 V — veri sayfasi s.2.", 300, 190, 1.35)

# ---------------------------------------------------------------- surucu 2
s.text("SURUCU 2 — IRF530N cifti, +18 dB, ~8 W", 300, 235, 1.8)
s.sym(T, "T10", "BN43-202 2:1", 330, 285, fp=FT)
s.pin_label(T, "1", 330, 285, 0, "D2_IN", "input", d=10.16)
s.pin_power(T, "2", 330, 285, 0, "GND", d=10.16)
s.pin_label(T, "3", 330, 285, 0, "D2_GA", "output", d=10.16)
s.pin_label(T, "4", 330, 285, 0, "D2_GB", "output", d=10.16)

for i, kol in enumerate(("A", "B")):
    x = 385 + i * 55
    s.sym(Q, f"Q{20 + i}", "IRF530N", x, 290, fp=FQ)
    s.sym(R, cnt("R"), "10R", x - 22, 290, rot=90, fp=FR)
    s.pin_label(R, "1", x - 22, 290, 90, f"D2_G{kol}", "passive")
    s.pin_label(R, "2", x - 22, 290, 90, f"D2_G{kol}_S", "passive")
    s.pin_label(Q, "1", x, 290, 0, f"D2_G{kol}_S", "input", d=7.62)
    s.pin_label(Q, "2", x, 290, 0, f"D2_D{kol}", "passive", d=7.62)
    s.pin_power(Q, "3", x, 290, 0, "GND", d=12.7)
    # sabit bias: bu kat AB, servo yok
    s.sym(R, cnt("R"), "10k", x - 22, 316, rot=90, fp=FR)
    s.pin_label(R, "1", x - 22, 316, 90, "D2_BIAS", "input")
    s.pin_label(R, "2", x - 22, 316, 90, f"D2_G{kol}_S", "passive")

# T12, T11 DEGIL. Surucu cikis trafosunu da T11 diye adlandirmistim
# ama final cikis trafosu (gen_02_final) zaten T11. KiCad ikisini TEK
# parcada birlestirdi, biri netlistten tamamen dustu ve PA_OUT
# beslenmeden kaldi. Referans cakismasi ERC'de gorunmuyor cunku
# sayfalar ayri; ayni ada iki farkli parca koymak serbest.
# ** ORTA UC BAGLI DEGILDI — SURUCU KATININ 12 V'U DA ULASMIYORDU. **
# Ayni hata final katindakiyle ayni (bkz. gen_02_final T31):
# D2_CT = {L11.2, C110.1}, yani bogucu ile kondansator birbirine
# bagli, trafoya degil. Q20/Q21'in drainlerinde DC besleme yoktu.
# Birincili orta uclu 5 bacakli trafo kullaniliyor.
TCT = "dogrudan-sdr:XFMR_CT"
FTCT = "dogrudan-sdr:XFMR_Toroid_5P_Vertical"
s.sym(TCT, "T12", "BN43-202 2:3 CT", 500, 285, fp=FTCT)
s.pin_label(TCT, "1", 500, 285, 0, "D2_DA", "input", d=10.16)
s.pin_label(TCT, "2", 500, 285, 0, "D2_DB", "input", d=10.16)
s.pin_label(TCT, "5", 500, 285, 0, "D2_CT", "input", d=15.24)
s.pin_label(TCT, "3", 500, 285, 0, "DRV_OUT", "output", d=10.16)
s.pin_power(TCT, "4", 500, 285, 0, "GND", d=10.16)
s.sym(L, "L11", "10uH bogucu", 500, 250, rot=90, fp=FL)
s.pin_label(L, "1", 500, 250, 90, "+12V", "input")
s.pin_label(L, "2", 500, 250, 90, "D2_CT", "passive")
# 12 V rayinda 10uF 0603'e sigmiyor: 0603'te 10uF en fazla
# 16 V sinifinda ve DC bias kaybiyla 12 V'ta yarisindan azi
# kaliyor. 1206 / 25 V.
s.sym(C, cnt("C"), "10uF", 528, 250, rot=90,
      fp="Capacitor_SMD:C_1206_3216Metric")
s.pin_label(C, "1", 528, 250, 90, "D2_CT", "passive")
s.pin_power(C, "2", 528, 250, 90, "GND")

s.text("SURUCU 2 AB SINIFI, A degil. Bu kat 8 W veriyor; A sinifinda\\n"
       "27 W isi ederdi ve hicbir sey kazandirmazdi — doğrusalligi\\n"
       "belirleyen FINAL kat. Sabit bias, servo yok.\\n\\n"
       "12 V besleme: 8 W icin 50 V gereksiz, LM5164 ile 50 V'tan\\n"
       "uretiliyor (06_power). (Once burada '24 V' yaziyordu; 24 V\\n"
       "rayi guc agacindan kalkti, metin bayat kalmisti.)\\n\\n"
       "IRF530N Ciss 920 pF — IRFP250N'in ucte biri, surulmesi kolay.",
       300, 330, 1.35)

# ** Q20/Q21 SOGUTUCU GEREKTIRIYOR — OLCUM **
#
#   ray butcesi (06_power):  12 V x 1.0 A = 12 W giris
#   bu katin cikisi                       =  8 W RF
#   ISIYA DONEN                           =  4 W, cihaz basina 2 W
#
#   TO-220, sogutucusuz, dik montaj:  Rth(j-a) ~62 C/W
#       dT = 2 W x 62 = 124 C
#   25 C oda sicakliginda Tj = 149 C. AMA bu kart 233 W dagitan bir
#   final katiyla ayni kutunun icinde: kutu ici 50-60 C. O zaman
#       Tj = 174 .. 184 C
#   IRF530N'in Tj(max) degeri 175 C. Yani cihaz sinirin TAM USTUNDE
#   ya da otesinde calisiyor — omru saatlerle olculur.
#
#   COZUM (mekanik, semada degil): Q20/Q21 finallerin bagli oldugu
#   AYNI bakir flansa vidalanacak. Kucuk bir kanatcik bile yetiyor:
#       Rth(s-a) 20 C/W ile  dT = 2 x (1.5 + 0.5 + 20) = 44 C
#       Tj = 55 + 44 = 99 C  — genis marj.
#   Kartta ayak izi TO-220 dik; kulak zaten flansa bakiyor,
#   yerlesimde final koridorunun kenarinda duruyorlar.
#
#   NOT: Q30 (ters polarite) ayni hastaliktaydi ve cok daha
#   agirdi (5.2 W, 322 C). O ideal diyot + IRFB4110 ile cozuldu
#   (06_power); burada cozum sogutucu, cunku kayip RF'in kendisi
#   degil, katin isi butcesi.
s.text("** Q20/Q21 SOGUTUCUSUZ CALISMAZ **\\n"
       "12 W giris - 8 W RF = 4 W isi, cihaz basina 2 W.\\n"
       "Sogutucusuz TO-220: Rth(j-a) 62 C/W -> 124 C artis.\\n"
       "Kutu ici 55 C ile Tj ~180 C; IRF530N siniri 175 C.\\n"
       "Ikisi de finallerin flansina vidalanacak: 20 C/W'lik bir\\n"
       "kanatcikla Tj ~99 C'ye iniyor.", 300, 365, 1.35)

s.write(os.path.join(HERE, "01_driver.kicad_sch"))
print("01_driver.kicad_sch yazildi")
