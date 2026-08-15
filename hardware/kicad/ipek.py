#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""Ipek baski etiketleri — konnektorler, LED'ler, uyarilar, bantlar.

    python3 ipek.py A          # ya da C, D

NEDEN: kart insan eliyle kurulacak, kablo takilacak, ariza aranacak.
Referans numarasi ("J31") kartin uzerinde ne oldugunu SOYLEMIYOR;
semayi acmadan hangi SMA'nin anten hangisinin alici oldugunu
bilemezsin. Ipek baski uretimde bedava, yanlis takilan bir kablo ise
100 W'i alicinin on ucuna verir.

UC KURAL:

1 PEDIN USTUNE YAZMA. Uretici ipegi pedlerin uzerinden zaten
  siliyor; yazi yarim kaliyor ve okunmuyor. Etiketler pedlerin
  disina, parcanin kenar tarafina konuyor.

2 TEK YONDEN OKUNSUN. Kartin dort bir yaninda donmus yazi
  okunmuyor. Kenar konnektorlerinde yazi kartin ICINE dogru
  yaziliyor, hepsi ayni yonde.

3 UYARILAR AYRI VE BUYUK. 50 V ve 100 W RF, "bu bacaga dokunma"
  bilgisi; kucuk punto ile diger etiketlerin arasina karisirsa
  gorevini yapmiyor.
"""
import os
import sys

import pcbnew

MM = 1e6
HERE = os.path.dirname(os.path.abspath(__file__))

# ref -> etiket. Konnektorler, LED'ler, onemli parcalar.
A_ETIKET = {
    "J20": "RX1 ANT", "J21": "RX2 ANT", "J22": "RX3 ANT", "J23": "RX4 ANT",
    "J30": "TX1", "J31": "TX2", "J32": "TX3", "J33": "TX4",
    # J1 "12-50V IN" DEGIL. A kartinin girisi 9-18 V:
    # NETLIST.md §1 "VIN 9-18V", D1 = SMBJ20A (20 V standoff TVS),
    # U1 = TPS62130 (mutlak azami 17 V giris), F1 = 2 A sigorta.
    # Sistemde 50 V'luk baska bir kart (D) var ve ayni kutuda ayni
    # tip kablo dolasiyor; "50V" yazan bir girise 50 V takilir ve
    # U1 ile TVS aninda gider. Etiket sinirin kendisini soylemeli.
    "J61": "10MHz REF", "J1": "12V IN  MAX 18V", "J10": "JTAG",
    "J40": "ETH0", "J41": "ETH1",
    # J62 ile J64 TERSTI. Karttan olculdu:
    #   J62 = +3V3_CLK / VCXO_CS / VCXO_CLK / VCXO_DIN / VCXO_VC / GND
    #         yani VCXO ayar DAC'inin SPI'i
    #   J64 = +3V3 / DBG_RX / DBG_TX / GND  yani hata ayiklama UART'i
    # Ters etiketle biri USB-seri cevirici takip VCXO'nun SPI
    # hatlarini UART trafigiyle surer.
    "J60": "GPS", "J62": "VCXO DAC", "J64": "DEBUG UART",
    "J63": "TO BOARD C", "J65": "TO BOARD C 2", "J66": "TO BOARD D",
    "D60": "STATUS", "D61": "RX", "D62": "TX", "D63": "DATA",
    "U10": "ECP5-25F", "U20": "ADC1", "U21": "ADC2", "U50": "SDRAM",
    "U15": "CLK BUF", "Y10": "VCXO",
    # SW1 pedi nPROGRAM. Basinca FPGA flash'tan YENIDEN
    # YAPILANDIRILIYOR, sifirlanmiyor — ECP5'te harici reset pini
    # yok, POR gateware icinde. "RESET" yazmak yanlis beklenti
    # yaratiyor.
    "SW1": "PROG",
}
C_ETIKET = {
    "J1": "ANT 1", "J2": "ANT 2", "J3": "ANT 3", "J4": "ANT 4",
    "J82": "RX1 -> A", "J83": "RX2 -> A", "J84": "RX3 -> A",
    "J85": "RX4 -> A",
    "J86": "TX1 <- A", "J87": "TX2 <- A", "J88": "TX3 <- A",
    "J89": "TX4 <- A",
    "J80": "CONTROL", "J81": "CONTROL 2", "J90": "TO BOARD D",
}
D_ETIKET = {
    "J10": "TX IN <- A", "J20": "DPD -> C", "J30": "50V IN",
    "J31": "TO BOARD A", "J32": "FROM BOARD C", "J40": "ANT OUT",
    "Q10": "FINAL 1", "Q11": "FINAL 2", "Q12": "FINAL 3",
    "Q13": "FINAL 4",
    # T31/U40/U41: eski adlari T11/U30/U31 idi. Referans
    # catismasi yuzunden yeniden numaralandirildi (bkz.
    # D_pa/gen_02_final.py basindaki aralik listesi).
    "T30": "FINAL IN XFMR", "T31": "OUTPUT XFMR",
    "T20": "FORWARD", "T21": "REFLECTED",
    "U60": "DET FWD", "U61": "DET REV", "K20": "DPD RELAY",
    "U41": "BIAS INT 1-2", "U42": "BIAS INT 3-4",
    "U31": "ISENSE 1", "U32": "ISENSE 2",
    "U33": "ISENSE 3", "U34": "ISENSE 4",
    "L10": "DRV CHOKE", "L20": "FINAL CHOKE", "T10": "DRV IN XFMR",
    # Ters polarite artik ideal diyot: Q30 anahtar, U52 denetleyici.
    # Servis sirasinda "buradaki MOSFET niye isinmiyor" sorusunun
    # cevabi kartin uzerinde dursun.
    "Q30": "REV POLARITY", "U52": "IDEAL DIODE", "D31": "INPUT TVS",
    "U50": "50V->12V", "U51": "12V->5V",
}

# Bant bankasi etiketleri — SEMADAKI FILTRE TABLOSUYLA AYNI OLMALI.
#
# Eski liste ["160m","80m","40m","30/20m","17/15m","12/10m","6m"] idi
# ve semayla TUTMUYORDU. D_pa/gen_05_lpf.py'deki gercek tablo alti
# filtre + bir bypass:
#     KL1 160m     fc  2.2 MHz
#     KL2 80/60m   fc  6.0
#     KL3 40/30m   fc 11.0
#     KL4 20/17m   fc 19.0
#     KL5 15/10m   fc 31.0
#     KL6 6m       fc 56.0
#     KL7 BYPASS   filtre yok, dogrudan gecis
# Eski etiketlerle KL4'e "30/20m", KL5'e "17/15m", KL6'ya "12/10m"
# yaziliyordu — hepsi bir kademe kaymis. En tehlikelisi KL7: uzerinde
# "6m" yaziyordu, oysa orasi FILTRESIZ gecis. Operatorun 6m'de 100 W
# vermesi, harmonikleri hic suzmeden antene basmasi demek.
# C kartinin bant bankasi ayni yedi konumu paylasiyor.
BANTLAR = ["160m", "80/60m", "40/30m", "20/17m", "15/10m", "6m",
           "BYPASS"]

# (metin, x, y, punto) — kart uzerinde sabit uyari/baslik
A_YAZI = [
    ("DIRECT SAMPLING SDR - MAIN BOARD  REV A", 55, 4, 2.0),
    # "!! 50V !!" BURADAN KALDIRILDI. A kartinda 50 V YOK; en yuksek
    # gerilim 18 V giris. O uyari D kartina ait ve orada zaten var.
    # Yanlis yerdeki bir uyari, dogru yerdekinin de inandiriciligini
    # goturuyor.
    ("INPUT 9-18V DC ONLY", 30, 20, 1.6),
    # SASE BAGI NOTU. Sistemde tek sase referans noktasi var ve o C
    # kartinda. Bu kartin delikleri kaplamasiz; RJ45 kalkani CHASSIS
    # aginda ve topraga R692 (0R) ile TEK NOKTADAN bagli. Kartlari
    # kasaya monte eden kisi bunu semadan degil karttan okumali:
    # metal ayak takip ikinci bir toprak yolu acmak, olcerek
    # bulunmasi en zor gurultu kaynagi.
    ("HOLES UNPLATED - CHASSIS BOND = R692", 30, 25, 1.2),
]
C_YAZI = [
    ("RF FILTER BANK - 4 CH x 7 BANDS  REV A", 85, 6, 2.2),
    ("!! 100W RF WHEN TRANSMITTING !!", 130, 232, 1.8),
    # Kaplamali delik (5,5)'te — sistemin TEK sase referansi.
    # Metal ayak buraya, oteki uc delige plastik ayak.
    ("CHASSIS GND - THIS HOLE ONLY", 26, 12, 1.2),
]
D_YAZI = [
    ("POWER AMPLIFIER - CLASS A 5..100W  REV A", 45, 4, 2.0),
    ("!! 50V - 100W RF - HEATSINK IS HOT !!", 50, 180, 1.8),
    ("HOLES UNPLATED - CHASSIS BOND ON BOARD C", 60, 9, 1.2),
]

KART = {
    "A": ("A_main/dogrudan_sdr_A.kicad_pcb", A_ETIKET, A_YAZI),
    "C": ("C_rf/dogrudan_sdr_C.kicad_pcb", C_ETIKET, C_YAZI),
    "D": ("D_pa/dogrudan_sdr_D.kicad_pcb", D_ETIKET, D_YAZI),
}


def eski_sil_dosyadan(pcb):
    """Onceki calistirmanin etiketlerini DOSYADAN kaldir.

    pcbnew ile silmeyi denedim: b.Remove() cagirinca surec cokuyor
    (segmentation fault). Kart dosyasi s-ifade; kendi yazdigimiz
    metinler sifir genislikli bosluk ile isaretli, o yuzden onlari
    parantez sayarak cikarmak guvenli ve pcbnew'a hic dokunmuyor.
    """
    metin = open(pcb, encoding="utf-8").read()
    isaret = "\u200b"
    out, i, n = [], 0, 0
    while True:
        k = metin.find(isaret, i)
        if k < 0:
            out.append(metin[i:])
            break
        # bu isareti iceren (gr_text ...) blogunun basini bul
        b0 = metin.rfind("(gr_text", 0, k)
        if b0 < 0:
            out.append(metin[i:k + 1])
            i = k + 1
            continue
        # parantez sayarak blogun sonunu bul
        derinlik, j = 0, b0
        while j < len(metin):
            if metin[j] == "(":
                derinlik += 1
            elif metin[j] == ")":
                derinlik -= 1
                if derinlik == 0:
                    j += 1
                    break
            j += 1
        out.append(metin[i:b0])
        i = j
        n += 1
    yeni = "".join(out)
    if n:
        open(pcb, "w", encoding="utf-8").write(yeni)
    return n


def yaz(b, metin, x, y, punto=1.0, aci=0, hiza=None):
    t = pcbnew.PCB_TEXT(b)
    # Gorunmez isaretleyici: kendi ekledigimiz yazilari sonra
    # ayirt edebilelim diye. Ayak izlerinin kendi referans/deger
    # metinlerine dokunmuyoruz.
    t.SetText("​" + metin)
    t.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(int(punto * 0.8 * MM), int(punto * MM)))
    t.SetTextThickness(int(max(0.15, punto * 0.15) * MM))
    t.SetTextAngleDegrees(aci)
    # HIZALAMA. Varsayilan ORTALI: sol kenardaki bir konnektorun
    # etiketini pedin sagina koyunca metnin yarisi geri gelip
    # konnektorun ustune biniyor ve kartin disinda kalan kismi
    # kirpiliyordu. Sol kenarda sola dayali, sag kenarda saga dayali.
    if hiza == "sol":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    elif hiza == "sag":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    b.Add(t)
    return t


def ped_kutusu(fp):
    """Ayak izinin ped sinirlari — DONMUS kutulardan.

    GetSizeX/GetSizeY pedin kendi cercevesindeki olcu, donme
    uygulanmamis. Donmus parcalarda kutu yanlis cikiyor ve etiket
    pedin ustune dusuyordu.
    """
    xs, ys = [], []
    for p in fp.Pads():
        k = p.GetBoundingBox()
        xs += [k.GetLeft() / MM, k.GetRight() / MM]
        ys += [k.GetTop() / MM, k.GetBottom() / MM]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def tum_pedler(b):
    """Karttaki BUTUN ped kutulari (mm) — carpisma sinamasi icin."""
    out = []
    for fp in b.Footprints():
        for p in fp.Pads():
            k = p.GetBoundingBox()
            out.append((k.GetLeft() / MM, k.GetTop() / MM,
                        k.GetRight() / MM, k.GetBottom() / MM))
    return out


def carpisiyor(kutu, pedler, pay=0.15):
    """Bir yazi kutusu herhangi bir pedle ortusuyor mu.

    NEDEN GEREKLI: etiket yerlestirme yalnizca KENDI parcasinin
    pedlerine bakiyordu. Yogun kartta yazi komsu parcanin pedine
    dusuyor ve ipek boyasi orada lehim islanmasini engelliyor —
    A'da 86, C'de 103, D'de 51 silk_over_copper uyarisi buydu.
    """
    ax0, ay0, ax1, ay1 = kutu
    for bx0, by0, bx1, by1 in pedler:
        if (ax0 - pay < bx1 and ax1 + pay > bx0
                and ay0 - pay < by1 and ay1 + pay > by0):
            return True
    return False


def yazi_kutusu(t):
    k = t.GetBoundingBox()
    return (k.GetLeft() / MM, k.GetTop() / MM,
            k.GetRight() / MM, k.GetBottom() / MM)


def referanslari_temizle(b, pedler):
    """Ped uzerine dusen referans yazilarini kaydir, olmazsa Fab'a al.

    Referanslar KiCad tarafindan ayak izinin orijinine konuyor ve
    yogun bolgelerde komsu pedlerin uzerine biniyor. Once kucuk
    kaydirmalar deneniyor; hicbiri temiz degilse yazi ipekten alinip
    Fab katmanina tasiniyor.

    NEDEN FAB: ipek uzerindeki okunmaz bir referans iki kez zarar
    veriyor — hem okunmuyor hem de altindaki pedin lehimlenmesini
    bozuyor. Fab katmani montaj dokumaninda kaliyor, yani bilgi
    kaybolmuyor, sadece bakirin uzerinden kalkiyor.
    """
    kaydirilan = fab = 0
    for fp in sorted(b.Footprints(), key=lambda f: f.GetReference()):
        t = fp.Reference()
        if not t.IsVisible():
            continue
        ilk = t.GetPosition()
        if not carpisiyor(yazi_kutusu(t), pedler):
            continue
        yerlesti = False
        for dx, dy in ((0, -1.6), (0, 1.6), (-2.2, 0), (2.2, 0),
                       (0, -2.8), (0, 2.8), (-3.4, 0), (3.4, 0)):
            t.SetPosition(pcbnew.VECTOR2I(int(ilk.x + dx * MM),
                                          int(ilk.y + dy * MM)))
            if not carpisiyor(yazi_kutusu(t), pedler):
                yerlesti = True
                kaydirilan += 1
                break
        if not yerlesti:
            t.SetPosition(ilk)
            t.SetLayer(pcbnew.B_Fab if fp.GetLayer() == pcbnew.B_Cu
                       else pcbnew.F_Fab)
            fab += 1
    return kaydirilan, fab


def uygula(kart):
    yol, etiket, yazilar = KART[kart]
    pcb = os.path.join(HERE, yol)
    silinen = eski_sil_dosyadan(pcb)
    b = pcbnew.LoadBoard(pcb)
    # SINIR KUTUSUNU ONCE AL. eski_sil() cizimleri dolasiyor ve ondan
    # sonra GetBoardEdgesBoundingBox() sarmalanmamis SwigPyObject
    # donduruyor (GetLeft() bile yok). pcbnew'un proxy'leri surec
    # icinde bozuluyor; ne lazimsa erken al.
    kutu = b.GetBoardEdgesBoundingBox()
    x0, y0 = kutu.GetLeft() / MM, kutu.GetTop() / MM
    x1, y1 = kutu.GetRight() / MM, kutu.GetBottom() / MM

    fps = {f.GetReference(): f for f in b.Footprints()}
    pedler = tum_pedler(b)
    n = 0
    for ref, ad in sorted(etiket.items()):
        fp = fps.get(ref)
        if fp is None:
            continue
        k = ped_kutusu(fp)
        if k is None:
            continue
        px0, py0, px1, py1 = k
        cx, cy = (px0 + px1) / 2, (py0 + py1) / 2
        # ETIKET PEDLERIN DISINA, KARTIN ICINE DOGRU. Parca hangi
        # kenara yakinsa yazi ters yone kayiyor; boylece kenar
        # konnektorlerinin yazisi hep kartin ustunde kaliyor.
        d = {"sol": cx - x0, "sag": x1 - cx, "ust": cy - y0, "alt": y1 - cy}
        yon = min(d, key=d.get)
        hiza = None
        if yon == "sol":
            x, y, aci, hiza = px1 + 1.0, cy, 0, "sol"
        elif yon == "sag":
            x, y, aci, hiza = px0 - 1.0, cy, 0, "sag"
        elif yon == "ust":
            x, y, aci = cx, py1 + 1.8, 0
        else:
            x, y, aci = cx, py0 - 1.8, 0
        y = min(max(y, y0 + 2), y1 - 2)
        t = yaz(b, ad, x, y, 1.0, aci, hiza)
        # PEDIN USTUNE DUSTUYSE KAYDIR. Yukaridaki yon secimi sadece
        # KENDI parcasinin pedlerine bakiyor; kenar konnektorlerinin
        # etiketi komsu parcanin pedine dusuyordu (or. "RX1 ANT" ->
        # J20 ped 1, "10MHz REF" -> J61 ped 1).
        if carpisiyor(yazi_kutusu(t), pedler):
            ilk = t.GetPosition()
            for dx, dy in ((0, -2.2), (0, 2.2), (0, -3.6), (0, 3.6),
                           (-3.0, 0), (3.0, 0), (0, -5.0), (0, 5.0)):
                t.SetPosition(pcbnew.VECTOR2I(int(ilk.x + dx * MM),
                                              int(ilk.y + dy * MM)))
                if not carpisiyor(yazi_kutusu(t), pedler):
                    break
        n += 1

    for metin, x, y, punto in yazilar:
        t = yaz(b, metin, x, y, punto)
        # SABIT UYARI YAZILARI DA PEDE DUSEBILIYOR. Bunlar elle
        # yazilmis koordinatlarda ve kart olculeri degistikce
        # konnektorlerin uzerine kaydilar: C'nin "100W RF" uyarisi
        # 10, D'nin "50V - HEATSINK IS HOT" uyarisi 11 pedin
        # uzerindeydi. Uyari yazisi en cok okunmasi gereken sey;
        # pedin uzerinde yariya bolunmus halde basilirsa gorevini
        # yapmiyor, ustelik lehimi de bozuyor.
        if carpisiyor(yazi_kutusu(t), pedler):
            ilk = t.GetPosition()
            for dy in (-3, 3, -6, 6, -9, 9, -12, 12, -16, 16):
                t.SetPosition(pcbnew.VECTOR2I(ilk.x, int(ilk.y + dy * MM)))
                kb = yazi_kutusu(t)
                if (not carpisiyor(kb, pedler)
                        and kb[1] > y0 + 1 and kb[3] < y1 - 1):
                    break
        n += 1

    kaydirilan, fab = referanslari_temizle(b, pedler)

    # C ve D'de bant bankasi etiketleri
    if kart == "C":
        for k in range(1, 5):
            for i, bant in enumerate(BANTLAR, start=1):
                fp = fps.get(f"K{k}{i}")
                if fp:
                    q = fp.GetPosition()
                    yaz(b, bant, q.x / MM - 5, q.y / MM - 10, 1.1)
                    n += 1
    if kart == "D":
        for i, bant in enumerate(BANTLAR, start=1):
            fp = fps.get(f"KL{i}")
            if fp:
                q = fp.GetPosition()
                yaz(b, bant, q.x / MM - 5, q.y / MM + 17, 1.2)
                n += 1

    b.Save(pcb)
    print(f"{kart}: {silinen} eski etiket silindi, {n} etiket yazildi, "
          f"{kaydirilan} referans kaydirildi, {fab} referans Fab'a alindi")


if __name__ == "__main__":
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        uygula(k)
