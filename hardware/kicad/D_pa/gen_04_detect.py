#!/usr/bin/env python3
"""04_detect: yonlu kuplor, guc olcumu, SWR korumasi, DPD ornekleme.
Kaynak: ../../PA_TASARIM.md §6 ve §6b.

REFERANS ARALIGI — BU DOSYA: J20 J40, K20, R160-R199, T20-T29, U60-U69.
(U40-U49 SECILEMEZ: gen_03_bias.py'nin LM358 paketleri U41/U42.
 Ilk duzeltmede dedektorleri oraya tasiyip ayni hatayi bir kez
 daha yaptim — bu sefer LM358'in biri kayboldu. Aralik secmeden
 once o araligin BOS oldugunu olcmek gerekiyor, varsaymak degil.)
Dedektorler U30/U31 idi ve gen_03_bias.py'nin INA240'lari da U30+n
uretiyordu: U31 CAKISTI. Kartta AD8318 kazandi, birinci cihazin akim
olcum yukselteci (INA240) HIC OLUSMADI — Q10'un bias servosu geri
beslemesiz kaldi. A sinifinda geri beslemesiz bias termal kacistir:
cihaz isindikca akim artar, artan akim daha cok isitir.
Ustelik kaybolan sembolun izi kaldi: AD8318 U31'in ped 8'i (GND)
SRC1 agina baglandi, yani 0.01R shunt bir QFN'in toprak pini
uzerinden kisa devre edilmis gorunuyordu. Iki ozdes dedektorden
birinin baglantisinin otekinden farkli olmasi hatanin imzasiydi.
Aralik listesi gen_02_final.py basinda."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

DET = "dogrudan-sdr:AD8318"
FDET = "Package_DFN_QFN:NXP_VQFN-16-1EP_4x4mm_P0.65mm_EP2.1x2.1mm"
T = "Device:Transformer_1P_1S"
# TRAFO AYAK IZI, BOBIN DEGIL. Once L_Toroid_T50_Vertical
# kullaniyordum: o 2 PEDLI bir bobin ayak izi. Trafo sembolunun
# 3. ve 4. bacaklari (ikincil) inecek bakir bulamadi ve sessizce
# yok oldu — final cikis trafosunun PA_OUT'u, kuplorlerin
# detektore giden ornegi, hepsi kopuktu.
FT = "dogrudan-sdr:XFMR_Toroid_4P_Vertical"
K = "dogrudan-sdr:G6K-2F-Y"
FK = "Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y"
R, C = "Device:R", "Device:C"
FR = "Resistor_SMD:R_0603_1608Metric"
FRP = "Resistor_SMD:R_2512_6332Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
CONN = "Connector:Conn_Coaxial"
CONN2 = "Connector_Generic:Conn_01x02"
FLUG = "TerminalBlock_Altech:Altech_AK100_1x02_P5.00mm"
FSMA = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"

s = Sheet("04_detect", "Kuplor + olcum", UU["04_detect"],
          "yonlu kuplor, AD8318 x2, SWR kesme, DPD ornekleme", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{399 + nr[0]}"


s.text("YONLU KUPLOR VE OLCUM", 16, 14, 2.2)
s.text("Uc is birden yapiyor:\\n"
       "  1 KAPALI CEVRIM GUC KONTROLU — kademeler kalibreli olsun\\n"
       "  2 SWR KORUMASI — anten yokken verirsen final olmesin\\n"
       "  3 DPD ORNEKLEME — bozulmanin tersini hesaplamak icin\\n\\n"
       "PA kazanci sicaklikla, beslemeyle ve bantla degisir. Zayiflaticiyi\\n"
       "acik cevrim ayarlamak 'yaklasik 50 W' verir; olcup duzeltmek\\n"
       "kalibreli 50 W verir.", 16, 22, 1.35)

# ---------------------------------------------------------------- kuplor
s.text("KUPLOR — tandem match, akim + gerilim ornegi", 16, 95, 1.8)
# T21'IN IKI PEDI DE ANT_OUT'TAYDI: BIRINCIL KISA DEVREYDI.
#
# Eski hali T20'nin kopyasiydi ama birincilinin iki ucu da ANT_OUT
# etiketliydi. Kisa devre edilmis bir birincilin ikincilinde gerilim
# olusmaz: REV_RAW HER ZAMAN SIFIR okur. Yani SWR korumasi hicbir
# kosulda tetiklenmez — anten sokulu haldeyken 100 W verilir ve
# final gider. Dogru okuyan bir olcum yerine SESSIZCE SIFIR okuyan
# bir olcum, hic olculmemesinden daha tehlikeli: ustune koruma
# mantigi kuruluyor.
#
# YERINE TANDEM MATCH (yonlu kuplor):
#   T20  1 sarim hatta SERI          -> akim ornegi, i = I/32
#   T21  32 sarim hat-TOPRAK arasi   -> gerilim ornegi, v = V/32
# T20'nin 32 sarimli ikincili DOGRUDAN iki port arasinda; her portun
# soguk ucu 51R uzerinden ORTAK dugume (CPL_COM) gidiyor ve o dugumu
# T21'in tek sarimli ucu surukluyor. Cozum:
#     V_FWD = v + 51 x i        V_REV = v - 51 x i
# Yansiyan port 51 x I = V oldugunda, yani yuk 51 ohm iken sifira
# iniyor. Sifir noktasi dedektor yukunden BAGIMSIZ: iki porta da
# ayni yuk biniyor, ortak mod terimini oteliyor.
#
# ISARET/SARIM YONU: T21'in tek sarimli ucunun yonu FWD ile REV'i
# takas eder. Devreye almada 50 ohm kukla yuke verilip REV'in
# sifirlandigi dogrulanacak; ters cikarsa T21'in 1 sarim ucu ters
# baglanacak. Semada ifade edilemeyen tek sey bu.
s.sym(T, "T20", "FT50-43 1:32", 70, 140, fp=FT)
s.pin_label(T, "1", 70, 140, 0, "PA_LPF_OUT", "input", d=10.16)
s.pin_label(T, "2", 70, 140, 0, "ANT_OUT", "output", d=10.16)
s.pin_label(T, "3", 70, 140, 0, "FWD_RAW", "output", d=10.16)
s.pin_label(T, "4", 70, 140, 0, "REV_RAW", "output", d=15.24)
s.sym(T, "T21", "FT50-43 1:32", 70, 190, fp=FT)
s.pin_label(T, "1", 70, 190, 0, "CPL_COM", "passive", d=10.16)
s.pin_power(T, "2", 70, 190, 0, "GND", d=15.24)
s.pin_label(T, "3", 70, 190, 0, "ANT_OUT", "input", d=10.16)
s.pin_power(T, "4", 70, 190, 0, "GND", d=15.24)

for i, net in enumerate(("FWD_RAW", "REV_RAW")):
    # 51R ARTIK TOPRAGA DEGIL CPL_COM'A. Iki sonlandirmanin soguk
    # ucu ortak ve gerilim ornegi oradan giriyor; topraga baglanirsa
    # gerilim ornegi devreden cikar ve iki port da ayni sayiyi
    # gosterir (yonluluk sifir).
    s.sym(R, cnt("R"), "51R 1%", 125, 140 + i * 50, rot=90, fp=FRP)
    s.pin_label(R, "1", 125, 140 + i * 50, 90, net, "passive")
    s.pin_label(R, "2", 125, 140 + i * 50, 90, "CPL_COM", "passive")
    s.sym(C, cnt("C"), "1nF", 150, 140 + i * 50, fp=FC)
    s.pin_label(C, "1", 150, 140 + i * 50, 0, net, "passive")
    s.pin_label(C, "2", 150, 140 + i * 50, 0, f"{net[:3]}_AC", "passive")

s.text("FT50-43 x2. T20: birincil 1 sarim (duz gecen tel), ikincil 32.\\n"
       "T21: 32 sarim hat-toprak arasi, 1 sarim CPL_COM'a.\\n\\n"
       "Akim ornegi 51 x I/32, gerilim ornegi V/32. Toplam ileri\\n"
       "porta, fark yansiyan porta gidiyor; 50 ohm yukte yansiyan\\n"
       "port sifir. Bir onceki devrede REV yapisi geregi sifirdi —\\n"
       "arasindaki fark, olcumun olup olmamasi.\\n\\n"
       "Kuplaj eski (tek trafolu, hatali) devreye gore 6 dB daha\\n"
       "yuksek: iki ornek toplaniyor. Dedektor girisindeki 61R9\\n"
       "sont 19R1'e indirildi, boylece AD8318 100 W'ta yine ~0 dBm\\n"
       "goruyor ve guc merdiveninin tamami araligin icinde kaliyor.\\n\\n"
       "YONLULUK sarimin duzgunlugune bagli: ikincil cekirdege ESIT\\n"
       "aralikli ve tam sarilmali. 20 dB yonluluk yeterli ve dikkatli\\n"
       "sarimla cikiyor; ozensiz sarimda 10 dB'ye duser ve SWR olcumu\\n"
       "yaniltir — koruma yanlis anda atar ya da hic atmaz.\\n"
       "Sarim ayrintisi: kicad/manyetik_hesap.py", 16, 250, 1.35)

# ---------------------------------------------------------------- detektorler
s.text("DETEKTORLER — AD8318 x2", 300, 95, 1.8)
for i, (net, ad) in enumerate([("FWD", "ileri"), ("REV", "yansiyan")]):
    x, y = 380, 140 + i * 75
    # Zayiflatici sont bacagi. 61R9 -> 19R1: tandem kuplor iki ornegi
    # topladigi icin port gerilimi 6 dB yukseldi, sont onu geri
    # aliyor. Seri direnc DEGISMEDI — onu buyutmek AD8318'in giris
    # kapasitesiyle bir kutup yapip 30 MHz'te kazanci dusururdu,
    # yani bant kenarinda guc okumasi kayardi.
    s.sym(R, cnt("R"), "19R1", x - 75, y, rot=90, fp=FR)
    s.pin_label(R, "1", x - 75, y, 90, f"{net}_AC", "passive")
    s.pin_power(R, "2", x - 75, y, 90, "GND")
    s.sym(R, cnt("R"), "247R", x - 55, y, rot=90, fp=FR)
    s.pin_label(R, "1", x - 55, y, 90, f"{net}_AC", "passive")
    s.pin_label(R, "2", x - 55, y, 90, f"{net}_DET", "passive")

    s.sym(DET, f"U{60 + i}", "AD8318ACPZ", x, y, fp=FDET)
    s.pin_label(DET, "14", x, y, 0, f"{net}_DET", "input", d=7.62)   # INHI
    s.pin_power(DET, "15", x, y, 0, "GND", d=12.7)                   # INLO
    s.pin_label(DET, "6", x, y, 0, f"{net}_LOG", "output", d=7.62)   # VOUT
    s.pin_label(DET, "7", x, y, 0, f"{net}_LOG", "input", d=12.7)    # VSET
    s.pin_label(DET, "16", x, y, 0, "+5V", "input", d=17.78)         # ENBL
    # TEMP kullanilmiyor: ADC kanallari dolu. Sicaklik telafisi zaten
    # asagidaki TADJ direnciyle yapiliyor. Bosta birakmak yerine
    # isaretle ki ERC "unutulmus pin" demesin.
    s.nc(*s.P(DET, "13", x, y))
    # TADJ TOPRAGA DOGRUDAN DEGIL, 500 OHM UZERINDEN.
    # Once GND'ye baglamistim. Veri sayfasi Tablo 5'te 0 ohm HIC yok:
    # 900 MHz 500, 1.9 GHz 500, 2.2 GHz 500, 3.6 GHz 51, 5.8 GHz 1k,
    # 8 GHz 500. Bu direnc sicaklik telafi katsayisini belirliyor;
    # sifirlayinca kesim noktasi sicaklikla suruklenir. 233 W isitan
    # bir PA'nin icinde tam da bu hata onemli — guc okumasi kayarsa
    # ALC ve koruma yanlis esikten calisir.
    # HF (1.8-54 MHz) tablonun altinda kaliyor ve veri sayfasi bu
    # bolge icin "deneme gerekir" diyor; 500 ohm listedeki alti
    # frekansin dordunde onerilen deger, savunulabilir varsayilan.
    # Uretimde sicaklik taramasiyla dogrulanacak.
    s.sym(R, f"R{160 + i}", "500R", x - 20, y + 40, rot=90, fp=FR)
    s.pin_label(R, "1", x - 20, y + 40, 90, f"{net}_TADJ", "passive")
    s.pin_power(R, "2", x - 20, y + 40, 90, "GND")
    s.pin_label(DET, "10", x, y, 0, f"{net}_TADJ", "passive", d=22.86)
    # besleme: VPSI x2 ve VPSO ESIT olmali (veri sayfasi Tablo 3)
    for pn in ("3", "4", "9"):
        s.pin_label(DET, pn, x, y, 0, "+5V", "input", d=5.08)
    # dort CMIP + CMOP + acik ped, hepsi topraga
    for k, pn in enumerate(("1", "2", "11", "12", "8", "17")):
        s.pin_power(DET, pn, x, y, 0, "GND", d=5.08 + (k % 3) * 6.35)
    # CLPF sembolun SOLUNDA; uzun saplama zayiflatici direncinin
    # uzerinden geciyordu. Kisa saplama + kondansator hemen yaninda.
    s.pin_label(DET, "5", x, y, 0, f"{net}_CLPF", "passive", d=7.62)
    s.sym(C, cnt("C"), "220pF", x - 20, y + 28, rot=90, fp=FC)
    s.pin_label(C, "1", x - 20, y + 28, 90, f"{net}_CLPF", "passive")
    s.pin_power(C, "2", x - 20, y + 28, 90, "GND")
    s.sym(C, cnt("C"), "100nF", x + 42, y + 20, rot=90, fp=FC)
    s.pin_label(C, "1", x + 42, y + 20, 90, "+5V", "input")
    s.pin_power(C, "2", x + 42, y + 20, 90, "GND")

# ---------------------------------------------------------------- anten
s.text("ANTEN CIKISI", 16, 395, 1.8)
# ANT_OUT'un KARTTAN CIKACAK YERI YOKTU. Kuplorlerden sonra ag
# T20/T21'de bitiyordu; 100 W'in gidecek bir konnektoru yoktu.
# Konnektor karta degil PANELE takiliyor: 100 W'lik bir HF amfisinde
# SO-239 kasaya vidalanir, karta kisa bir koaksiyelle baglanir.
# Buradaki iki lehim terminali o koaksiyelin ucu.
s.sym(CONN2, "J40", "ANTEN -> panel SO-239", 70, 425, fp=FLUG)
s.pin_label(CONN2, "1", 70, 425, 0, "ANT_OUT", "input", d=10.16)
s.pin_power(CONN2, "2", 70, 425, 0, "GND", d=10.16)
s.text("SO-239 kasaya, karta kisa koaksiyel. 100 W'ta SMA da tasir\\n"
       "ama amator istasyonun kablo tarafi PL-259; donusturucu\\n"
       "eklemek her baglantida bir kayip ve bir arizali temas noktasi\\n"
       "daha demek.\\n\\n"
       "Terminal 1.5 sqmm lehim teli icin: 100 W / 50 ohm = 1.4 A,\\n"
       "ama SWR 3:1'de tepe akim iki katina cikiyor.", 16, 445, 1.35)

s.text("VSET cikisa bagli = OLCUM modu (kontrol modu degil). Cikis\\n"
       "girise logaritmik: -25 mV/dB, 0 dBm'de ~0.5 V.\\n"
       "Giris araligi -60..0 dBm, yani 60 dB. Tandem kuplor + sont\\n"
       "zayiflatici birlikte ~-50 dB: 100 W'ta detektor ~0 dBm\\n"
       "goruyor, 100 mW'ta -30 dBm. Butun guc merdiveni araligin\\n"
       "icinde. Kesin degeri devreye almada kukla yukle olculecek;\\n"
       "log detektorun kalibrasyonu zaten olcumle yapiliyor.\\n\\n"
       "PINOUT VERI SAYFASINDAN (Rev.E Tablo 3) — ilk cizimde tahmin\\n"
       "etmis ve isaretlemistim; dokuz bacagin HICBIRI tutmadi.\\n"
       "Isaretlememis olsaydik kart basilacakti.\\n\\n"
       "VPSI (3,4) ve VPSO (9) ESIT olmali. Dort CMIP + CMOP + acik ped\\n"
       "hepsi topraga; acik ped dahili olarak CMIP'e bagli ama yine de\\n"
       "lehimlenmeli.", 300, 285, 1.35)

# ---------------------------------------------------------------- DPD
s.text("DPD ORNEKLEME YOLU", 16, 300, 1.8)
s.sym(K, "K20", "G6K-2F-Y", 70, 340, fp=FK)
s.pin_label(K, "3", 70, 340, 0, "FWD_AC", "passive", d=7.62)
s.pin_label(K, "4", 70, 340, 0, "DPD_OUT", "passive", d=7.62)
s.pin_label(K, "2", 70, 340, 0, "DPD_TERM", "passive", d=12.7)
s.pin_label(K, "1", 70, 340, 0, "+5V", "input", d=17.78)
s.pin_label(K, "8", 70, 340, 0, "DPD_EN_LO", "passive", d=22.86)
s.pin_power(K, "6", 70, 340, 0, "GND", d=27.94)
s.pin_power(K, "7", 70, 340, 0, "GND", d=33.02)
s.pin_power(K, "5", 70, 340, 0, "GND", d=38.1)
s.sym(R, cnt("R"), "51R", 120, 340, rot=90, fp=FR)
s.pin_label(R, "1", 120, 340, 90, "DPD_TERM", "passive")
s.pin_power(R, "2", 120, 340, 90, "GND")
s.sym(CONN, "J20", "DPD -> C karti", 165, 340, fp=FSMA)
s.pin_label(CONN, "1", 165, 340, 0, "DPD_OUT", "passive")
s.pin_power(CONN, "2", 165, 340, 0, "GND")

s.text("Kuplorun ileri ornegi bir role uzerinden C kartina, oradan\\n"
       "RX4 girisine gidiyor. FPGA cikisi ornekleyip bozulmanin tersini\\n"
       "hesapliyor ve gonderilen orneklere onceden uyguluyor.\\n\\n"
       "VERIRKEN ZATEN ALAMIYORUZ (TASARIM.md §8.3) — dort RX kanali\\n"
       "bosta. Kuplor guc olcumu icin zaten kondu. FPGA orada.\\n"
       "EKLENEN DONANIM: bir role, bir koaks, uc direnc.\\n\\n"
       "A sinifi + geri besleme     -42 dBc\\n"
       "+ DPD                       -55 .. -65 dBc\\n\\n"
       "Hicbir amator telsizin ulasmadigi seviye. Bu aletin yazilim\\n"
       "tanimli olmasi burada karsiligini veriyor.\\n\\n"
       "Role bosaltildiginda ornekleme yolu 51R'ye sonlaniyor: DPD\\n"
       "kapaliyken kuplor cikisi acik kalmasin, yonluluk bozulmasin.",
       16, 375, 1.35)

s.write(os.path.join(HERE, "04_detect.kicad_sch"))
print("04_detect.kicad_sch yazildi")
