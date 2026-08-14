#!/usr/bin/env python3
"""FPGA ball atamasini GEOMETRIDEN hesapla.

    python3 ball_atama.py            # ball_atama.json yazar

SORUN. Sema ureticileri banka pinlerini ALFABETIK siralayip veri
yoluna zip'liyordu:

    io7 = sorted(n for n, nm in B7.items() if nm.startswith("PL"))
    for p, net in zip(io7, nets7): ...

"A10, A11, A12, B2, B3..." sirasi ball'larin FIZIKSEL diziliminde
hicbir sey ifade etmiyor. SDRAM'in DQ0 bacagi kartin solunda, ona
atanan ball BGA'nin saginda kalabiliyor — o zaman yol butun demeti
capraz kesiyor, via atiyor, ve uzunluk esitlemesi imkansizlasiyor.

COZUM. Ball atamasi BIZIM secimimiz: ECP5'in kullanici I/O'lari
bankasi icinde birbirinin yerine gecebilir. Iki ucu da koridor
eksenine izdusur, ikisini de sirala, sirayla eslestir. Monoton
eslestirme = kesisme yok.

Iki kisit korunuyor:
  1 BANKA DEGISMIYOR. Sadece ayni banka icinde takas yapiliyor;
    banka = ayni IO gerilimi, ayni surucu gecikmesi.
  2 Fark cifti pinleri (PCLK, diferansiyel) disarida birakiliyor.

Iki gecisli calisir: yerlesim zaten netlistten bagimsiz (koordinatlar
kat planindan geliyor), o yuzden tek tur yetiyor.
"""
import json
import os
import re
import sys

import math

import pcbnew

from ecp5_saat import BANKA, PCLK

MM = 1e6
HERE = os.path.dirname(os.path.abspath(__file__))

# (fpga birimi, cevre birim referansi, net listesi uretici)
YOLLAR = [
    ("U20", "ADC1", [f"ADC1_D{i}" for i in range(14)] + ["ADC1_DCO", "ADC1_OR"]),
    ("U21", "ADC2", [f"ADC2_D{i}" for i in range(14)] + ["ADC2_DCO", "ADC2_OR"]),
    # SDRAM IKI KORIDOR. Veri yolu + A0..A8 banka 7'de (FPGA'nin sol
    # ustu), tasan adres/komut banka 0'da (ustu). Iki ayri banka = iki
    # ayri fiziksel demet; tek liste olarak olcunce birbirlerini
    # "kesiyor" gorunuyorlardi, oysa hic ayni koridorda degiller.
    ("U50", "SDRAM_B7", [f"SD_DQ{i}" for i in range(16)]
     + [f"SD_A{i}" for i in range(9)]),
    ("U50", "SDRAM_B0", [f"SD_A{i}" for i in range(9, 13)]
     + ["SD_BA0", "SD_BA1", "SD_UDQM"]),
    # AD9767 iki bagimsiz porta sahip: P1 ve P2, her biri 14 bit.
    # Ikisi AYRI demet — birlikte siralanirsa birbirine dolaniyorlar.
    ("U30", "DAC1_P1", [f"DAC1_P1_D{i}" for i in range(14)]),
    ("U30", "DAC1_P2", [f"DAC1_P2_D{i}" for i in range(14)]),
    # U31 semada tek portlu cizildi: DAC2_D0..D13
    ("U31", "DAC2", [f"DAC2_D{i}" for i in range(14)]),
    ("U40", "PHY1", [f"PHY1_TXD{i}" for i in range(4)]
     + ["PHY1_TXC", "PHY1_TXCTL"] + [f"PHY1_RXD{i}" for i in range(4)]
     + ["PHY1_RXC", "PHY1_RXCTL"]),
    ("U41", "PHY2", [f"PHY2_TXD{i}" for i in range(4)]
     + ["PHY2_TXC", "PHY2_TXCTL"] + [f"PHY2_RXD{i}" for i in range(4)]
     + ["PHY2_RXC", "PHY2_RXCTL"]),
]

FPGA = "U10"

# SAAT AGLARI YENIDEN ATANMAZ.
# Bu hatlar ECP5'te saat yetenekli (PCLK) ayaklara dusmek zorunda:
# oradan dogrudan saat agacina giriyorlar. Normal bir I/O'ya
# dusurursen sinyal genel yonlendirmeden gecer, skew ve jitter
# toplar, gateware'de zamanlama kapanmaz. Geometrik siralayici bunu
# bilmiyor — banka icinde herhangi bir ayagi uygun goruyor. O yuzden
# saatler haritanin DISINDA birakiliyor, su anki ayaklarinda kaliyor.
#
# ACIK MADDE: su anki ayaklarin PCLK olup olmadigi HENUZ
# DOGRULANMADI. Lattice LFE5U-25F BG256 ayak listesi lazim.
# Kart bastirilmadan once kapatilacak.
SAAT_AGLARI = {
    "ADC1_DCO", "ADC2_DCO",          # ADC veri saati, kaynak-senkron
    "SD_CLK_FPGA",                   # SDRAM saati
    "PHY1_RXC", "PHY2_RXC",          # RGMII alis saati, PHY suruyor
    "PHY1_TXC", "PHY2_TXC",          # RGMII veris saati
    "DAC1_CLK", "DAC2_CLK",
    "REF10_IN", "GPS_1PPS",
    "CLK_FPGA", "CLK_MAIN",
}


def pedler(b, ref):
    fp = next((f for f in b.Footprints() if f.GetReference() == ref), None)
    if fp is None:
        return {}
    out = {}
    for pad in fp.Pads():
        n = pad.GetNetname()
        if n:
            q = pad.GetPosition()
            out.setdefault(n, (q.x / MM, q.y / MM))
    return out


def eksen(a, c):
    """Iki parca arasindaki koridorun DIK ekseni.

    Cevre birim FPGA'nin SOLUNDA ise demet yatay akar, o zaman
    siralama Y'ye gore. Ustunde ise X'e gore. Yani izdusum ekseni,
    baglanti dogrultusuna DIK olan eksen.
    """
    dx, dy = abs(a[0] - c[0]), abs(a[1] - c[1])
    return 1 if dx >= dy else 0


def saat_ata(ball, kullanilan, hedef=None):
    """Saatleri KENDI BANKALARININ PCLK ayaklarina yerlestir.

    Saat kisiti geometriden ONCE gelir. Bir saat PCLK olmayan bir
    ayaga dusmusse, o bankadaki bir PCLK ile TAKAS ediliyor: saat
    PCLK'ya, oradaki veri hatti saatin eski ayagina. Ikisi de ayni
    bankada kaldigi icin IO gerilimi ve surucu gecikmesi degismiyor.

    HEPSI BIRDEN, TEK TEK DEGIL. Saatleri sirayla yerlestirince biri
    otekinin ayagini aliyordu (PHY1_RXC, PHY2_RXC'nin ustune gitti)
    ve semada uc ihlal cikti. Butun (saat, PCLK) ciftleri mesafeye
    gore siralanip en yakindan baslayarak dagitiliyor; hem saat hem
    ayak bir kez kullaniliyor.

    Mesafe olcusu saatin CEVRE BIRIMDEKI bacagi. Sadece "bos ilk
    PCLK" secmek kisiti sagliyor ama saati demetin ortasindan
    gecirebiliyor — ADC1'de DCO bes veri hattini kesiyordu.

    1PPS listede yok: 1 Hz'lik bir isaret saat agacina girmiyor,
    sistem saatine gore yakalaniyor. PCLK harcamak yersiz olurdu.
    """
    net2ball = {v[2]: b for b, v in ball.items() if v[2]}
    saatler = [n for n in sorted(SAAT_AGLARI - {"GPS_1PPS"})
               if n in net2ball]
    saat_ayak = {net2ball[n] for n in saatler}
    ciftler = []
    for net in saatler:
        b0 = net2ball[net]
        bank = BANKA.get(b0)
        if bank is None:
            continue
        h = (hedef or {}).get(net)
        for bl, fn in PCLK.get(bank, []):
            if "GR_" in fn:
                continue
            # baska bir saatin ustune gitme
            if bl in saat_ayak and bl != b0:
                continue
            d = (math.dist((ball[bl][0], ball[bl][1]), h) if h
                 else (0.0 if bl == b0 else 1.0))
            ciftler.append((d, net, bl))
    ciftler.sort()
    secim, alinan = {}, set()
    for d, net, bl in ciftler:
        if net in secim or bl in alinan:
            continue
        secim[net] = bl
        alinan.add(bl)
    takas = {}
    for net, yeni in secim.items():
        b0 = net2ball[net]
        kullanilan.add(yeni)
        if yeni != b0:
            takas[net] = (b0, yeni, ball[yeni][2])
    return takas


def hesapla(pcb):
    b = pcbnew.LoadBoard(pcb)
    fp_pad = pedler(b, FPGA)
    fpga = next(f for f in b.Footprints() if f.GetReference() == FPGA)
    fmerkez = (fpga.GetPosition().x / MM, fpga.GetPosition().y / MM)
    # ball adi -> konum ve net
    ball = {}
    for pad in fpga.Pads():
        q = pad.GetPosition()
        ball[pad.GetNumber()] = (q.x / MM, q.y / MM, pad.GetNetname())

    atama = {}
    rapor = []
    # SAATLER ONCE. Geometrik siralayici bunlari gormuyor; PCLK
    # kisiti daha agir bastigi icin once onlar yerlesiyor, sonra
    # kalan ayaklar demetlere paylastiriliyor.
    kullanilan = set()
    # saatin cevre birimdeki bacaginin konumu — PCLK secimi buna gore
    hedef = {}
    for cevre, ad, netler in YOLLAR:
        for n, q in pedler(b, cevre).items():
            if n in SAAT_AGLARI:
                hedef[n] = q
    takas = saat_ata(ball, kullanilan, hedef)
    atama["SAAT"] = {n: yeni for n, (eski, yeni, _) in takas.items()}
    for n, (eski, yeni, kurban) in sorted(takas.items()):
        rapor.append(f"  SAAT {n}: {eski} -> {yeni}"
                     + (f" (yer degistirdigi: {kurban})" if kurban else ""))
    # TAKASI HEMEN ISLE. Yoksa geometrik gecis hala eski durumu
    # goruyor ve yerinden edilen veri hattini kendi eski ayagina
    # geri esliyor — iki harita ayni ball'i veriyor, semada iki
    # etiket ayni pine biniyordu (multiple_net_names).
    for n, (eski, yeni, kurban) in takas.items():
        x1, y1, _ = ball[yeni]
        x0, y0, _ = ball[eski]
        ball[yeni] = (x1, y1, n)
        ball[eski] = (x0, y0, kurban)
        # Yerinden edilen hat SABITLENMIYOR. Saatin bosalan ayagini
        # kendi demetinin havuzuna birakiyoruz; geometrik gecis onu
        # sirasina gore yerlestirsin. Sabitleyince siralamayi eziyor
        # ve kesisme 0'dan 13'e cikiyordu.
    for cevre, ad, netler in YOLLAR:
        cp = pedler(b, cevre)
        var = [n for n in netler if n in cp and n in fp_pad
               and n not in SAAT_AGLARI]
        if len(var) < 4:
            rapor.append(f"  {ad}: atlandi ({len(var)} net bulundu)")
            continue
        cmerkez = next(f for f in b.Footprints()
                       if f.GetReference() == cevre).GetPosition()
        e = eksen(fmerkez, (cmerkez.x / MM, cmerkez.y / MM))

        # bu yolun SU AN kullandigi ball'lar — havuz bu, banka sabit
        havuz = [bn for bn, (x, y, net) in ball.items() if net in var]
        if len(havuz) != len(var):
            rapor.append(f"  {ad}: ball sayisi tutmuyor "
                         f"({len(havuz)} ball / {len(var)} net)")
            continue

        # iki ucu da koridor eksenine izdusur ve sirala
        net_sira = sorted(var, key=lambda n: cp[n][e])
        ball_sira = sorted(havuz, key=lambda bn: (ball[bn][1 - 0] if e else
                                                  ball[bn][0]) if False
                           else (ball[bn][e]))

        onceki = sum(1 for i, n in enumerate(net_sira)
                     if ball.get(next((bn for bn in havuz
                                       if ball[bn][2] == n), ""), (0, 0, ""))[e]
                     != ball[ball_sira[i]][e])
        atama[ad] = dict(zip(net_sira, ball_sira))
        rapor.append(f"  {ad}: {len(var)} hat, eksen "
                     f"{'Y' if e else 'X'}, {onceki} hat yeniden atandi")
    return atama, rapor


if __name__ == "__main__":
    pcb = (sys.argv[1] if len(sys.argv) > 1
           else os.path.join(HERE, "A_main", "dogrudan_sdr_A.kicad_pcb"))
    atama, rapor = hesapla(pcb)
    yol = os.path.join(HERE, "ball_atama.json")
    json.dump(atama, open(yol, "w"), indent=1, sort_keys=True)
    print("ball_atama.json:")
    for r in rapor:
        print(r)
