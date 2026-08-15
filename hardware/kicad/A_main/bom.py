#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""A karti BOM'unu semadan uretir, LCSC kodlariyla eslestirir.

Calistir:  python3 bom.py            ekrana ozet
           python3 bom.py csv        JLCPCB'ye yuklenecek CSV

CPL (yerlesim) dosyasi BURADAN CIKMAZ — o PCB layout'undan uretilir.
BOM once cikiyor cunku parca stogu ve maliyet layout'u beklemiyor.
"""
import collections, csv, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCH = os.path.join(HERE, "dogrudan_sdr_A.kicad_sch")

# LCSC eslesmesi. Kaynak: ../BOM_JLC.md + bu oturumda dogrulanan parcalar.
# "BASE" olanlar JLCPCB temel kutuphanesinde — ek kurulum ucreti yok.
LCSC = {
    "AD9251BCPZ-80":      ("C653380",  30.97, "extended"),
    "AD9767ASTZ":         ("C653820",  10.72, "extended"),
    "LFE5U-25F-7BG256I":  ("C1550762",  8.91, "extended"),
    "ADCLK846BCPZ":       ("C578957",   2.31, "extended"),
    "W9825G6KH-6I":       ("C97572",    7.41, "extended"),
    "RTL8211FI-CG":       ("C717681",   1.47, "extended"),
    "HR911130A":          ("C54408",    1.58, "extended"),
    "ADT1-1WT+":          ("C6835853",  3.03, "extended"),
    "PE4312C-Z":          ("C500480",   1.45, "extended"),
    "TLV3501AIDBVR":      ("C193413",   1.57, "extended"),
    "SN65LVDS2DBVR":      ("C38204",    0.36, "extended"),
    "W25Q128JVSIQ":       ("C97521",    1.80, "base"),
    "TPS62130":           ("C337502",   0.67, "extended"),
    # TPS7A2018 = 1.8 V surumu. Eski eslemedeki kod 3.3 V'luk
    # parcaya aitti. LCSC C963430 = TPS7A2018PDBVR, SOT-23-5L,
    # 1.8 V cikis (LCSC urun sayfasindan okundu, Agu 2026: 3256 stok).
    # Semadaki ayak izi SOT-23-5 (DBV) — tutuyor.
    "TPS7A2018":          ("C963430",  0.55, "extended"),
    # ADP150 SABIT CIKISLI: HER GERILIM AYRI PARCA NUMARASI.
    # Alti LDO tek koda (C144257 = ADP150AUJZ-2.5) baglanmisti ve
    # siparis edilse uc ray yanlis gerilimde gelirdi; 1.8 V bekleyen
    # ADC'ler 2.5 V gorurdu ve mutlak azamileri 2.0 V.
    # Uc kod da LCSC urun sayfasindan okundu (Agu 2026). Hepsi TSOT-5,
    # semadaki TSOT-23-5 ayak iziyle tutuyor. Stok: 1.8 -> 5835,
    # 2.5 -> 302 (DUSUK, siparis oncesi bak), 3.3 -> 4200.
    # ADP150-3.3 artik kullanilmiyor (U6/U7 ferrite donustu); kod
    # tabloda kaliyor cunku ADP150-2.5 stogu tukenirse ray sasar ve
    # o zaman hangi varyantin var oldugunu bilmek gerekiyor.
    "ADP150-2.5":         ("C144257",   1.00, "extended"),
    "ADP150-1.8":         ("C141959",   1.00, "extended"),
    "ADP150-3.3":         ("C29149",    1.00, "extended"),
    "ABLNO-V-80.000MHZ":  ("C5378891", 22.00, "extended"),
    "25MHz CL12pF":       ("C9006",     0.05, "base"),   # YXC X322525MOB4SI, CL=12pF
    "SMBJ20A":            ("C364296",   0.03, "extended"),
    "DMP3098L":           ("C155039",   0.12, "extended"),
    "2A":                 ("C371166",   0.05, "extended"),
    "12V":                ("C8062",     0.02, "extended"),
    "PROG":               ("C318884",   0.05, "extended"),
    # LED renkleri — hepsi 0805, JLCPCB'den okundu (Agu 2026).
    # Kirmizi NCD0805R1; sari/yesil/mavi KT-0805 ailesi. Mavi
    # genisletilmis kutuphanede, otekiler temel.
    "yesil":              ("C72043",    0.02, "extended"),
    "kirmizi":            ("C84256",    0.01, "base"),
    "sari":               ("C2296",     0.01, "base"),
    "mavi":               ("C2293",     0.02, "extended"),
    "ferrit 600R":        ("C1015",     0.01, "base"),
    "2.2uH":              ("C1017",     0.10, "extended"),
    "4.7uH":              ("C1018",     0.12, "extended"),
    # --- konnektorler
    "XT60":               ("C98732",    0.45, "extended"),
    "SMA A1":             ("C496550",   0.19, "extended"),
    "SMA B1":             ("C496550",   0.19, "extended"),
    "SMA A2":             ("C496550",   0.19, "extended"),
    "SMA B2":             ("C496550",   0.19, "extended"),
    "SMA TX1":            ("C496550",   0.19, "extended"),
    "SMA TX2":            ("C496550",   0.19, "extended"),
    "SMA TX3":            ("C496550",   0.19, "extended"),
    "SMA TX4":            ("C496550",   0.19, "extended"),
    "SMA 10MHz ref":      ("C496550",   0.19, "extended"),
    # 2.54 mm basliklar — dizgiye VERILMIYOR, elde lehimleniyor.
    # JLCPCB'de THT dizgi ek ucret ve bunlar zaten kolay parcalar.
    "JTAG 2x3":           ("EL",        0.05, "elde"),
    "GPS modul":          ("EL",        0.05, "elde"),
    "DAC modul":          ("EL",        0.05, "elde"),
    "C kartina":          ("EL",        0.15, "elde"),
    "C kartina #2":       ("EL",        0.05, "elde"),
    "D kartina":          ("EL",        0.15, "elde"),
    "UART 3.3V":          ("EL",        0.04, "elde"),
}
# Pasifler: deger -> LCSC. Hepsi 0402/0603 temel kutuphane.
PASIF = {
    "100nF": ("C1525",  0.0018), "10uF":  ("C15850", 0.012),
    "22uF":  ("C45783", 0.030),  "47uF":  ("C46653", 0.060),
    "1uF":   ("C52923", 0.004),  "22pF":  ("C1554",  0.002),
    "18pF":  ("C1584",  0.002),  "100nF 2kV": ("C336276", 0.030),
    "10uF X5R": ("C15850", 0.012),
    "10k":   ("C25744", 0.0008), "1k":    ("C21190", 0.0008),
    "100k":  ("C25741", 0.0008), "330R":  ("C25104", 0.0008),
    "50R 1%": ("C22775", 0.002), "49.9R 1%": ("C25107", 0.002),
    "100R":  ("C25076", 0.0008), "22R":   ("C25092", 0.0008),
    "33R 1%": ("C25105", 0.002), "0R":    ("C21189", 0.0008),
    "220R":  ("C25091", 0.0008), "32k":   ("C25768", 0.002),
    # 0603 temel kutuphane, JLCPCB'den okundu (Agu 2026)
    "470R":  ("C23179", 0.0008), "4.7k":  ("C23162", 0.0008),
    "26.7k": ("C25765", 0.002),  "10k 1%": ("C25744", 0.002),
    "2.2k 1%": ("C4190", 0.002), "1.92k 1%": ("C23025", 0.002),
    "1.5k":  ("C4310",  0.0008), "50R":   ("C22775", 0.002),
}


def netlist():
    out = "/tmp/bom_A.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist", SCH,
                    "-o", out, "--format", "kicadsexpr"],
                   capture_output=True, check=True)
    t = open(out, encoding="utf-8").read()
    rows = []
    for m in re.finditer(
            r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*'
            r'(?:\(footprint "([^"]*)"\))?', t):
        ref, val, fp = m.group(1), m.group(2), m.group(3) or ""
        if ref.startswith("#"):
            continue
        rows.append((ref, val, fp))
    return rows


def main():
    rows = netlist()
    grup = collections.defaultdict(list)
    for ref, val, fp in rows:
        grup[(val, fp)].append(ref)

    lines, toplam, eksik, kurulum = [], 0.0, [], set()
    for (val, fp), refs in sorted(grup.items(), key=lambda z: -len(z[1])):
        kod = fiyat = tip = None
        if val in LCSC:
            kod, fiyat, tip = LCSC[val]
        elif val in PASIF:
            kod, fiyat = PASIF[val]
            tip = "base"
        if kod is None:
            eksik.append((val, fp, len(refs)))
            kod, fiyat, tip = "?", 0.0, "?"
        elif tip == "extended":
            kurulum.add(kod)
        ara = fiyat * len(refs)
        toplam += ara
        lines.append((len(refs), val, kod, tip, fiyat, ara,
                      ", ".join(sorted(refs)[:6]) + (" ..." if len(refs) > 6 else "")))

    print(f"{'adet':>4}  {'deger':<20} {'LCSC':<10} {'tip':<9} "
          f"{'birim':>8} {'ara':>8}  referanslar")
    print("-" * 100)
    for n, val, kod, tip, f, ara, r in lines:
        print(f"{n:>4}  {val:<20} {kod:<10} {tip:<9} {f:>8.4f} {ara:>8.2f}  {r}")

    print("-" * 100)
    print(f"toplam bilesen : {sum(len(v) for v in grup.values())}")
    print(f"essiz satir    : {len(grup)}")
    print(f"parca maliyeti : ${toplam:.2f}  (kart basina)")
    print(f"genisletilmis  : {len(kurulum)} adet -> kurulum ~${len(kurulum) * 3:.0f}"
          f"  (JLCPCB genisletilmis parca basina ~$3, SIPARISTE BIR KEZ)")
    print(f"iki kart       : ${toplam * 2 + len(kurulum) * 3:.2f} + PCB + dizgi iscilik")
    if eksik:
        print("\n** LCSC KODU OLMAYAN SATIRLAR — doldurulmadan siparis verilmez **")
        for val, fp, n in eksik:
            print(f"   {n:>3} x {val:<22} {fp}")

    if len(sys.argv) > 1 and sys.argv[1] == "csv":
        path = os.path.join(HERE, "BOM_A.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
            for (val, fp), refs in sorted(grup.items()):
                # A KARTINDA pasif_ara() YOK — C ve D'de var.
                # Duzeltmeyi uc bom.py'ye birden uygularken buraya da
                # pasif_ara() cagrisi girmisti ve NameError veriyordu.
                # Hata gorunmedi cunku uretim komutunda stderr
                # /dev/null'a gidiyordu: CSV 78 satir yerine 31
                # satirda kesildi ve dosya "uretildi" sayildi.
                # Kesilmis bir BOM ile siparis, eksik parcayla dizgi
                # demek. Bu kartin arama zinciri LCSC -> PASIF; ozet
                # de aynisini kullaniyor, yani ikisi zaten tutarli.
                kod = (LCSC.get(val) or PASIF.get(val) or ("?",))[0]
                w.writerow([val, ",".join(sorted(refs)), fp, kod])
        print(f"\nyazildi: {path}")


if __name__ == "__main__":
    main()
