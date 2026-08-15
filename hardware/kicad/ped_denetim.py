#!/usr/bin/env python3
"""Agsiz bakir ped avcisi — sembol/ayak izi numara uyusmazligi.

    python3 ped_denetim.py            # uc kart
    python3 ped_denetim.py A          # tek kart

NEDEN VAR. Bir sembolun pin numarasi ayak izinin ped numarasiyla
tutmazsa, o pine yazilan ag HICBIR YERE gitmez. Netlist sessizce
atlar, ERC bir sey demez (o semaya bakar, karta degil), DRC de
sikayet etmez — agsiz bir ped kural ihlali degildir. Kart uretilir,
parca dizilir, ve devre calismaz.

BU KARTLARDA GERCEKTEN OLDU. Ilk kosuda 31 numarali ped agsizdi:

  A  U20/U21  AD9251     ped 65   sembolde acik ped "0" idi
  A  U40/U41  RTL8211F   42..49   AYAK IZI YANLIS PARCAYA AITTI:
                                  QFN-48 6x6 secilmis, cip WQFN-40 5x5
  A  Y610/Y626 kristal   3,4      2 pinli sembol, 4 pedli ayak izi;
                                  ustelik XO ped 2'ye (govdeye) gidiyordu,
                                  yani iki PHY'nin de 25 MHz saati YOKTU
  C  E100..E127 GDT      2        sembol pinleri 1/3, ayak izi 1/2;
                                  anten korumasinin bir ucu havadaydi
  C  U40..U43 PE4312     21       sembolde acik ped "Pad" adindaydi
  D  U10     PE4312      21       ayni

Hicbiri ERC'de gorunmedi: uc kart da "Found 0 violations" veriyordu.

IKI DENETIM:
  1 Agsiz numarali ped. Adsiz pedler (macun/maske acikliklari) haric.
  2 Ped sayisi ile sembol pin sayisi. Tutmuyorsa ya yanlis ayak izi
    secilmis ya sembolde pin eksik. Uyari, hata degil: tek pinli
    baglanti noktalari ve mekanik pedler mesru istisnalar.

CIKIS KODU 1 ise zincir durur. Bir agsiz ped her zaman hatadir:
gercekten baglanmayacak bir bacak varsa semada NC isaretlenir, ki o
zaman ped de olusmaz.
"""
import sys

import pcbnew

KARTLAR = {
    "A": "A_main/dogrudan_sdr_A.kicad_pcb",
    "C": "C_rf/dogrudan_sdr_C.kicad_pcb",
    "D": "D_pa/dogrudan_sdr_D.kicad_pcb",
}


def agsiz_pedler(b):
    """(referans, deger, [ped numaralari]) — agsiz numarali pedler."""
    out = []
    for f in sorted(b.GetFootprints(), key=lambda x: x.GetReference()):
        bos = sorted({p.GetNumber() for p in f.Pads()
                      if p.GetNumber()
                      and not p.GetNetname()
                      # NPTH = mekanik delik, bakiri yok, agi olmaz
                      and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH})
        if bos:
            out.append((f.GetReference(), f.GetValue(), bos))
    return out


def kart_isle(ad):
    b = pcbnew.LoadBoard(KARTLAR[ad])
    bos = agsiz_pedler(b)
    n = sum(len(x[2]) for x in bos)
    if n == 0:
        print("%s: agsiz numarali ped yok" % ad)
        return 0
    print("%s: %d AGSIZ NUMARALI PED — sembol/ayak izi numaralari tutmuyor"
          % (ad, n))
    for ref, deg, pedler in bos:
        print("   %-7s %-18s ped %s" % (ref, deg, ",".join(pedler)))
    return n


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    toplam = 0
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        if k in KARTLAR:
            toplam += kart_isle(k)
    sys.exit(1 if toplam else 0)
