#!/usr/bin/env python3
"""01_power sayfasini uretir. Kaynak: ../NETLIST.md §1 ve §9."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

R, C, L = "Device:R", "Device:C", "Device:L"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
# 10uF/25V 0603'te YOK: 0603'te 25 V sinifinda tavan 2.2 uF
# (kondansator_denetim.py tablosu). 18 V'a kadar cikan VIN_PROT
# rayinda 25 V sinifi asgari, o yuzden 1206.
FC1206 = "Capacitor_SMD:C_1206_3216Metric"
FC0805 = "Capacitor_SMD:C_0805_2012Metric"
FL = "Inductor_SMD:L_Taiyo-Yuden_NR-30xx"
BUCK = "Regulator_Switching:TPS62130"
FBUCK = "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm"
LDO = "Regulator_Linear:TPS7A20xxxDBV"
ADP = "dogrudan-sdr:ADP150"
FSOT = "Package_TO_SOT_SMD:SOT-23-5"
FTSOT = "Package_TO_SOT_SMD:TSOT-23-5"
FFB = "Inductor_SMD:L_0805_2012Metric"   # ferrit boncuk

s = Sheet("01_power", "Guc agaci", UU["01_power"],
          "9-18V giris, ters polarite, TPS62130 x2, TPS7A20, ADP150 x4")


def buck(ref, x, y, vin_label, vout_label, lref, fb_hi, fb_lo, note,
         pg_label=None, en_label=None, cin=(), cin_fp=None):
    """Bir TPS62130 kati: giris, bobin, cikis, geri besleme boleni."""
    s.sym(BUCK, ref, "TPS62130", x, y, fp=FBUCK)
    P = lambda n: s.P(BUCK, n, x, y)
    # GIRIS KONDANSATORU YOKTU.
    # Bir buck'ta giris kondansatoru sussuz gibi gorunur ama devrenin
    # en kritik parcasidir: yuksek taraf anahtari her periyotta
    # kapaninca giris akimi SIFIRDAN TEPE AKIMA ziplar. O kesikli
    # akimi verecek bir kondansator IC'nin dibinde yoksa, akim
    # kaynagin ta kendisinden — burada A kartinin XT60'indan ve
    # kablodan — cekilir. Cevrim kartin yarisi kadar buyur, di/dt
    # yuksektir, sonuc hem yayilim hem giris rayinda gurultudur.
    # TPS62130 veri sayfasi Tablo 8: en az 10 uF seramik, VIN
    # bacaginin DIBINDE. Ikinci 100 nF yuksek frekans icin.
    # Bu iki parca yerlesimde regulatorle TEK BLOK yerlesiyor
    # (kicad/gercek_yerlesim.py, regulator_blok).
    for cref, cval, cfp in zip(cin, ("10uF", "100nF"),
                               (cin_fp or FC1206, FC)):
        s.sym(C, cref, cval, x - 30 + 18 * cin.index(cref), y + 30,
              rot=90, fp=cfp)
        s.pin_label(C, "1", x - 30 + 18 * cin.index(cref), y + 30, 90,
                    vin_label, "input")
        s.pin_power(C, "2", x - 30 + 18 * cin.index(cref), y + 30, 90, "GND")
    # giris
    s.pin_label(BUCK, "10", x, y, 0, vin_label, "input", d=15.24)
    s.pin_label(BUCK, "13", x, y, 0, en_label or ("EN_" + ref), "input", d=20.32)
    s.pin_power(BUCK, "6", x, y, 0, "GND", d=8.89)
    # kullanilmayan/sabit pinler — bosta birakilirsa ERC hatasi ve
    # gercekte de tanimsiz davranis
    s.pin_power(BUCK, "7", x, y, 0, "GND", d=8.89)  # FSW: sabit anahtarlama frekansi
    s.pin_power(BUCK, "8", x, y, 0, "GND", d=13.97) # DEF: ayarlanabilir cikis modu
    s.nc(*P("9"))                                # SS/TR: dahili yumusak baslatma
    if pg_label:
        s.pin_label(BUCK, "4", x, y, 0, pg_label, "output")
    else:
        s.nc(*P("4"))
    # SW -> bobin -> cikis dugumu
    sw = P("1")
    lx, ly = sw[0] + 15, sw[1]
    # rot=270, 90 DEGIL. 90'da pin 1 sagda, pin 2 solda kaliyor; SW'den
    # pin 1'e cekilen yatay tel tam pin 2'nin ustunden geciyor ve BOBINI
    # KISA DEVRE ediyor. Netlist'te L1'in iki pini de +3V3'te goruldu,
    # ERC "Output ile Power output baglanmis" diye bagirdi.
    s.sym(L, lref, "2.2uH", lx, ly, rot=270, fp=FL)
    s.link(sw, s.P(L, "1", lx, ly, 270))
    out = s.P(L, "2", lx, ly, 270)
    ox = out[0] + 12
    s.wire(out[0], out[1], ox, out[1])
    s.glabel(vout_label, ox, out[1], "output")
    # cikis kondansatoru
    s.sym(C, "C" + ref[1:], "22uF", ox - 6, out[1] + 12, fp=FC)
    s.link((ox, out[1]), s.P(C, "1", ox - 6, out[1] + 12), mid="v")
    s.pin_power(C, "2", ox - 6, out[1] + 12, 0, "GND")
    # VOS ve FB ETIKETLE baglaniyor, uzun tel cekilerek DEGIL.
    # Once ortogonal tel cektim: VOS'tan cikis dugumune giden yatay
    # parca tam bobinin uzerinden geciyordu, bobin kisa devre oldu.
    # Bir sayfada elle koordinat kovalamak calisiyor; uretecte
    # calismiyor. Uzun mesafe = etiket.
    s.pin_label(BUCK, "14", x, y, 0, vout_label, "input")        # VOS
    fbnet = "FB_" + ref
    s.pin_label(BUCK, "5", x, y, 0, fbnet, "input")
    # geri besleme boleni: cikis - Rhi - FB - Rlo - GND
    fx, fy = ox + 20, out[1] + 8
    s.sym(R, fb_hi[0], fb_hi[1], fx, fy, fp=FR)
    s.sym(R, fb_lo[0], fb_lo[1], fx, fy + 16, fp=FR)
    s.pin_label(R, "1", fx, fy, 0, vout_label, "input")
    mid = s.P(R, "2", fx, fy)
    s.link(mid, s.P(R, "1", fx, fy + 16))
    s.glabel(fbnet, mid[0], mid[1], "passive")
    s.pin_power(R, "2", fx, fy + 16, 0, "GND")
    s.text(note, x - 8, y + 34, 1.2)


# ---------------------------------------------------------------- giris
s.text("GIRIS VE KORUMA — NETLIST.md §9\\n"
       "9-18 V aku ya da tezgah kaynagi. Ters polarite sahada bir kere olur, yeter.",
       20, 16)

s.sym("Connector:Conn_01x02_Pin", "J1", "XT60", 30, 42,
      fp="Connector_Wire:SolderWire-1.5sqmm_1x02_P6mm_D1.7mm_OD3mm_Relief")
JP = lambda n: s.P("Connector:Conn_01x02_Pin", n, 30, 42)
s.pin_power("Connector:Conn_01x02_Pin", "2", 30, 42, 0, "GND")

s.sym("Transistor_FET:Q_PMOS_GSD", "Q1", "DMP3098L", 58, 40,
      fp="Package_TO_SOT_SMD:SOT-23")
QS = s.P("Transistor_FET:Q_PMOS_GSD", "3", 58, 40)     # source
QD = s.P("Transistor_FET:Q_PMOS_GSD", "2", 58, 40)     # drain
QG = s.P("Transistor_FET:Q_PMOS_GSD", "1", 58, 40)     # gate
s.link(JP("1"), QS)
s.sym(R, "R1", "100k", 58, 60, rot=90, fp=FR)
s.link(QG, s.P(R, "1", 58, 60, 90), mid="v")
s.pin_power(R, "2", 58, 60, 90, "GND")
s.sym("Device:D_Zener", "D2", "12V", 48, 60, rot=90,
      fp="Diode_SMD:D_SOD-323")
s.link(QG, s.P("Device:D_Zener", "2", 48, 60, 90), mid="v")
s.pin_power("Device:D_Zener", "1", 48, 60, 90, "GND")

s.sym("Device:Fuse", "F1", "2A", 82, 40,
      fp="Fuse:Fuse_1206_3216Metric")
s.link(QD, s.P("Device:Fuse", "1", 82, 40))
FO = s.P("Device:Fuse", "2", 82, 40)
s.sym("Device:D_TVS", "D1", "SMBJ20A", 96, 52, rot=90,
      fp="Diode_SMD:D_SMB")
s.link(FO, s.P("Device:D_TVS", "1", 96, 52, 90), mid="v")
s.pin_power("Device:D_TVS", "2", 96, 52, 90, "GND")
s.wire(FO[0], FO[1], FO[0] + 22, FO[1])
s.glabel("VIN_PROT", FO[0] + 22, FO[1], "output")
s.pwr_flag(FO[0] + 22, FO[1] - 6.35)
s.wire(FO[0] + 22, FO[1], FO[0] + 22, FO[1] - 6.35)

# ANAHTARLAMALI REGULATOR CIKISI PASIF GORUNUYOR: TPS62130'un SW pini
# bobine gidiyor, bobin pasif, dolayisiyla +3V3 ve +1V1 raylarinda ERC
# hicbir "guc kaynagi" gormuyor. LDO'larda sorun yok, VOUT'lari power_out.
# Bayragi GEOMETRIYLE dugume degdirmeye calisma — etiketle bagla, yeri
# serbest kalsin. (Once koordinat tahmin ettim, teller boslukta kaldi.)
def flag(x, y, net):
    s.glabel(net, x, y, "input")
    s.wire(x, y, x, y - 6.35)
    s.pwr_flag(x, y - 6.35)

flag(150, 100, "+3V3")
flag(350, 100, "+1V1")
s.power("GND", 200, 100)
s.wire(200, 100, 200, 93.65)
s.pwr_flag(200, 93.65)

# TPS62130 PG ACIK DRENAJ — cekme direnci OLMADAN U2'nin EN'i hicbir
# zaman yukari cikmaz, yani +1V1 hic acilmaz. Kartta gorunmez bir hata,
# semada ERC yakaladi.
s.sym(R, "R2", "100k", 390, 100, rot=90, fp=FR)
s.pin_label(R, "1", 390, 100, 90, "+3V3", "input")
s.pin_label(R, "2", 390, 100, 90, "PG_3V3", "passive")

s.text("PWR_FLAG sadece VIN_PROT'ta: o ray konnektorden geliyor, gercek guc\n"
       "cikisi pini yok. Regulator ciktilarina bayrak konursa ERC cakisma verir.",
       130, 62, 1.2)
s.text("Q1 kaynagi girise, drain VIN_PROT'a. Govde diyodu ters baglamada iletmiyor.\\n"
       "R1 gate'i asagi ceker (P-kanal icin iletim), D2 Vgs'i 12V'ta sinirlar.\\n"
       "TVS ve sigorta drain tarafinda — koruma yukun oncesinde.", 40, 74, 1.25)

# ---------------------------------------------------------------- buck x2
s.text("ANA RAY +3V3 — TPS62130, 3-17V giris, 3A", 20, 100)
buck("U1", 45, 125, "VIN_PROT", "+3V3", "L1", ("R3", "100k"), ("R4", "32k"),
     "Vout = 0.8 x (1 + R3/R4).  3.3V icin oran 3.125\\n"
     "L1, Cin ve Cout datasheet Tablo 8'den.",
     pg_label="PG_3V3", en_label="VIN_PROT", cin=("C3", "C4"))

s.text("FPGA CEKIRDEK +1V1 — TPS62130 #2", 220, 100)
buck("U2", 245, 125, "+3V3", "+1V1", "L2", ("R5", "10k"), ("R6", "26.7k"),
     "1.1V icin oran 0.375.  EN zinciri: U1 PG -> U2 EN,\\n"
     "guc siralamasi VCC(1.1) once, sonra VCCAUX, sonra VCCIO.",
     en_label="PG_3V3", cin=("C5", "C6"), cin_fp=FC0805)

# ---------------------------------------------------------------- LDO'lar
s.text("HASSAS RAYLAR — her biri AYRI LDO, AYRI ADA. Anahtarlamalidan BESLENMEZ (§1).",
       20, 185)

# LDO'LARIN GIRIS VE CIKIS KONDANSATORLERI — HICBIRI YOKTU.
# Yedi regulatorun (U3 + U4..U9) tek bir kondansatoru yoktu. En
# yakin +3V3 kapasitesi 18-37 mm oteydi, cikis raylarininki 40-94 mm.
# O mesafede kondansator regulatorun donguse hicbir sey katmaz:
# aradaki iz endüktansi (~1 nH/mm) LDO'nun gordugu empedansi
# yukseltiyor ve dogrudan kararlilik meselesi.
#
# ADP150 veri sayfasi (Rev. G, "Capacitor Selection"): girise ve
# cikisa 1 uF X5R/X7R seramik ZORUNLU; "output capacitor ... is
# required for stability". TPS7A20 (TI SBVS340) da en az 1 uF
# giris + 1 uF cikis istiyor.
#
# Kondansatorsuz bir LDO carpik calismaz — SALINIR. Cikista
# yuz kHz mertebesinde bir salinim olur ve o ray neyi besliyorsa
# (ADC AVDD, VCXO, FPGA VCCAUX) onun gurultu tabanina biner.
# Aranmasi en zor hata sinifi: her sey "calisiyor" gorunur,
# yalnizca spektrum kotudur.
#
# ERC neden gormedi: eksik bir kondansator kural ihlali degil.
# Bir netlist "bu regulatorun kondansatoru olmali" bilmiyor.
def ldo_kaplar(r_in, r_out, x, giris, cikis, y=205):
    """Bir LDO'nun giris/cikis 1 uF'lari — govdenin iki yaninda."""
    for ref, dx, ag in ((r_in, -14, giris), (r_out, 14, cikis)):
        s.sym(C, ref, "1uF", x + dx, y + 14, rot=90, fp=FC)
        s.pin_label(C, "1", x + dx, y + 14, 90, ag, "input")
        s.pin_power(C, "2", x + dx, y + 14, 90, "GND")


# TPS7A2033 DEGIL TPS7A2018. Sondaki iki hane cikis gerilimi:
# "33" = 3.3 V, "18" = 1.8 V. Parca 3.3 V'luk yazilmisti ama cikisi
# +1V8 rayina, yani FPGA'nin banka 6/3 VCCIO'suna gidiyor (20 ped).
# Siparis edilse o bankalar 3.3 V gorurdu. Bagalanti dogruydu, yanlis
# olan tek sey parca numarasiydi — ve bunu ne ERC ne DRC ne de bir
# netlist denetimi gorur.
s.sym(LDO, "U3", "TPS7A2018", 40, 205, fp=FSOT)
s.pin_label(LDO, "1", 40, 205, 0, "+3V3", "input")
s.pin_label(LDO, "3", 40, 205, 0, "+3V3", "input")
s.pin_label(LDO, "5", 40, 205, 0, "+1V8", "output")

s.pin_power(LDO, "2", 40, 205, 0, "GND")
ldo_kaplar("C10", "C11", 40, "+3V3", "+1V8")
s.text("+1V8\\nFPGA VCCIO\\nbanka 6/3", 30, 219, 1.2)

# ARALIK 55 mm. Once 10 mm koymustum, U4 ile U5 govdesi ust uste
# bindi — SVG'ye bakmadan fark edilmiyordu.
# ADP150 basina (giris kondansatoru, cikis kondansatoru).
# C10/C11 U3'un; C12..C23 alti ADP150'nin. C7-C46 araligi bostu.
ADP_KAP = {"U8": ("C12", "C13"), "U4": ("C14", "C15"),
           "U5": ("C16", "C17"), "U6": ("C18", "C19"),
           "U7": ("C20", "C21"), "U9": ("C22", "C23")}
# HER RAYIN KENDI VARYANTI — ADP150 SABIT CIKISLI BIR LDO.
#
# Alti LDO'nun degeri de "ADP150" yaziyordu ve BOM'da tek satirda,
# tek LCSC koduyla (C144257) toplaniyorlardi. O kod bu dosyanin kendi
# yorumuna gore ADP150AUJZ-2.5. Yani siparis edilse +1V8_A, +1V8_D ve
# +1V8_CLK raylari 2.5 V cikardi.
#
# AD9251'in AVDD mutlak azami 2.0 V (veri sayfasi Tablo 3). Iki ADC de
# ilk enerjilendirmede olurdu ve hicbir denetim bunu gostermezdi:
# sema dogru, netlist dogru, DRC temiz — yalnizca parca numarasi tek.
#
# Deger artik gerilimi tasiyor; bom.py her varyanti ayri satira
# koyuyor.
# ACIK MADDE — U6 VE U7 CALISMAZ: 3.3'TEN 3.3 URETILEMEZ.
#
# ONCE COZUM DENENDI VE GERI ALINDI. LDO'lari cikarip yerine ferrit
# boncuk + kondansator koydum; sema uretimi kirildi ve kart bozuldu
# (ERC 1 ihlal, sema denetimi 58 bulgu). Deger kaybetmemek icin
# yalnizca o blok geri alindi, varyant duzeltmeleri kaldi.
#
# Ikisi de girisini +3V3'ten aliyor ve cikisi +3V3_CLK ile +3V3_A,
# yani yine 3.3 V. Bir LDO'nun dusme gerilimi var (ADP150 icin 150 mA'de
# ~105 mV); ayni gerilimden ayni gerilim uretilemez. Regulatorler
# duzenlemeye hic girmez, cikis girisi takip eder ve LDO'nun
# varlik sebebi olan PSRR hic olusmaz.
#
# Yerine FERRIT BONCUK + KONDANSATOR. Yuk kucuk: +3V3_CLK dort ped
# (VCXO), +3V3_A sekiz ped (DAC AVDD), toplam ~100 mA. Gurultunun
# geldigi yer U1'in anahtarlama frekansi (TPS62130, 2.5 MHz) ve orada
# ferrit + 10 uF, bir LDO'nun ayni frekanstaki PSRR'iyla ayni
# mertebede bastirma veriyor. Ustelik iki parca ve iki ray eksiliyor.
#
# Alternatifler tartildi: VIN_PROT'tan LDO ile beslemek TSOT-23-5
# govdede parca basina 0.44 W demek (12 V - 3.3 V) x 50 mA, cok
# sicak. Ayri bir 5 V buck eklemek calisirdi ama bir bobin, bir
# geri besleme bolucusu ve dort kondansator daha getiriyordu.
rails = [("U8", "+2V5", "2.5", "FPGA VCCAUX\\nZORUNLU", 100),
         ("U6", "+3V3_CLK", "3.3", "VCXO — TEK\\nbesleme, FERRIT", 265),
         ("U7", "+3V3_A", "3.3", "DAC AVDD", 320),
         ("U4", "+1V8_A", "1.8", "ADC AVDD", 155),
         ("U5", "+1V8_D", "1.8", "ADC DRVDD", 210),
         ("U9", "+1V8_CLK", "1.8", "ADCLK846 VS\\nZORUNLU 1.8V", 375)]
for ref, out, volt, what, x in rails:
    s.sym(ADP, ref, f"ADP150-{volt}", x, 205, fp=FTSOT)
    # U9 (+1V8_CLK) +2V5'ten besleniyor: 3.3'ten dusurmek 1.5 V x akim
    # kadar gereksiz isi uretirdi, TSOT-5 govdede bu cok.
    src = "+2V5" if ref == "U9" else "+3V3"
    s.pin_label(ADP, "1", x, 205, 0, src, "input")
    s.pin_label(ADP, "3", x, 205, 0, src, "input")        # EN -> VIN
    s.pin_label(ADP, "5", x, 205, 0, out, "output")
    s.pin_power(ADP, "2", x, 205, 0, "GND")
    s.nc(*s.P(ADP, "4", x, 205))
    # her ADP150'ye kendi giris ve cikis 1 uF'i (veri sayfasi sarti)
    ldo_kaplar(*ADP_KAP[ref], x=x, giris=src, cikis=out)
    s.text(what, x - 8, 226, 1.2)

s.text("U9 (+1V8_CLK) ADCLK846'nin VS rayi. Veri sayfasi basligi:\n"
       "'1.8 V, 6 LVDS/12 CMOS Output Clock Fanout Buffer'. Saat bolumu\n"
       "bastan 3.3 V varsayilmisti — tampon o rayda calismaz.", 320, 252, 1.25)
s.text("U8 (+2V5) ECP5 VCCAUX. Ilk guc agacinda ATLANMISTI — FPGA'yi hic\n"
       "calistirmayan turden bir eksik. ADP150AUJZ-2.5, LCSC C144257.", 105, 244, 1.25)
s.text("U6 (+3V3_CLK) VCXO'nun TEK beslemesi. Ferrit boncuk, ayri toprak adasi.\\n"
       "Besleme gurultusu DOGRUDAN faz gurultusune donusuyor — manset spec burada.",
       105, 232, 1.3)

# ---------------------------------------------------------------- notlar
s.text("AYRISTIRMA (NETLIST.md §1)\\n"
       "her ECP5 VCC/VCCIO topu 100nF, viasi dogrudan duzleme · ECP5 toplu 4x10uF + 2x47uF\\n"
       "ADC AVDD x8 pin basina 100nF + toplu 10uF · ADC DRVDD x4 100nF\\n"
       "VCXO 100nF + 10uF + FERRIT BONCUK · PHY 10uF X5R  (Y5V KULLANMA, datasheet s.46-53)",
       20, 250, 1.3)
s.text("GUC BUTCESI ~2.8 W -> 12V'ta ~230 mA. 10 Ah aku ile ~40 saat.\\n"
       "Saha modunda ikinci PHY yazilimdan kapatilabilir, 0.25 W kazanc.", 20, 268, 1.3)

s.write(os.path.join(HERE, "01_power.kicad_sch"))
print("01_power.kicad_sch yazildi")
