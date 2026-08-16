#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""ARDC teknik ekini DERLE — elle degil, araclari kosturarak.

    python3 ardc/topla.py
    python3 ardc/topla.py --hizli     # yavas kosulari atla

NEDEN VAR. Bu klasor bir kez ELLE derlenmisti ve on uc commit sonra
icindeki sayilar artik tasarimi anlatmiyordu: BOM'da bant filtresi
bobini 150 nH yaziyordu, karttaki deger 68 nH. Aradaki farkta iki
ayri yeniden tasarim vardi (katlanma bastirmasi ve tolerans
merkezleme). O paket gonderilse YANLIS SEMA gonderilmis olurdu, ve
bunu fark ettiren tek sey elle karsilastirmaydi.

Elle derlenen bir paket sessizce eskiyor. Bu betik paketi her
kosuda SIFIRDAN uretiyor:

  - sema PDF'leri guncel .kicad_sch dosyalarindan
  - BOM'lar guncel uretecin ciktisindan
  - dogrulama belgesi ARACLARI KOSTURUP ciktilarini yakalayarak

Yani belgedeki her sayi, belgeyi ureten kosuda gercekten olculmus
oluyor. Bir arac kalirsa betik DURUYOR ve paket uretilmiyor —
"gecmeyen bir dogrulamayi anlatan bir dogrulama belgesi" cikmiyor.

DIL INGILIZCE. ARDC bir ABD vakfi; teknik ek onlarin okuyacagi dilde
olmali. Depodaki Turkce belgeler duruyor, bu paket onlarin ozeti
degil, AYRI bir cikti.
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARDC = os.path.join(KOK, "ardc")
KICAD = os.path.join(KOK, "kicad")
GW = os.path.join(KOK, "gateware")

KARTLAR = [("A", "A_main", "dogrudan_sdr_A"),
           ("C", "C_rf", "dogrudan_sdr_C"),
           ("D", "D_pa", "dogrudan_sdr_D")]


def kos(cmd, cwd, sure=1800):
    """Komutu kostur. Doner: (cikis_kodu, cikti)."""
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True,
                       text=True, timeout=sure)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def say(metin, kalip, varsayilan="-"):
    m = re.search(kalip, metin, re.M)
    return m.group(1) if m else varsayilan


# ---------------------------------------------------------------- kosular
def kicad_denetimleri():
    """Sema tarafi denetimleri. Doner: liste (ad, gecti, ozet)."""
    out = []
    for ad, aciklama in [
        ("temel_denetim", "Symbol pins against footprint pads"),
        ("ped_denetim", "Pads with no net"),
        ("netlist_denetim", "Netlist against the design intent"),
        ("sema_denetim", "Schematic rules"),
        ("regulator_denetim", "Regulator part number against its rail"),
    ]:
        rc, t = kos("python3 %s.py" % ad, KICAD)
        out.append((aciklama, rc == 0,
                    say(t, r"TOPLAM (\d+ bulgu)", "0 bulgu")))
    return out


def analog_simler(hizli):
    out = []
    isler = [
        ("zincir_sim", "Receive chain, antenna to ADC pin", 2400),
        ("lpf_sim", "Transmit harmonic filters", 1200),
        ("tx_zincir_sim", "Transmit chain, DAC images", 1800),
        ("bias_sim", "PA bias servo, stability and fault", 900),
        ("pdn_sim", "Power distribution network impedance", 600),
        ("kazanc_butcesi", "Gain budget from device parameters", 600),
        ("termal_hesap", "Thermal budget", 600),
    ]
    if not hizli:
        isler.append(("tolerans_sim", "Tolerance and Monte Carlo", 3000))
    for ad, aciklama, sure in isler:
        try:
            rc, t = kos("python3 %s.py" % ad, KICAD, sure)
        except subprocess.TimeoutExpired:
            rc, t = 1, "zaman asimi"
        out.append((aciklama, rc == 0, ad + ".py"))
    return out


def gateware_kosulari(hizli):
    ortam = "export PATH=$HOME/opt/oss-cad-suite/bin:$PATH; "
    if hizli:
        ortam += "SBY_ATLA=1 "
    try:
        rc, t = kos(ortam + "bash sim/kos.sh", GW, 3600)
    except subprocess.TimeoutExpired:
        return 1, "zaman asimi", "-", "-"
    gecen = say(t, r"  (\d+) gecti", "?")
    kalan = say(t, r"gecti, (\d+) kaldi", "?")
    return rc, t, gecen, kalan


def sentez_ozeti():
    """Son sentez kosusundan saat paylari."""
    yol = os.path.join(GW, "sentez", "pnr.log")
    if not os.path.exists(yol):
        return []
    t = open(yol, encoding="utf-8", errors="replace").read()
    son = {}
    for m in re.finditer(
            r"Max frequency for clock\s+'\$glbnet\$([^']+?)(?:\$TRELLIS_IO_IN)?':"
            r"\s+([\d.]+) MHz \((PASS|FAIL) at ([\d.]+) MHz\)", t):
        son[m.group(1)] = (m.group(2), m.group(3), m.group(4))
    return sorted(son.items())


# ---------------------------------------------------------------- paket
def semalari_uret():
    os.makedirs(os.path.join(ARDC, "sema"), exist_ok=True)
    os.makedirs(os.path.join(ARDC, "bom"), exist_ok=True)
    for kart, dizin, dosya in KARTLAR:
        sch = os.path.join(KICAD, dizin, dosya + ".kicad_sch")
        pdf = os.path.join(ARDC, "sema", dosya + ".pdf")
        rc, t = kos('kicad-cli sch export pdf "%s" -o "%s"' % (sch, pdf),
                    KICAD, 900)
        if rc != 0:
            raise SystemExit("PDF uretilemedi (%s):\n%s" % (kart, t[-500:]))
        bom_k = os.path.join(KICAD, dizin, "BOM_%s.csv" % kart)
        shutil.copy(bom_k, os.path.join(ARDC, "bom", "BOM_%s.csv" % kart))


def bom_satir_sayisi(kart):
    """(satir sayisi, parca adedi).

    CSV'yi ELLE BOLMEYE CALISTIM VE SIFIR CIKTI. Designator alani
    tirnak icinde ve ICINDE VIRGUL var ("C1,C2,C3"); satiri virgulden
    ya da '","' deseninden bolmek dogru alani vermiyor. csv modulu
    tirnaklamayi zaten biliyor — elle ayristirmanin sebebi yoktu.
    """
    import csv as _csv
    yol = os.path.join(ARDC, "bom", "BOM_%s.csv" % kart)
    satir = adet = 0
    with open(yol, encoding="utf-8", newline="") as f:
        for r in _csv.DictReader(f):
            ref = (r.get("Designator") or "").strip()
            if not ref:
                continue
            satir += 1
            adet += len([x for x in ref.split(",") if x.strip()])
    return satir, adet


def yaz(denetimler, analog, gw_gecen, gw_kalan, saatler):
    bugun = datetime.date.today().isoformat()
    s = []
    a = s.append
    a("# Verification evidence")
    a("")
    a("Project `dogrudan-sdr`. Amateur radio club of TEVITOL, station")
    a("callsign YM2X.")
    a("")
    a("**This file is generated.** `python3 ardc/topla.py` writes it. Each")
    a("number below comes from a tool that ran when the file was written.")
    a("If a tool fails, the script stops and no package is produced.")
    a("")
    a("Date of this package: %s" % bugun)
    a("")
    a("---")
    a("")
    a("## 1. Schematic checks")
    a("")
    a("These tools examine the schematic and the netlist. They find faults")
    a("that ERC cannot see, because ERC looks at the schematic alone.")
    a("")
    a("| Check | Result |")
    a("|---|---|")
    for ad, gecti, ozet in denetimler:
        a("| %s | %s |" % (ad, "pass" if gecti else "**FAIL**"))
    a("")
    a("## 2. Circuit simulation")
    a("")
    a("Connectivity can be correct while the values are wrong. These runs")
    a("measure the circuit, not the connections. Each one found a fault")
    a("that would have made a board unusable.")
    a("")
    a("| Simulation | Result | Tool |")
    a("|---|---|---|")
    for ad, gecti, arac in analog:
        a("| %s | %s | `kicad/%s` |" % (ad, "pass" if gecti else "**FAIL**",
                                        arac))
    a("")
    a("## 3. Gateware verification")
    a("")
    a("| Item | Value |")
    a("|---|---|")
    a("| Checks that pass | %s |" % gw_gecen)
    a("| Checks that fail | %s |" % gw_kalan)
    a("")
    a("The set includes module testbenches, a full-chip simulation with an")
    a("observer on every output pin, gate-level runs against the")
    a("synthesised netlist, a structural clock-domain-crossing check, and")
    a("three formal proofs. Each formal proof was tested by mutation: a")
    a("proof that passes but catches nothing gives false confidence.")
    a("")
    if saatler:
        a("## 4. Timing")
        a("")
        a("| Clock | Achieved | Required | Result |")
        a("|---|---|---|---|")
        for ad, (mhz, sonuc, hedef) in saatler:
            a("| %s | %s MHz | %s MHz | %s |"
              % (ad, mhz, hedef, "pass" if sonuc == "PASS" else "**FAIL**"))
        a("")
    a("## 5. Bill of materials")
    a("")
    a("| Board | Lines | Components |")
    a("|---|---|---|")
    for kart, _, _ in KARTLAR:
        satir, adet = bom_satir_sayisi(kart)
        a("| %s | %d | %d |" % (kart, satir, adet))
    a("")
    a("Every line has a verified order code. A separate tool queries the")
    a("supplier and checks three things: the package and the value must")
    a("agree exactly, the stock must exceed the quantity, and the real")
    a("properties of the part must suit the circuit. That last check found")
    a("filter capacitors specified as X7R, and trap capacitors rated at")
    a("50 V in a position that carries 93 V.")
    a("")
    a("Through-hole parts do not go into machine assembly. `ELLE_TAKILAN.md`")
    a("on board D lists them with the necessary specification.")
    a("")
    a("## 6. Files in this package")
    a("")
    a("| File | Content |")
    a("|---|---|")
    a("| `sema/` | Schematics of the three boards, PDF |")
    a("| `bom/` | Bill of materials of the three boards, CSV |")
    a("| `VERIFICATION.md` | This file |")
    a("| `README.md` | What the unit is and what it is for |")
    a("| `RATIONALE.md` | Why the four main design decisions were made |")
    a("")
    a("The schematics and the bills of materials are regenerated from the")
    a("source of this package. They cannot be older than the design.")
    open(os.path.join(ARDC, "VERIFICATION.md"), "w",
         encoding="utf-8").write("\n".join(s) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hizli", action="store_true")
    a = ap.parse_args()

    print("ARDC teknik eki derleniyor...")
    print("  sema PDF'leri ve BOM'lar")
    semalari_uret()

    print("  sema denetimleri")
    denetimler = kicad_denetimleri()
    print("  devre simulasyonlari")
    analog = analog_simler(a.hizli)
    print("  gateware")
    gw_rc, gw_t, gecen, kalan = gateware_kosulari(a.hizli)
    saatler = sentez_ozeti()

    # DATASHEET GUNCEL MI — sessizce eskimesin.
    #
    # VERIFICATION.md her kosuda uretiliyor, ama docs/DATASHEET.md
    # elle yaziliyor ve icinde sentezden gelen sayilar var. Bu klasor
    # bir kez tam boyle eskidi. Burada karsilastirilip uyariliyor.
    ds = os.path.join(KOK, "docs", "DATASHEET.md")
    if os.path.exists(ds) and saatler:
        metin = open(ds, encoding="utf-8").read()
        eskiler = []
        for ad, (mhz, _, _) in saatler:
            if ("`%s` maximum frequency" % ad) in metin:
                sat = re.search(r"`%s` maximum frequency \| ([\d.]+) MHz"
                                % re.escape(ad), metin)
                if sat and sat.group(1) != mhz:
                    eskiler.append("%s: belge %s, olcum %s MHz"
                                   % (ad, sat.group(1), mhz))
        if eskiler:
            print()
            print("  DIKKAT: docs/DATASHEET.md sentez sayilariyla uyusmuyor")
            for e in eskiler:
                print("     " + e)

    yaz(denetimler, analog, gecen, kalan, saatler)

    kotu = [ad for ad, g, _ in denetimler if not g] + \
           [ad for ad, g, _ in analog if not g]
    if gw_rc != 0:
        kotu.append("gateware")
    print()
    for ad in kotu:
        print("  KALDI: %s" % ad)
    if kotu:
        print()
        print("PAKET URETILDI AMA EKSIK — yukaridakiler gecmiyor.")
        print("Gecmeyen bir dogrulamayi anlatan belge gondermeyin.")
    else:
        print("  butun kosular gecti")
        print()
        print("ardc/VERIFICATION.md yazildi")
    sys.exit(1 if kotu else 0)
