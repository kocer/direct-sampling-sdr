#!/usr/bin/env python3
"""04_atten: PE4312 x4, ortak seri yol, ayri LE. Kaynak: ../NETLIST_C.md §4."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

A = "dogrudan-sdr:PE4312"
# ACIK PED 2.6 -> 2.1 mm. Veri sayfasi (DOC-81482, Sekil 26) cipin
# alt tarafindaki acik pedi 2.15 +-0.05 mm kare veriyor, onerilen
# lehim alani 2.20 mm. Secili KiCad ayak izinde 2.6 mm vardi: her
# kenarda 0.2 mm fazla bakir. Ped sayisi tuttugu icin hicbir denetim
# goremiyor — ped_denetim de, DRC de sessiz.
#
# Iki somut bedeli var: (1) acik ped kenari ile en yakin sinyal
# pedinin ic kenari arasindaki bosluk 0.4 mm yerine 0.2 mm'ye
# duşuyor, yani maske koprusu uretim sinirinda; (2) 2.6 mm'lik
# ped icin kesilen macun sablonu cipin gercek pedinden %46 fazla
# lehim koyuyor, cip macunun uzerinde yuzup kayabiliyor.
#
# TQFN-20-1EP...EP2.1x2.1: 2.1 mm, yani nominalin 0.05 mm altinda
# ve onerilen alanin guvenli tarafinda.
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
# dokumu var, yani ped dokume oturuyor. PE4312 3.3 V'ta 130 uA cekiyor, yani 0.43 mW — 100 W'lik bir
# final katinda termal via anlamli, 0.43 mW'lik bir zayiflaticida degil.
# Dokumun ulasamadigi yere kisa toprak sapi gerekirse onu
# yonlendirmeden SONRA dikis.py ekliyor — sabit izgarali footprint
# via'sindan daha esnek.
FA = "Package_DFN_QFN:TQFN-20-1EP_4x4mm_P0.5mm_EP2.1x2.1mm"
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
    # PIN 3'E SERI 10k — VERI SAYFASI SARTI, SUSLEME DEGIL.
    # DOC-81482 s.5, "Resistors on pins 1 and 3":
    #   "A 10-kohm resistor on the inputs to pin 1 and 3 eliminates
    #    the package resonance between the RF input pin and the two
    #    digital inputs. The specified attenuation error versus
    #    frequency performance depends upon this condition."
    # Yani bu direnc olmadan veri sayfasindaki zayiflatma dogrulugu
    # GECERLI DEGIL. Pin 1'de (C16) zaten 10k var — asagidaki acilis
    # cekme direnci ayni isi goruyor ve pin 1'in tek disariya baglantisi
    # o. Pin 3 dogrudan A kartinin hattina bagliydi.
    # Zamanlama: 10k x ~5 pF = 50 ns; veri sayfasi tCLK azami 10 MHz
    # (100 ns) ve tSDSUP 10 ns istiyor. Ureticinin kendi degerlendirme
    # karti da (Sekil 24) Data ve Clock'a 10k koyuyor.
    s.sym(R, cnt("R"), "10k", x - 25, y, rot=90, fp=FR)
    s.pin_label(R, "1", x - 25, y, 90, "ATT_DATA", "input")
    s.pin_label(R, "2", x - 25, y, 90, f"ATT{n}_DAT", "passive")
    s.pin_label(A, "3", x, y, 0, f"ATT{n}_DAT", "input", d=7.62)
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
    # ACIK PED "21", "Pad" DEGIL.
    # Sembol acik pedi "Pad" diye adlandiriyordu, ayak izi (QFN-20-1EP)
    # "21" diyor. Ad tutmayinca GND hicbir yere gitmiyordu ve ped 21
    # kartta agsiz kaliyordu — bes PE4312'nin hepsinde. Acik ped
    # zayiflaticinin toprak referansi; bosta kalirsa zayiflatma
    # degerleri tutmaz ve RF yolu kararsizlasir.
    for p in ("10", "11", "18", "21"):
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
