#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""06_ethernet: 2x RTL8211F + 2x HR911105A, banka 3. Kaynak: ../NETLIST.md §5."""
import json, os
from schlib import Sheet, unit_pins, yol_esle

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

P = "dogrudan-sdr:RTL8211F"
# AYAK IZI YANLIS PARCAYA AITTI.
#
# QFN-48_6x6mm_P0.4mm yaziyordu. RTL8211F(I)-CG ise WQFN-40-EP(5x5):
# KIRK pin, 5x5 mm govde. Yani pin sayisi, govde olcusu ve adim,
# ucu de tutmuyordu. Cip bu ped desenine LEHIMLENEMEZ — kart
# uretilse bile iki ethernet portu monte edilemezdi.
#
# Belirti nasil gorunuyordu: kartta 42-49 pedleri agsizdi. Once
# "sembolde eksik pin var" diye okudum ve sembole EP ekledim; yanlis
# taniydi. Sembol 41 pinle DOGRUYDU (40 bacak + acik ped 41);
# fazlalik ayak izindeydi.
#
# EP olcusu 3.6x3.6 secildi ve ARTIK DOGRULANDI.
# Realtek RTL8211F(I)/RTL8211FD(I) veri sayfasi Rev 1.1, s.64,
# "Mechanical Dimensions" tablosu (JEDEC MO-220): govde D/E 5.00 BSC,
# adim e 0.40 BSC, acik ped D2/E2 = 3.45 / 3.70 / 3.95 mm
# (asgari / nominal / azami). Ped 3.6 mm, yani nominalin altinda ama
# asgarinin uzerinde — istenen taraf: kucuk ped her zaman lehimlenir,
# buyugu bacaklara kopru atabilir. Termal via'li surum degil,
# parca ~1 W harciyor.
# TERMAL VIA'LAR KALDIRILDI — OLCULDU, GEREKMIYOR VE ZARARLI.
# KiCad'in "_ThermalVias" surumu acik pedin icine DELIKLI (PTH) via
# koyuyor. Olculen sonuc: bu via'lar ile komsu sinyal pedi arasindaki
# bosluk 0.229 mm. Yonlendirici DSN sinif kurallarinda guc aglarini
# 300 um'de tutuyor, yani bu ciftler HER TURDA ihlal sayiliyor ve
# ihlal geometriden geldigi icin COZULEMIYOR: D kartinin
# yonlendirme gunlugunde ihlal sayisi turdan tura sabit
# (152, 152, 152) kalirken yonlendirilmemis ag sayisi duşuyor.
#
# Via'lar zaten gerekmiyor: acik ped GND'ye bagli ve F.Cu'da GND
# dokumu var, yani ped dokume oturuyor. RTL8211F ~0.5 W harciyor; bu gercek bir isi ama A karti ALTI
# katmanli ve In1/In4 tam toprak duzlemi — dokum lateral yayilim
# icin yeterli, ve gerekirse dikis.py hedefli via atiyor.
# Dokumun ulasamadigi yere kisa toprak sapi gerekirse onu
# yonlendirmeden SONRA dikis.py ekliyor — sabit izgarali footprint
# via'sindan daha esnek.
FP = "Package_DFN_QFN:QFN-40-1EP_5x5mm_P0.4mm_EP3.6x3.6mm"
J = "dogrudan-sdr:HR911130A"
FJ = "dogrudan-sdr:RJ45_Hanrun_HR911130A"
E = "dogrudan-sdr:ECP5-BGA256"
FE = ("Package_BGA:BGA-256_14.0x14.0mm_Layout16x16_P0.8mm_"
      "Ball0.45mm_Pad0.32mm_NSMD")
# DORT PEDLI KRISTALIN SEMBOLU DE DORT PINLI OLMALI.
# Once "Device:Crystal" yaziyordu: IKI pinli bir sembol, ama ayak izi
# Crystal_SMD_3225-4Pin. Sonuc, kartta olculdu: ped 3 ve ped 4 AGSIZ
# kaldi, ve daha kotusu XO ped 2'ye baglandi.
#
# 3225 dizilimi capraz: ped 1 ve 3 kristalin UCLARI, ped 2 ve 4 metal
# GOVDE (KiCad'in "GND24" adi tam bunu anlatiyor). Yani XO gercekte
# kristale degil govdeye gidiyordu — ve XI ile XO arasinda kristal
# YOKTU. Iki PHY'nin de 25 MHz saati olusmaz, yani ethernet hic
# calismaz. Kart uzerinde belirtisi "PHY olu"; sebebi aramak gunler
# alirdi cunku semada her sey bagli gorunuyor.
XTAL = "Device:Crystal_GND24"
FX = "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm"
R, C, L = "Device:R", "Device:C", "Device:L"
LED = "Device:LED"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"
FL = "Inductor_SMD:L_0805_2012Metric"
FLED = "LED_SMD:LED_0603_1608Metric"

s = Sheet("06_ethernet", "Ethernet x2", UU["06_ethernet"],
          "RTL8211F x2 + HR911105A x2, RGMII banka 3", paper="A1")
# A1: iki PHY + destek devreleri + RJ45'ler + FPGA bankasi A2'ye
# sigmadi, bloklar sayfa cercevesinin disina tasti.

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{599 + nr[0]}"


# strap tablosu: NETLIST.md §5.2. PHY adresi 0 ve 1.
STRAP = {
    "22": ("PHYAD0", "dn", "up"),
    "27": ("PHYAD1", "dn", "dn"),
    "26": ("PHYAD2", "dn", "dn"),
    "24": ("TXDLY", "up", "up"),
    "25": ("RXDLY", "up", "up"),
    "23": ("PLLOFF", "dn", "dn"),
}
RGMII = {"20": "TXC", "18": "TXD0", "17": "TXD1", "16": "TXD2", "15": "TXD3",
         "19": "TXCTL", "27": "RXC", "25": "RXD0", "24": "RXD1", "23": "RXD2",
         "22": "RXD3", "26": "RXCTL"}


def phy(ref, x, y, n, jref, jx, jy, sx, sy):
    # ---------------- birim 1: RGMII + yonetim
    s.sym(P, ref, "RTL8211FI-CG", x, y, fp=FP, unit=1)
    for pn, sig in sorted(RGMII.items(), key=lambda z: int(z[0])):
        shape = "input" if sig.startswith("TX") else "output"
        s.pin_label(P, pn, x, y, 0, f"PHY{n}_{sig}", shape, d=10.16)
    s.pin_label(P, "13", x, y, 0, "MDC", "input", d=15.24)
    s.pin_label(P, "14", x, y, 0, "MDIO", "bidirectional", d=20.32)
    s.pin_label(P, "12", x, y, 0, f"PHY{n}_nRST", "input", d=25.4)
    s.pin_label(P, "31", x, y, 0, f"PHY{n}_nINT", "output", d=30.48)
    # pin 28 sembolun USTUNDE (rot 270). Uzun saplama sayfa disina
    # tasiyordu (y = -17.78). Dikey pinlerde d kisa tutuluyor.
    s.pin_label(P, "28", x, y, 0, "+1V8", "input", d=7.62)

    # ---------------- strap dirençleri
    for i, (pn, (name, p1, p2)) in enumerate(sorted(STRAP.items(),
                                                    key=lambda z: int(z[0]))):
        up = (p1 if n == 1 else p2) == "up"
        # ARALIK 25.4. 18 mm denedim: g() ile 17.78'e oturdu ve komsu
        # direnclerin 5.08'lik saplamalari TAM UC UCA degdi (121.92'de).
        # Alti strap birbirine ve +1V8'e kisa devre oldu.
        rx, ry = sx + i * 25.4, sy
        s.sym(R, cnt("R"), "1k", rx, ry, rot=90, fp=FR)
        s.pin_label(R, "1" if up else "2", rx, ry, 90,
                    "+1V8" if up else "GND_STRAP", "passive")
        s.pin_label(R, "2" if up else "1", rx, ry, 90,
                    f"PHY{n}_{RGMII[pn]}", "passive")

    # ---------------- birim 2: analog, guc, saat, MDI
    ax, ay = x, y + 120
    s.sym(P, ref, "RTL8211FI-CG", ax, ay, fp=FP, unit=2)
    # 3, 8, 11, 21, 29, 38, 40 hepsi UST kenarda; 41 alt kenarda.
    # Saplamalar dikey, en fazla 12.7 — daha uzunu ust komsu bloklara
    # ya da sayfa disina giriyor.
    for pn in ("11", "40"):
        s.pin_label(P, pn, ax, ay, 0, "+3V3", "input", d=5.08)
    s.pin_label(P, "29", ax, ay, 0, "+3V3", "input", d=10.16)
    for pn in ("3", "8", "38"):
        s.pin_label(P, pn, ax, ay, 0, f"PHY{n}_1V0", "input", d=5.08)
    s.pin_label(P, "21", ax, ay, 0, f"PHY{n}_1V0", "input", d=10.16)
    s.pin_label(P, "30", ax, ay, 0, f"PHY{n}_REGOUT", "output", d=27.94)
    s.pin_power(P, "41", ax, ay, 0, "GND", d=5.08)
    # 41 = ACIK PED. QFN-40'in altindaki 3.6x3.6 mm ped; hem tek
    # termal yol hem ic regulatorun toprak donusu.
    s.pin_label(P, "39", ax, ay, 0, f"PHY{n}_RSET", "passive", d=33.02)
    s.pin_label(P, "36", ax, ay, 0, f"PHY{n}_XI", "input", d=38.1)
    s.pin_label(P, "37", ax, ay, 0, f"PHY{n}_XO", "output", d=43.18)
    s.nc(*s.P(P, "35", ax, ay))                     # CLKOUT bosta
    for i in range(4):
        s.pin_label(P, str([1, 4, 6, 9][i]), ax, ay, 0,
                    f"PHY{n}_MDI{i}P", "bidirectional", d=7.62)
        s.pin_label(P, str([2, 5, 7, 10][i]), ax, ay, 0,
                    f"PHY{n}_MDI{i}N", "bidirectional", d=12.7)
    # LED / CFG bacaklari
    s.pin_label(P, "32", ax, ay, 0, f"PHY{n}_CFGEXT", "passive", d=17.78)
    s.pin_label(P, "33", ax, ay, 0, f"PHY{n}_LED1", "passive", d=22.86)
    s.pin_label(P, "34", ax, ay, 0, f"PHY{n}_LED2", "passive", d=27.94)

    # REG_OUT bobini: dahili anahtarlamali regulator cikisi
    lx, ly = sx, sy + 60
    s.sym(L, cnt("L"), "4.7uH", lx, ly, fp=FL)
    s.pin_label(L, "1", lx, ly, 0, f"PHY{n}_REGOUT", "input")
    s.pin_label(L, "2", lx, ly, 0, f"PHY{n}_1V0", "output")
    # 1.0 V rayi bobinden geciyor, bobin pasif: ERC ray icin bir guc
    # kaynagi goremiyor. Bayrak, gercek bir baglanti degil.
    s.glabel(f"PHY{n}_1V0", lx, ly + 20, "input")
    s.wire(lx, ly + 20, lx, ly + 13.65)
    s.pwr_flag(lx, ly + 13.65)
    s.sym(C, cnt("C"), "10uF X5R", lx + 22, ly, fp=FC)
    s.pin_label(C, "1", lx + 22, ly, 0, f"PHY{n}_1V0", "passive")
    s.pin_power(C, "2", lx + 22, ly, 0, "GND")
    s.sym(R, cnt("R"), "2.2k 1%", lx + 44, ly, fp=FR)
    s.pin_label(R, "1", lx + 44, ly, 0, f"PHY{n}_RSET", "passive")
    s.pin_power(R, "2", lx + 44, ly, 0, "GND")
    s.sym(R, cnt("R"), "10k", lx + 66, ly, fp=FR)
    s.pin_label(R, "1", lx + 66, ly, 0, "+3V3", "input")
    s.pin_label(R, "2", lx + 66, ly, 0, f"PHY{n}_CFGEXT", "passive")

    # ---------------- kristal, PHY basina AYRI
    cx, cy = sx, sy + 100
    # DEGERE YUK KAPASITESI YAZILIYOR: "25MHz" TEK BASINA EKSIK.
    # Yandaki iki 18 pF bu kristale gore secildi. CL = 18*18/(18+18)
    # + Cstray = 9 + ~3 = 12 pF, yani BOM'daki C9006'nin (YXC
    # X322525MOB4SI) 12 pF yuk kapasitesiyle tutuyor.
    # Yuk kapasitesi yazilmazsa satin alan ayni govdede 20 pF'lik
    # bir kristal alabilir; o zaman salinim ~24 ppm yukarida kosar
    # ve 802.3'un +-50 ppm butcesi kristal toleransiyla birlikte
    # tasar. Ethernet "bazen link kuruyor" diye arizalanir.
    # Ilk prototipte 25 MHz frekans meta ile olculup 18 pF gerekirse
    # 15/16 pF'e cekilecek (URETIM notu).
    s.sym(XTAL, cnt("Y"), "25MHz CL12pF", cx, cy, fp=FX)
    s.pin_label(XTAL, "1", cx, cy, 0, f"PHY{n}_XI", "passive")
    s.pin_label(XTAL, "3", cx, cy, 0, f"PHY{n}_XO", "passive")
    # Govde pedleri topraga: hem ekranlama hem mekanik tutunma.
    # Bosta birakilan metal govde 25 MHz'te anten gibi davraniyor.
    s.pin_power(XTAL, "2", cx, cy, 0, "GND")
    s.pin_power(XTAL, "4", cx, cy, 0, "GND")
    for i, net in enumerate((f"PHY{n}_XI", f"PHY{n}_XO")):
        s.sym(C, cnt("C"), "18pF", cx + 25 + i * 20, cy, fp=FC)
        s.pin_label(C, "1", cx + 25 + i * 20, cy, 0, net, "passive")
        s.pin_power(C, "2", cx + 25 + i * 20, cy, 0, "GND")

    # ---------------- LED'ler MAGJACK'IN ICINDE
    # Once ayrik 0603 LED koymustum; HR911130A'nin govdesinde zaten
    # yesil ve sari LED var (veri sayfasi s.2: 568 nm / 585 nm, 20 mA).
    # Dort ayrik LED ve dort direnc kalkti, dort direnc kaldi.
    for i, (nm, a, k) in enumerate([("LED1", "11", "12"), ("LED2", "14", "13")]):
        ex, ey = sx + i * 30, sy + 140
        s.sym(R, cnt("R"), "330R", ex, ey, rot=90, fp=FR)
        s.pin_label(R, "1", ex, ey, 90, "+3V3", "input")
        s.pin_label(R, "2", ex, ey, 90, f"PHY{n}_{nm}_A", "passive")

    # ---------------- RJ45 + manyetik
    s.sym(J, jref, "HR911130A", jx, jy, fp=FJ)
    # Cift eslesmesi SIRALI DEGIL, ic ice (veri sayfasi s.1):
    #   MDI0 P2/P3 · MDI1 P4/P7 · MDI2 P5/P6 · MDI3 P8/P9
    for pn, net in [("2", f"PHY{n}_MDI0P"), ("3", f"PHY{n}_MDI0N"),
                    ("4", f"PHY{n}_MDI1P"), ("7", f"PHY{n}_MDI1N"),
                    ("5", f"PHY{n}_MDI2P"), ("6", f"PHY{n}_MDI2N"),
                    ("8", f"PHY{n}_MDI3P"), ("9", f"PHY{n}_MDI3N")]:
        s.pin_label(J, pn, jx, jy, 0, net, "passive", d=10.16)
    # P1 = cip tarafi orta uclarin ortak dugumu. Toprakla DOGRUDAN
    # birlestirilmiyor: 100nF ile AC toprakta, DC yolu yok.
    s.pin_label(J, "1", jx, jy, 0, f"PHY{n}_CT", "passive", d=7.62)
    s.sym(C, cnt("C"), "100nF 2kV", jx - 20, jy + 30, rot=90, fp=FC)
    s.pin_label(C, "1", jx - 20, jy + 30, 90, f"PHY{n}_CT", "passive")
    s.pin_label(C, "2", jx - 20, jy + 30, 90, "CHASSIS", "passive")
    # P10 = govde / Bob Smith dugumu, icerideki 1000pF 2kV uzerinden
    s.pin_label(J, "10", jx, jy, 0, "CHASSIS", "passive", d=12.7)
    # KALKAN KULAKLARI DA CHASSIS'E. Sembolde bu dort ped yoktu ve
    # kartta AGSIZ bakir olarak duruyorlardi: kablonun ekrani
    # konnektorun govdesinde bitiyordu, gidecek bir yeri yoktu.
    # Ekranin isi bu — gurultuyu tasiyip TEK bir noktadan kasaya
    # birakmak. Dordu birden CHASSIS'e; CHASSIS de asagida tek
    # noktadan GND'ye bagli.
    for pn in ("SH1", "SH2", "SH3", "SH4"):
        s.pin_label(J, pn, jx, jy, 0, "CHASSIS", "passive", d=17.78)
    # dahili LED'ler
    for pn, net in [("11", f"PHY{n}_LED1_A"), ("12", f"PHY{n}_LED1"),
                    ("14", f"PHY{n}_LED2_A"), ("13", f"PHY{n}_LED2")]:
        s.pin_label(J, pn, jx, jy, 0, net, "passive", d=10.16)


s.text("ETHERNET x2 — RTL8211FI-CG, RGMII, banka 3", 16, 14, 2.0)
s.text("Iki bagimsiz gigabit arayuz. Sahada tek kablo yeterli; labda\\n"
       "biri ham IQ akisi, digeri kontrol/telemetri — akislar birbirinin\\n"
       "gecikmesini bozmuyor.", 16, 20, 1.35)

# x=50 denedim: sol taraftaki RGMII etiketleri (d=35.56'ya kadar)
# sayfa cercevesinin disina tasti. 90'dan basliyor.
phy("U40", 90, 60, 1, "J40", 200, 330, 165, 45)
phy("U41", 460, 60, 2, "J41", 570, 330, 535, 45)

# ------------------------------------------------------------------ ortak
s.text("MDIO ORTAK YOL", 740, 40, 1.6)
s.sym(R, "R690", "1.5k", 750, 55, rot=90, fp=FR)
s.pin_label(R, "1", 750, 55, 90, "+1V8", "input")
s.pin_label(R, "2", 750, 55, 90, "MDIO", "passive")
s.text("MDC ve MDIO iki PHY'da ORTAK. Adresler strap ile ayrilmis:\\n"
       "PHY-1 = 0, PHY-2 = 1. MDIO acik drenaj, 1.5k ile 1.8 V'a cekiliyor.\\n"
       "Cekme direnci DVDD_RG seviyesinde olmali (1.8 V), 3.3 V DEGIL.",
       740, 70, 1.3)

s.pin_label(R, "1", 750, 100, 0, "GND_STRAP", "passive")
s.sym(R, "R691", "0R", 750, 100, fp=FR)
s.pin_power(R, "2", 750, 100, 0, "GND")
s.text("Asagi cekilen strap'ler GND_STRAP uzerinden 0R ile toprakta.\\n"
       "Tek noktadan ayrilabiliyor: adres catismasi cikarsa direnc\\n"
       "sokulup baska kombinasyon denenir.", 740, 112, 1.3)

# ---------------------------------------------------------------- sase bagi
# CHASSIS YUZEN ADAYDI. Uzerinde sadece J40.10, J41.10 ve iki 100nF/2kV
# vardi; hicbir yerde topraga ya da kasaya baglanmiyordu. Yuzen bir
# "sase" agi ekran icin en kotu durum: ekranin ustundeki gurultunun
# akacak yolu yok, ag antene donusuyor ve iki magjack birbirine
# kapasitif bagli kaliyor.
#
# SISTEMDE TEK SASE REFERANS NOKTASI VAR: C KARTI (anten
# konnektorleri orada, kaplamali montaj deligi GND'ye bagli). A ve
# D'nin montaj delikleri KAPLAMASIZ — ikinci bir metal temas noktasi
# toprak dongusu demek, dongu de 50 Hz ve anahtarlama gurultusunu
# alis onucuna tasir.
# Bu kartta ekran topraga ELEKTRIKSEL olarak buradan, tek noktadan
# baglaniyor: R692 0R. Olcum sirasinda ayrilabilsin diye direnc,
# duz bakir degil.
s.pin_label(R, "1", 750, 128, 0, "CHASSIS", "passive")
s.sym(R, "R692", "0R", 750, 128, fp=FR)
s.pin_power(R, "2", 750, 128, 0, "GND")
s.text("SASE BAGI — RJ45 kalkani ve orta uc dugumu CHASSIS'te; CHASSIS\\n"
       "topraga TEK NOKTADAN, R692 (0R) ile bagli. Montaj delikleri bu\\n"
       "kartta KAPLAMASIZ: sase referansi C kartinda, orada anten\\n"
       "konnektorlerinin dibindeki delik kaplamali ve GND'de.\\n"
       "Iki karttan da kasaya baglanirsa toprak dongusu olusur.",
       740, 355, 1.3)

s.text("STRAP DIRENCLERI 1k (NETLIST.md §5.2)\\n"
       "Bu alti bacak hem RGMII verisi hem reset anindaki strap.\\n"
       "  TXDLY / RXDLY yukari  -> 2 ns ic gecikmeyi PHY uretiyor,\\n"
       "                           FPGA tarafinda gecikme kurmaya gerek yok\\n"
       "  PHYAD0 PHY-2'de yukari -> adresler 0 ve 1\\n"
       "  PLLOFF asagi           -> ALDPS'te PLL acik kalsin\\n"
       "1k: RGMII sinyal butunlugunu bozmayacak kadar yuksek, strap'i\\n"
       "belirleyecek kadar dusuk. 100R olsa surucuyu yorardi, 10k olsa\\n"
       "kacak akim strap'i belirsiz birakirdi.", 740, 145, 1.3)

s.text("REG_OUT BOBINI — datasheet s.46-53\\n"
       "PHY'nin dahili anahtarlamali regulatoru 1.0 V rayini kendi uretiyor;\\n"
       "bobin ve cikis kondansatoru DISARIDA. 4.7uH + 10uF X5R.\\n"
       "** Y5V KULLANMA ** — datasheet dalgalanma olcumlerinde acikca\\n"
       "uyariyor; Y5V'nin DC bias altinda kapasitesi cokuyor.", 740, 210, 1.3)

s.text("SAAT: PHY BASINA AYRI KRISTAL\\n"
       "25 MHz X322525MOB4SI, LCSC C9006. Iki PHY'a tek kristal paylastirmak\\n"
       "denenmedi — her PHY'nin kendi osilator devresi var, paylasim\\n"
       "yuk kapasitesini bozar. 5 kurusluk parca icin risk alinmiyor.\\n"
       "CLKOUT (35) bosta.", 740, 250, 1.3)

s.text("** PARCA DEGISTI: HR911105A -> HR911130A ** (veri sayfasi geldi)\\n"
       "Veri sayfasi geldi ve HR911105A'nin kapaginda 'for 10/100Base-T NIC\\n"
       "Applications' yaziyor. Semasinda SADECE IKI cift sargi var (TD, RD);\\n"
       "gigabit DORT cift ister. O parcayla iki GbE portu 100 Mbit'e duserdi\\n"
       "— aletin veri borusu on kat daralirdi, 4 kanal IQ akisi imkansiz.\\n"
       "HR911130A ayni ailenin gigabit uyesi: LCSC C54408, $1.58, 6005 stok.\\n\\n"
       "BACAK SAYISI 12 DEGIL 14 — ayak izi de degisti, KiCad'de yoktu,\\n"
       "veri sayfasi s.2 montaj deseninden uretildi (lib/gen_fp).\\n"
       "Cift eslesmesi SIRALI DEGIL, ic ice: MDI0 P2/P3, MDI1 P4/P7,\\n"
       "MDI2 P5/P6, MDI3 P8/P9. Sirali baglasaydik iki cift takas olurdu.\\n\\n"
       "P1 = cip tarafi orta uclarin ortak dugumu, 100nF 2kV ile CHASSIS'e.\\n"
       "P10 = govde, icerideki 1000pF 2kV Bob Smith agina gidiyor.\\n"
       "LED'ler MAGJACK'IN ICINDE (568/585 nm, 20 mA) — ayrik LED'ler kalkti.\\n\\n"
       "** AYAK IZI BASMADAN ONCE 1:1 CIKTI ALINIP PARCA UZERINE KONACAK. **\\n"
       "Cizimden olculdu; delik capları ve aciklıklar dogru ama tek\\n"
       "dogrulama yolu fiziksel karsilastirma.\\n\\n"
       "Kalkan CHASSIS agina: dort kalkan pedi (SH1-SH4) + P10 CHASSIS'te,\\n"
       "CHASSIS topraga R692 (0R) ile TEK NOKTADAN bagli. Ayrintisi\\n"
       "sagda, sase bagi notunda.", 740, 300, 1.35)

# ------------------------------------------------------------------ FPGA
s.text("FPGA BANKA 3 — RGMII x2", 300, 400, 2.0)
B3X, B3Y = 690, 460
s.sym(E, "U10", "LFE5U-25F-7BG256I", B3X, B3Y, fp=FE, unit=5)
B3 = unit_pins(E, 5)
nets3 = []
for n in (1, 2):
    for sig in ("TXC", "TXD0", "TXD1", "TXD2", "TXD3", "TXCTL",
                "RXC", "RXD0", "RXD1", "RXD2", "RXD3", "RXCTL"):
        nets3.append(f"PHY{n}_{sig}")
nets3 += ["PHY1_nRST", "PHY2_nRST", "PHY1_nINT", "PHY2_nINT", "MDC", "MDIO"]
# Banka 3'un iki bos pini de LED'e
nets3 += ["LED_TX", "LED_DATA"]
io3 = sorted(n for n, nm in B3.items() if nm.startswith("PR"))
assert len(nets3) == 32 and len(io3) == 32, (len(nets3), len(io3))
for p, net in yol_esle(io3, nets3, "PHY1", "PHY2"):
    s.pin_label(E, p, B3X, B3Y, 0, net, "bidirectional", d=7.62)
for p in io3[len(nets3):]:
    s.nc(*s.P(E, p, B3X, B3Y))
for n, nm in sorted(B3.items()):
    if nm.startswith("VCCIO"):
        s.pin_label(E, n, B3X, B3Y, 0, "+1V8", "input", d=15.24)

s.text("BANKA 3: 24 RGMII + 2 reset + 2 kesme + MDC/MDIO = 30/32.\\n"
       "Iki pin bos — bu kartta tek marj burasi.\\n"
       "VCCIO3 = +1V8, PHY'nin DVDD_RG'siyle ayni.\\n\\n"
       "UZUNLUK ESLEME: TXC ile TXD[3:0]+TXCTL grubu +-5 mm; RXC ile RXD\\n"
       "grubu ayni. Gruplar ARASI esleme gerekmiyor — RGMII kaynak-senkron,\\n"
       "her yon kendi saatini tasiyor.\\n"
       "TXC/RXC saat-yetenekli pine dusmeli, liste Lattice pinout'undan\\n"
       "yeniden siralanacak.", 300, 412, 1.3)

# ---- PHY basina ayristirma
s.text("AYRISTIRMA — PHY basina", 90, 480, 2.0)
for i, n in enumerate((1, 2)):
    bx = 95 + i * 330
    s.decaps("+3V3", 3, "100nF", bx, 500, 700 + i * 20, per_row=3)
    s.decaps(f"PHY{n}_1V0", 4, "100nF", bx + 60, 500, 703 + i * 20, per_row=4)
    s.decaps("+1V8", 1, "100nF", bx + 140, 500, 707 + i * 20)
s.text("Cip basina: AVDD33 (11, 40) ve DVDD33 (29) -> 3 x 100nF @+3V3\\n"
       "AVDD10 (3, 8, 38) ve DVDD10 (21) -> 4 x 100nF @PHYn_1V0\\n"
       "DVDD_RG (28) -> 1 x 100nF @+1V8\\n"
       "Artı REG_OUT cikisindaki 10uF X5R (yukarida).\\n"
       "** Y5V KULLANMA ** — datasheet s.46-53.", 90, 530, 1.3)

s.write(os.path.join(HERE, "06_ethernet.kicad_sch"))
print("06_ethernet.kicad_sch yazildi")
