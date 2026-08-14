#!/usr/bin/env python3
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
    "J61": "10MHz REF", "J1": "12-50V IN", "J10": "JTAG",
    "J40": "ETH0", "J41": "ETH1",
    "J60": "GPS", "J62": "DEBUG UART", "J64": "SPARE",
    "J63": "TO BOARD C", "J65": "TO BOARD C 2", "J66": "TO BOARD D",
    "D60": "STATUS", "D61": "RX", "D62": "TX", "D63": "DATA",
    "U10": "ECP5-25F", "U20": "ADC1", "U21": "ADC2", "U50": "SDRAM",
    "U15": "CLK BUF", "Y10": "VCXO",
    "SW1": "RESET",
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
    "T11": "OUTPUT XFMR", "T20": "FORWARD", "T21": "REFLECTED",
    "U30": "DET FWD", "U31": "DET REV", "K20": "DPD RELAY",
}

# Bant bankasi etiketleri: kesim frekansindan bant adina
BANTLAR = ["160m", "80m", "40m", "30/20m", "17/15m", "12/10m", "6m"]

# (metin, x, y, punto) — kart uzerinde sabit uyari/baslik
A_YAZI = [
    ("DIRECT SAMPLING SDR - MAIN BOARD  REV A", 55, 4, 2.0),
    ("!! 50V !!", 30, 20, 1.6),
]
C_YAZI = [
    ("RF FILTER BANK - 4 CH x 7 BANDS  REV A", 85, 6, 2.2),
    ("!! 100W RF WHEN TRANSMITTING !!", 130, 232, 1.8),
]
D_YAZI = [
    ("POWER AMPLIFIER - CLASS A 5..100W  REV A", 45, 4, 2.0),
    ("!! 50V - 100W RF - HEATSINK IS HOT !!", 50, 180, 1.8),
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
    xs, ys = [], []
    for p in fp.Pads():
        q = p.GetPosition()
        w, h = p.GetSizeX() / 2, p.GetSizeY() / 2
        xs += [(q.x - w) / MM, (q.x + w) / MM]
        ys += [(q.y - h) / MM, (q.y + h) / MM]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


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
        yaz(b, ad, x, y, 1.0, aci, hiza)
        n += 1

    for metin, x, y, punto in yazilar:
        yaz(b, metin, x, y, punto)
        n += 1

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
    print(f"{kart}: {silinen} eski etiket silindi, {n} etiket yazildi")


if __name__ == "__main__":
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        uygula(k)
