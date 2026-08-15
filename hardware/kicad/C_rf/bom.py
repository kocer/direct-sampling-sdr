#!/usr/bin/env python3
"""C karti BOM'unu semadan uretir, LCSC kodlariyla eslestirir.

Calistir:  python3 bom.py            ekrana ozet
           python3 bom.py csv        JLCPCB'ye yuklenecek CSV

CPL (yerlesim) dosyasi BURADAN CIKMAZ — o PCB layout'undan uretilir.
BOM once cikiyor cunku parca stogu ve maliyet layout'u beklemiyor.
"""
import collections, csv, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCH = os.path.join(HERE, "dogrudan_sdr_C.kicad_sch")

# LCSC eslesmesi. Kaynak: ../BOM_JLC.md + bu oturumda dogrulanan parcalar.
# "BASE" olanlar JLCPCB temel kutuphanesinde — ek kurulum ucreti yok.
LCSC = {
    "G6KU-2F-Y":      ("C2153173", 0.84, "extended"),   # kilitlenen, filtre
    "G6K-2F-Y":       ("C80087",   0.69, "extended"),   # kilitlenmeyen, T/R
    "PE4312C-Z":      ("C500480",  1.45, "extended"),
    "DRV8833PWPR":    ("C53055901", 0.16, "extended"),
    "74HC595D":       ("C5947",    0.07, "base"),
    "TPS62130":       ("C337502",  0.67, "extended"),
    "SMBJ20A":        ("C364296",  0.03, "extended"),
    "1N4148WS":       ("C129905",  0.04, "extended"),
    "2N7002":         ("C8545",    0.01, "base"),
    "GDT 90V":        ("C2909520", 0.18, "extended"),
    "2.2uH":          ("C1017",    0.10, "extended"),
    "A kartina":      ("EL", 0.15, "elde"),
    "A kartina #2":   ("EL", 0.05, "elde"),
    "SMA anten 1": ("C496550", 0.19, "extended"),
    "SMA anten 2": ("C496550", 0.19, "extended"),
    "SMA anten 3": ("C496550", 0.19, "extended"),
    "SMA anten 4": ("C496550", 0.19, "extended"),
    "RX1 -> A": ("C496550", 0.19, "extended"),
    "RX2 -> A": ("C496550", 0.19, "extended"),
    "RX3 -> A": ("C496550", 0.19, "extended"),
    "RX4 -> A": ("C496550", 0.19, "extended"),
    "TX1 <- A": ("C496550", 0.19, "extended"),
    "TX2 <- A": ("C496550", 0.19, "extended"),
    "TX3 <- A": ("C496550", 0.19, "extended"),
    "TX4 <- A": ("C496550", 0.19, "extended"),
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
    "26.7k": ("C25765", 0.002),  "10k 1%": ("C25744", 0.002),
    "2.2k 1%": ("C4190", 0.002), "1.92k 1%": ("C23025", 0.002),
    "1.5k":  ("C4310",  0.0008), "50R":   ("C22775", 0.002),
    "105k":  ("C25081", 0.002),  "20k":   ("C25765", 0.002),
}


def pasif_ara(val):
    """Filtre bankasindaki pF ve uH degerleri E24'ten geliyor; hepsini
    tek tek tabloya yazmak yerine bicimi tanıyıp temel kutuphane
    fiyatiyla gecıyoruz. Gercek LCSC kodu siparişte doldurulacak."""
    import re as _re
    if _re.fullmatch(r"[\d.]+(pF|nF|uF|nH|uH|k|R|M)", val):
        return ("BASE", 0.003)
    return None


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
        elif pasif_ara(val):
            kod, fiyat = pasif_ara(val)
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
        path = os.path.join(HERE, "BOM_C.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
            for (val, fp), refs in sorted(grup.items()):
                # CSV OZETLE AYNI ARAMA ZINCIRINI KULLANMALI.
                # Burada yalniz LCSC ve PASIF tablolarina bakiliyordu;
                # ekrandaki ozet ise ustune pasif_ara()'yi da
                # cagiriyor. Sonuc: ozet "BASE" derken CSV ayni satira
                # "?" yaziyordu. Uc kartta 68 satir boyle: siparise
                # giden dosya, ekranda temiz gorunen bir BOM'dan
                # sessizce daha kotu.
                kod = (LCSC.get(val) or PASIF.get(val)
                       or pasif_ara(val) or ("?",))[0]
                w.writerow([val, ",".join(sorted(refs)), fp, kod])
        print(f"\nyazildi: {path}")


if __name__ == "__main__":
    main()
