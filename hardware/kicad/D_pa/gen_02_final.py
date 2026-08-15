#!/usr/bin/env python3
"""02_final: 4 x IRFP250N push-pull-paralel, geri beslemeli.
Kaynak: ../../PA_TASARIM.md §0 ve §1.

REFERANS ARALIGI — BU DOSYA: L20-L29, Q10-Q19, T30-T39.
Elle sayilan referanslar iki dosyada ayni degeri uretince parcalar
SESSIZCE KAYBOLUYOR: iki sembol tek ayak izine cokuyor, biri kartta
hic olmuyor ve netlist yine de tutarli gorunuyor. Bu dosya ile
gen_01_driver.py arasinda uc kez oldu:
    L10  1uH bogucu (surucu) / 10uH bogucu (final)  -> surucununki gitti
    T10  2:1 (surucu)        / 3:1 (final)          -> surucununki gitti
    T11  cikis trafosu       -> daha once ayni sekilde kaybolup
                                T12 diye geri gelmisti
Ayrilan araliklar dosyalarin basinda yazili; yeni parca eklerken
KENDI araligindan al.
    gen_01_driver : C10-C19  J10  L10-L19  Q20-Q29  R10-R19  T10-T19  U10-U19
    gen_02_final  : L20-L29  Q10-Q19  T30-T39
    gen_03_bias   : RS1-RS4  U20-U29 (DAC)  U31-U39 (INA240)  U41-U49 (LM358)
    gen_04_detect : J20 J40  K20  R160-R199  T20-T29  U60-U69
    gen_05_lpf    : KL1-KL7  QL1-QL7  C500+  L500+  R500+
    gen_06_power  : D30  J30-J33  L50-L59  Q30-Q39  R600+  U50-U59
"""
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
s.sym(T, "T30", "BN43-202 3:1", 70, 130, fp=FT)
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
    # ** BIAS SERVOSU CALISAMIYORDU — DC YOLU 1R'YE KISA DEVREYDI. **
    #
    # Eski baglanti: GIN_A/GIN_B dogrudan 10R uzerinden gecide
    # gidiyordu. Ama GIN_A ve GIN_B'nin her biri 1R ile TOPRAGA
    # bagli (bastirma direnci, yukarida). Gecidin DC gerilimi
    # boylece
    #     Vg = VGATE x (10 + 1) / (1000 + 10 + 1) = VGATE / 92
    # oluyordu: servo 4 V icin 367 V uretmek zorundaydi. Yani A
    # sinifi bias HIC KURULAMAZDI ve dort servo da doymus halde
    # kalirdi. Ustelik dort gecit birbirine 10R+10R uzerinden DC
    # bagliydi, yani "her cihaza ayri servo" tasarim kararinin
    # kendisi de gecersizdi.
    #
    # COZUM: her cihazin gecidine AYRI kuplaj kondansatoru. RF
    # trafodan geciyor, DC yolu yalnizca kendi servosuna kaliyor.
    # 100 nF, 1.8 MHz'te 0.88 ohm — 10R bastirma direncinin onda
    # biri, RF surusune etkisi yok.
    # REFERANSLAR SABIT: bu uc parca (kuplaj kondansatoru, 10R
    # bastirma, 1k servo direnci) YERLESIMDE ADIYLA aniliyor
    # (gercek_yerlesim SIMETRIK listesi ve ayna cagrilari). cnt()
    # ile uretilirse sayfaya bir parca eklendiginde hepsi kayiyor
    # ve simetrik yerlestirilen dirençler baska parcalara donuyor —
    # bu sayfada tam olarak o oldu: dort kuplaj kondansatoru
    # eklenince R202..R209 baska parcalara kaydi ve dort kapi
    # hatti 14.5 mm'den 22.5/34.2/24.9 mm'ye dagildi.
    s.sym(C, f"C{230 + i}", "100nF", x - 40, y, rot=90, fp=FC)
    s.pin_label(C, "1", x - 40, y, 90, f"GIN_{kol}", "passive")
    s.pin_label(C, "2", x - 40, y, 90, f"GC{10 + i}", "passive")
    # her gecide AYRI seri direnc: parazit osilasyon sondurme
    s.sym(R, f"R{240 + i}", "10R", x - 22, y, rot=90, fp=FR)
    s.pin_label(R, "1", x - 22, y, 90, f"GC{10 + i}", "passive")
    s.pin_label(R, "2", x - 22, y, 90, f"G{10 + i}", "passive")
    s.pin_label(Q, "1", x, y, 0, f"G{10 + i}", "input", d=7.62)
    # bias servosu gecidi suruyor (03_bias)
    s.sym(R, f"R{244 + i}", "1k", x - 22, y + 26, rot=90, fp=FR)
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
# ** ORTA UC BAGLI DEGILDI — FINAL KATININ 50 V'U DRAINLERE HIC
# ULASMIYORDU. **
# Device:Transformer_1P_1S dort bacakli ve ORTA UCU YOK. Asagidaki
# bogucu (L20) ve baypas kondansatorleri DRN_CT dugumune baglaniyor
# ama o dugumun trafoda karsiligi olmadigi icin ag havada kaliyordu.
# Netlistten olculdu: DRN_CT = {L20.2, C210, C211, C212} — dort
# parca, TRAFOYA GITMIYOR. Yani dort IRFP250N'in drainleri sadece
# birbirine ve trafonun birincil uclarina bagliydi; DC besleme yolu
# YOKTU. Kart basilsa final kati hic calismazdi.
# ERC de DRC de bunu gormez: DRN_CT dort pedli, yani "bagli" ag.
# Cozum: birincili orta uclu 5 bacakli trafo (lib/gen_symbols
# xfmr_ct + XFMR_Toroid_5P_Vertical). Fiziksel karsiligi iki turlu
# bifilar birincilin orta noktasindaki tel eki — BN43-3312'de
# standart uygulama.
TCT = "dogrudan-sdr:XFMR_CT"
FTCT = "dogrudan-sdr:XFMR_Toroid_5P_Vertical"
s.sym(TCT, "T31", "BN43-3312 2:4 CT", 350, 285, fp=FTCT)
s.pin_label(TCT, "1", 350, 285, 0, "DRN_A", "input", d=10.16)
s.pin_label(TCT, "2", 350, 285, 0, "DRN_B", "input", d=10.16)
s.pin_label(TCT, "5", 350, 285, 0, "DRN_CT", "input", d=15.24)
s.pin_label(TCT, "3", 350, 285, 0, "PA_OUT", "output", d=10.16)
s.pin_power(TCT, "4", 350, 285, 0, "GND", d=10.16)

# besleme: orta uctan, RF bogucu ile
s.sym(L, "L20", "10uH bogucu", 350, 250, rot=90, fp=FL)
s.pin_label(L, "1", 350, 250, 90, "+50V", "input")
s.pin_label(L, "2", 350, 250, 90, "DRN_CT", "passive")
# DRN_CT 50 V RAYI: 1206'DA 100uF YOK.
# 1206'da 100uF yalnizca 6.3 V sinifinda uretiliyor; 50 V'ta
# ayni pakette tavan ~10 uF. Toplu enerji zaten +50V rayindaki
# iki 470uF elektrolitikten geliyor (gen_06_power C601/C602);
# buradaki is yerel dusuk-ESR baypas, 10uF/100V bunu yapiyor.
for i, v in enumerate(("100nF", "1uF", "10uF")):
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
       "T31 cikis: BN43-3312, birincil 2 sarim ORTA UCLU, ikincil 4.\\n"
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
       "10uF (modulasyon zarfi, 100 V sinifi). A sinifinda DC cekisi\\n"
       "sabit oldugu icin zarf akimi kucuk, ama tepe akim 6.7 A —\\n"
       "dusuk ESR sec. Toplu enerji +50V'daki 2 x 470uF'te.",
       300, 320, 1.35)

s.write(os.path.join(HERE, "02_final.kicad_sch"))
print("02_final.kicad_sch yazildi")
