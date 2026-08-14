#!/usr/bin/env python3
"""08_control: banka 0 ve 1 — SPI, PE4312, GPS, VCXO DAC, kart arasi.
Kaynak: ../NETLIST.md §7 ve §8."""
import json, os
from schlib import Sheet, unit_pins, yol_esle

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

E = "dogrudan-sdr:ECP5-BGA256"
FE = ("Package_BGA:BGA-256_14.0x14.0mm_Layout16x16_P0.8mm_"
      "Ball0.45mm_Pad0.32mm_NSMD")
A = "dogrudan-sdr:PE4312"
FA = "Package_DFN_QFN:QFN-20-1EP_4x4mm_P0.5mm_EP2.6x2.6mm_ThermalVias"
R, C = "Device:R", "Device:C"
LED = "Device:LED"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
FLED = "LED_SMD:LED_0603_1608Metric"
HDR = "Connector_Generic:Conn_02x10_Odd_Even"
FHDR = "Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Vertical"
HDR6 = "Connector_Generic:Conn_01x06"
FHDR6 = "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"
CONN = "Connector:Conn_Coaxial"
FSMA = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"

s = Sheet("08_control", "Kontrol", UU["08_control"],
          "banka 0 ve 1, PE4312 x2, GPS, VCXO DAC, kart arasi", paper="A2")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{799 + nr[0]}"


# ================================================================== banka 0
s.text("FPGA BANKA 0 — kontrol ve SDRAM tasmasi", 16, 14, 2.0)
B0X, B0Y = 80, 105
s.sym(E, "U10", "LFE5U-25F-7BG256I", B0X, B0Y, fp=FE, unit=2)
B0 = unit_pins(E, 2)
# BANKA 0 YENIDEN DAGITILDI. Iki sebep:
#   1 zayiflatici sayisi ikiden DORDE cikti (faz uyumu ozdes zincir
#     ister); veri ve saat ortaklasti, LE'ler ayrildi
#   2 D karti (PA) A'dan 13 sinyal istiyordu ve hicbiri yoktu
#
# Yer nereden acildi: ADC PDWN ve DAC SLEEP hatlari FPGA'dan cikarildi.
# Bu alet ya acik ya kapali; guc-dusurme kontrolunu hic kullanmiyoruz.
# Dordu de kendi sayfalarinda GND'ye baglandi -> 4 pin serbest.
# Artı banka 1'deki yedek = 5 yeni hat.
nets0 = [
    "SD_A9", "SD_A10", "SD_A11", "SD_A12", "SD_BA0", "SD_BA1", "SD_UDQM",
    "ADC_SDIO", "ADC_SCLK", "ADC1_nCSB", "ADC2_nCSB", "ADC_SYNC",
    # ortak seri yol: C kartindaki dort PE4312 + D kartindaki bir tane
    # + bias DAC'lari + PA'nin ADC'si hepsi bunu paylasiyor
    "ATT_DATA", "ATT_CLK",
    "ATT1_LE", "ATT2_LE", "ATT3_LE", "ATT4_LE",
    "PA_ATT_LE", "BIAS_CS1", "BIAS_CS2", "PA_ADC_CS",
    "RLY_SER", "RLY_SRCLK", "RLY_RCLK",
]
# ------------------------------------------------------------ durum LED'leri
s.text("DURUM LED'LERI", 640, 14, 1.8)
LEDS = [("LED_STATUS", "yesil", "STATUS"), ("LED_RX", "mavi", "RX"),
        ("LED_TX", "kirmizi", "TX"), ("LED_DATA", "sari", "DATA")]
for i, (net, renk, ad) in enumerate(LEDS):
    ly = 30 + i * 26
    s.sym("Device:LED", f"D{60 + i}", renk, 660, ly, rot=90,
          fp="LED_SMD:LED_0805_2012Metric")
    s.pin_label("Device:LED", "2", 660, ly, 90, "+3V3", "input")
    s.pin_label("Device:LED", "1", 660, ly, 90, f"{net}_K", "passive")
    s.sym("Device:R", f"R{60 + i}", "1k", 660, ly + 13, rot=90,
          fp="Resistor_SMD:R_0603_1608Metric")
    s.pin_label("Device:R", "1", 660, ly + 13, 90, f"{net}_K", "passive")
    s.pin_label("Device:R", "2", 660, ly + 13, 90, net, "passive")

s.text("ANOT +3V3'te, FPGA KATODU CEKIYOR (aktif dusuk).\\n"
       "Boyle secildi cunku ECP5'in IO'su akim CEKMEKTE (sink) akim\\n"
       "VERMEKTEN (source) daha guclu: 3.3V bankada 8 mA sink,\\n"
       "source tarafinda gerilim dusuyor ve LED sonuk kaliyor.\\n\\n"
       "1k ile 3.3V'ta ~1.6 mA — 0805 LED icin fazlasiyla gorunur,\\n"
       "dort LED toplam 6.4 mA. Parlaklik isterse 470R'a inilir.\\n\\n"
       "STATUS  gateware kalkti / PLL kilitli\\n"
       "RX      alis zinciri veri uretiyor\\n"
       "TX      veris aktif — PA acikken de yanar\\n"
       "DATA    ethernet trafigi", 640, 140, 1.35)

io0 = sorted(n for n, nm in B0.items() if nm.startswith("PT"))
assert len(io0) == 24, len(io0)
for p, net in yol_esle(io0, nets0[:24], "SDRAM_B0"):
    s.pin_label(E, p, B0X, B0Y, 0, net, "bidirectional", d=7.62)
for n, nm in sorted(B0.items()):
    if nm.startswith("VCCIO"):
        s.pin_label(E, n, B0X, B0Y, 0, "+3V3", "input", d=15.24)

s.text("BANKA 0: 24 I/O, TAMAMI DOLU.\\n"
       "  SDRAM tasmasi   7   (A9-A12, BA0/1, UDQM)\\n"
       "  ADC SPI+SYNC    5   SDIO, SCLK, 2x nCSB, SYNC\\n"
       "  ortak seri yol  2   ATT_DATA, ATT_CLK\\n"
       "  secme hatlari   7   ATT1..4_LE, PA_ATT_LE, BIAS_CS1/CS2\\n"
       "  PA'nin ADC'si   1   PA_ADC_CS\\n"
       "  role yazmaci    3   SER/SRCLK/RCLK\\n\\n"
       "ADC PDWN ve DAC SLEEP hatlari KALDIRILDI. Bu alet ya acik ya\\n"
       "kapali; guc-dusurme kontrolu hic kullanilmiyor. Dordu de kendi\\n"
       "sayfalarinda GND'ye bagli. Acilan 4 pin + banka 1 yedegi, PA'nin\\n"
       "istedigi 5 yeni hatti karsiladi.\\n\\n"
       "ORTAK SERI YOL: PE4312, MCP4922 ve MCP3208 hepsi saat+veri\\n"
       "paylasiyor, hangisinin dinledigini LE/CS belirliyor. Ayri yol\\n"
       "cekseydik 14 pin ederdi, boyle 9.", 16, 24, 1.35)

# ================================================================== banka 1
s.text("FPGA BANKA 1 — GPSDO, DAC-2, durum", 300, 14, 2.0)
B1X, B1Y = 370, 95
s.sym(E, "U10", "LFE5U-25F-7BG256I", B1X, B1Y, fp=FE, unit=3)
B1 = unit_pins(E, 3)
nets1 = ([f"DAC2_D{i}" for i in range(14)] +
         ["DAC2_IQWRT", "DAC2_IQRESET", "DAC2_IQSEL"] +
         ["GPS_1PPS", "GPS_RX", "GPS_TX",
          "VCXO_CS", "VCXO_CLK", "VCXO_DIN",
          "DBG_RX", "DBG_TX", "REF10_IN", "RLY_RCLK"] +
         ["TR1", "TR2", "TR3", "TR4", "PA_INHIBIT"])
io1 = sorted(n for n, nm in B1.items() if nm.startswith("PT"))
assert len(io1) == 32 and len(nets1) == 32, (len(io1), len(nets1))
for p, net in yol_esle(io1, nets1, "DAC2"):
    s.pin_label(E, p, B1X, B1Y, 0, net, "bidirectional", d=7.62)
for n, nm in sorted(B1.items()):
    if nm.startswith("VCCIO"):
        s.pin_label(E, n, B1X, B1Y, 0, "+3V3", "input", d=15.24)

s.text("BANKA 1: 32/32, MARJ YOK.\\n"
       "  DAC-2 interleaved 17 · GPS 3 · VCXO DAC 3 · hata ayiklama UART 2\\n"
       "  harici 10 MHz 1 · role RCLK 1 · T/R 4 · PA_INHIBIT 1\\n\\n"       "PA_INHIBIT yedek pini aldi. Donanim kesme hatti: FPGA\\n"       "sifirlaninca ya da beslemesizken D kartinda 100k asagi\\n"       "cekiyor ve surucu beslemesiz kaliyor. Bu hattin seri yola\\n"       "girmesi kabul edilemez — guvenlik dogrudan olmali.\\n\\n"
       "Durum LED'leri buraya sigmadi — 07_fpga_power'daki DONE LED'i ve\\n"
       "PHY LED'leri var, ayrica durum LED'i koymuyoruz. Gerekirse\\n"
       "role yazmacinin bos cikislarindan surulur, FPGA pini harcamaz.\\n\\n"
       "GPS_1PPS ve REF10_IN SAAT-YETENEKLI pine dusmeli: 1PPS'in kenari\\n"
       "dogrudan sayacla yakalanacak, yumusak I/O'da jitter olur ve\\n"
       "GPSDO'nun butun anlami kacar. Lattice pinout CSV'siyle sabitlenecek.",
       300, 24, 1.35)

# ================================================================== zayiflatici
# PE4312'LER BU KARTTA DEGIL, C KARTINDA. Once buraya cizmistim ve
# BOM'a girdiler — oysa RF zincirinin parcasilar, filtrelerle ayni
# kartta olmalilar. Burada sadece kontrol hatlari var, kart arasi
# bagliktan gidiyorlar. Cipin kendisi, P/S bacagi ve alti C bacagindaki
# cekme direnci C karti semasinda.
s.text("ZAYIFLATICI KONTROLU — cipler C KARTINDA", 16, 210, 2.0)
s.text("PE4312 x2, 0-31.5 dB. Her birine uc hat: Data / Clock / LE.\\n"
       "Seri mod (P/S = HIGH). Paralel modda alti adres bacagini surmek\\n"
       "gerekirdi, iki cip icin 12 pin ederdi.\\n\\n"
       "ACILIS DURUMU C KARTINDA COZULUYOR: seri modda bile acilistaki\\n"
       "zayiflatma C0.5..C16 bacaklarindaki seviyeye gore belirleniyor\\n"
       "(veri sayfasi s.6). Altisi da 10k ile yukari -> 31.5 dB, yani\\n"
       "acilista alici en sagir halinde. FPGA flash'tan kalkip seri\\n"
       "hatti yazana kadar on uc korunuyor. Bos biraksaydik zayiflatma\\n"
       "tanimsiz olurdu — okulun kendi HF vericisi yanibasinda kabul edilemez.",
       16, 220, 1.3)

# ================================================================== GPS
s.text("GPS / GPSDO ARAYUZU", 330, 210, 2.0)
s.sym(HDR6, "J60", "GPS modul", 360, 240, fp=FHDR6)
for p, net in [("1", "+3V3"), ("2", "GPS_RX"), ("3", "GPS_TX"),
               ("4", "GPS_1PPS")]:
    s.pin_label(HDR6, p, 360, 240, 0, net, "passive", d=10.16)
s.pin_power(HDR6, "5", 360, 240, 0, "GND", d=10.16)
s.pin_power(HDR6, "6", 360, 240, 0, "GND", d=15.24)

# REFERANSLAR 900'LU SERIDE. Once R800'den basladim, ama cnt() de
# R800'den sayiyor: zayiflaticinin cekme direnci ile buradaki 50R
# sonlandirma AYNI referansi aldi ve KiCad ikisini tek parca sandi —
# netlist'te REF10_RAW ile ATT1_C0 ayni bilesenin iki bacagi olarak
# gorundu. Elle referans yazarken sayacin araligindan uzak dur.
# ---- harici 10 MHz: SMA -> 50R -> AC kuplaj -> KOMPARATOR -> FPGA
# Ilk cizimde komparator YOKTU: SMA -> 50R -> 100nF -> FPGA. Iki hata
# birdendi. (1) Kondansatorden sonra hicbir DC yolu yok, bacak havada
# kaliyor. (2) DC bias eklense bile 3.3 V LVCMOS esikleri (VIH ~2.0 V,
# VIL ~0.8 V) 0.5 Vpp sinusle asilmiyor — giris hic anahtarlamaz.
CMP = "Comparator:TLV3501AIDBV"
FCMP = "Package_TO_SOT_SMD:SOT-23-6"
s.sym(CONN, "J61", "SMA 10MHz ref", 350, 290, fp=FSMA)
s.pin_label(CONN, "1", 350, 290, 0, "REF10_RAW", "output")
s.pin_power(CONN, "2", 350, 290, 0, "GND")
s.sym(R, "R900", "50R 1%", 372, 290, rot=90, fp=FR)
s.pin_label(R, "1", 372, 290, 90, "REF10_RAW", "passive")
s.pin_power(R, "2", 372, 290, 90, "GND")
s.sym(C, "C900", "100nF", 392, 290, rot=90, fp=FC)
s.pin_label(C, "1", 392, 290, 90, "REF10_RAW", "passive")
s.pin_label(C, "2", 392, 290, 90, "REF10_AC", "passive")

# orta gerilim bolucu: hem sinyal bacagina hem referans bacagina
for i, (net, ref_hi, ref_lo) in enumerate(
        [("REF10_AC", "R901", "R902"), ("REF10_BIAS", "R903", "R904")]):
    bx = 415 + i * 30
    s.sym(R, ref_hi, "10k", bx, 275, rot=90, fp=FR)
    s.pin_label(R, "1", bx, 275, 90, "+3V3", "input")
    s.pin_label(R, "2", bx, 275, 90, net, "passive")
    s.sym(R, ref_lo, "10k", bx, 295, rot=90, fp=FR)
    s.pin_label(R, "1", bx, 295, 90, net, "passive")
    s.pin_power(R, "2", bx, 295, 90, "GND")
s.sym(C, "C901", "100nF", 475, 285, rot=90, fp=FC)
s.pin_label(C, "1", 475, 285, 90, "REF10_BIAS", "passive")
s.pin_power(C, "2", 475, 285, 90, "GND")

s.sym(CMP, "U62", "TLV3501AIDBVR", 505, 325, fp=FCMP)
# TLV3501 SOT-23-6 dizilimi: 1 IN-, 2 V-, 3 IN+, 4 V+, 5 OUT, 6 ~SHDN.
# Once 1'i cikis, 5'i besleme sanmistim — ERC "cikis ile guc cikisi
# baglanmis" diye yakaladi. Boyle baglansaydi 3.3 V rayina komparator
# cikisi surulurdu.
s.pin_label(CMP, "5", 505, 325, 0, "REF10_IN", "output")
s.pin_label(CMP, "3", 505, 325, 0, "REF10_AC", "input")
s.pin_label(CMP, "1", 505, 325, 0, "REF10_BIAS", "input")
s.pin_label(CMP, "4", 505, 325, 0, "+3V3", "input")
s.pin_power(CMP, "2", 505, 325, 0, "GND")
s.pin_label(CMP, "6", 505, 325, 0, "+3V3", "input")   # ~SHDN aktif-dusuk
s.sym(C, "C902", "100nF", 545, 300, rot=90, fp=FC)
s.pin_label(C, "1", 545, 300, 90, "+3V3", "input")
s.pin_power(C, "2", 545, 300, 90, "GND")

s.text("HARICI 10 MHz — SMA, 50R sonlandirma, AC kuplaj, KOMPARATOR.\\n"
       "Iki 10k bolucu orta gerilim (1.65 V) uretiyor: sinyal bacagi o\\n"
       "gerilim etrafinda salınıyor, referans bacagi ayni gerilimde sabit\\n"
       "(100nF ile susturulmus). Komparator birkac yuz mV'luk sinusu\\n"
       "tam salinimli kare dalgaya ceviriyor.\\n\\n"
       "TLV3501AIDBVR, LCSC C193413, $1.57, 1850 stok, SOT-23-6.\\n"
       "4.5 ns gecikme, rail-to-rail giris, tek 3.3 V besleme.\\n"
       "Alternatifi FPGA'nin diferansiyel girisiydi ama bir pin daha\\n"
       "isterdi ve banka 1 zaten 32/32 dolu — bir dolar, pin planindan ucuz.\\n\\n"
       "Histerezis direnci konmadi; TLV3501'in dahili histerezisi 6 mV,\\n"
       "temiz referans kaynagi icin yeter. Gurultuluyse cikistan IN+'ya\\n"
       "1M pozitif geri besleme eklenir.", 350, 345, 1.3)

# ================================================================== VCXO DAC
s.text("VCXO Vc — SPI DAC", 330, 365, 1.6)
s.sym(HDR6, "J62", "DAC modul", 360, 385, fp=FHDR6)
for p, net in [("1", "+3V3_CLK"), ("2", "VCXO_CS"), ("3", "VCXO_CLK"),
               ("4", "VCXO_DIN"), ("5", "VCXO_VC")]:
    s.pin_label(HDR6, p, 360, 385, 0, net, "passive", d=10.16)
s.pin_power(HDR6, "6", 360, 385, 0, "GND", d=15.24)

s.text("DAC parcasi HENUZ SECILMEDI — 16 bit, dusuk gurultulu, SPI.\\n"
       "Vc gurultusu dogrudan faz gurultusune donusuyor, o yuzden\\n"
       "beslemesi +3V3_CLK (VCXO'nun kendi LDO'su). Baslik olarak\\n"
       "cizildi; parca secilince yerine konacak.", 330, 398, 1.3)

# ================================================================== hata ayiklama
s.text("HATA AYIKLAMA UART", 480, 215, 1.6)
s.sym("Connector_Generic:Conn_01x04", "J64", "UART 3.3V", 500, 240,
      fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")
for p_, net in [("1", "+3V3"), ("2", "DBG_RX"), ("3", "DBG_TX")]:
    s.pin_label("Connector_Generic:Conn_01x04", p_, 500, 240, 0, net,
                "passive", d=10.16)
s.pin_power("Connector_Generic:Conn_01x04", "4", 500, 240, 0, "GND", d=10.16)
s.text("3.3 V TTL, CP2102/FT232 tarzi ucuz donusturucu takilir.\\n"
       "Bringup'ta FPGA icindeki yazilim buradan konusuyor;\\n"
       "JTAG'den once calisan tek gozlem yolu.", 470, 262, 1.3)

# ================================================================== kart arasi
s.text("KART ARASI — A <-> C, NETLIST.md §8", 16, 355, 2.0)
s.sym(HDR, "J63", "C kartina", 70, 390, fp=FHDR)
pairs = [("1", "+3V3"), ("2", "GND_HDR"), ("3", "RLY_SER"), ("4", "GND_HDR"),
         ("5", "RLY_SRCLK"), ("6", "GND_HDR"), ("7", "RLY_RCLK"), ("8", "GND_HDR"),
         ("9", "TR1"), ("10", "GND_HDR"), ("11", "TR2"), ("12", "GND_HDR"),
         ("13", "TR3"), ("14", "GND_HDR"), ("15", "TR4"), ("16", "GND_HDR"),
         ("17", "ATT_DATA"), ("18", "ATT_CLK"), ("19", "ATT1_LE"),
         ("20", "VIN_PROT")]
for p_, net in pairs:
    s.pin_label(HDR, p_, 70, 390, 0, net, "passive", d=7.62)

# ikinci baslik: C kartinin kalan LE hatlari
s.sym(HDR6, "J65", "C kartina #2", 190, 390, fp=FHDR6)
for p_, net in [("1", "ATT2_LE"), ("2", "ATT3_LE"), ("3", "ATT4_LE"),
                ("4", "VIN_PROT"), ("5", "+3V3")]:
    s.pin_label(HDR6, p_, 190, 390, 0, net, "passive", d=10.16)
s.pin_power(HDR6, "6", 190, 390, 0, "GND", d=15.24)

# ucuncu baslik: D karti (PA)
s.text("D KARTINA (PA)", 260, 355, 1.6)
s.sym(HDR, "J66", "D kartina", 300, 390, fp=FHDR)
# D karti yalniz A'dan bunlari aliyor. Role zinciri (SER/SRCLK/RCLK)
# D'ye C KARTINDAN gidiyor — zincirin sekizinci halkasi orada.
# ADC_SDIO ortak MISO: AD9251'in cift yonlu SDIO'su ve PA'nin
# MCP3208'inin Dout'u ayni hatta. Ikisi de yalnizca kendi CS'i
# secildiginde suruyor; firmware ikisini ayni anda secmeyecek.
dpairs = [("1", "+3V3"), ("2", "GND_HDR"), ("3", "ATT_DATA"), ("4", "GND_HDR"),
          ("5", "ATT_CLK"), ("6", "GND_HDR"), ("7", "PA_ATT_LE"), ("8", "GND_HDR"),
          ("9", "BIAS_CS1"), ("10", "GND_HDR"), ("11", "BIAS_CS2"),
          ("12", "GND_HDR"), ("13", "PA_ADC_CS"), ("14", "GND_HDR"),
          ("15", "PA_INHIBIT"), ("16", "GND_HDR"), ("17", "ADC_SDIO"),
          ("18", "GND_HDR"), ("19", "GND_HDR"), ("20", "GND_HDR")]
for p_, net in dpairs:
    s.pin_label(HDR, p_, 300, 390, 0, net, "passive", d=7.62)

s.text("PA'nin istedigi 13 sinyal 5 YENI HATLA karsilandi:\\n"
       "  ATT_DATA / ATT_CLK  -> C kartiyla ORTAK, yeni hat yok\\n"
       "  ADC_SDIO            -> ortak MISO, AD9251'in hatti\\n"
       "  role zinciri        -> D'ye C KARTINDAN gidiyor, A'dan degil\\n"
       "  PA_ATT_LE, BIAS_CS1, BIAS_CS2, PA_ADC_CS, PA_INHIBIT -> yeni\\n\\n"
       "FLANGE_T, FWD_LOG, REV_LOG analog olcumleri A kartina GELMIYOR:\\n"
       "D kartinda bir MCP3208 (8 kanal 12 bit SPI ADC) var, ayni seri\\n"
       "yolu paylasiyor ve PA_ADC_CS ile seciliyor. Uc analog hat yerine\\n"
       "bir sayisal hat.", 260, 425, 1.3)

s.sym(R, "R801", "0R", 140, 392, fp=FR)
s.pin_label(R, "1", 140, 392, 0, "GND_HDR", "passive")
s.pin_power(R, "2", 140, 392, 0, "GND")

s.text("HER SINYALIN YANINDA TOPRAK. 2.54 mm baslikta bitisik toprak\\n"
       "donus yolunu kisaltiyor; role hatlari 12 V anahtarliyor ve\\n"
       "kenarlari sert, yanindaki RF'e kuplaj yapmasin.\\n"
       "ATT2 hatlari ve +12 V ikinci baslikta (yerlesimde eklenecek).\\n"
       "RF kart arasi koaks kuyrukla — baslikla DEGIL.\\n\\n"
       "Toprak GND_HDR uzerinden 0R ile ana topraga: tek nokta,\\n"
       "gerekirse ayrilabiliyor.", 16, 365, 1.3)

s.write(os.path.join(HERE, "08_control.kicad_sch"))
print("08_control.kicad_sch yazildi")
