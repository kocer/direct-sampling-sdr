#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""docs/TOOLS.md'yi ARACLARIN KENDISINDEN uret.

    python3 docs/arac_listesi.py

NEDEN. TOOLS.md elle yazilmisti ve on bes arac sayiyordu; depoda
kirktan fazla var. Elle tutulan bir liste, arac eklendikce sessizce
eksiliyor ve okuyan kisi "bu kadar mi varmis" diye dusunuyor.

Her aracin modul aciklamasinin ILK SATIRI zaten ne yaptigini
soyluyor — liste oradan cikiyor. Yani yeni bir arac yazildiginda
listeye girmesi icin ekstra bir is yok; girmemesi icin aracin
aciklamasiz olmasi gerekiyor, ki o zaten ayri bir eksiklik.

Aciklamasi olmayan arac RAPOR EDILIYOR, sessizce atlanmiyor.
"""
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (baslik, dizin, aciklama)
GRUPLAR = [
    ("Schematic and netlist checks", "kicad", [
        "temel_denetim", "ped_denetim", "netlist_denetim", "sema_denetim",
        "regulator_denetim", "kondansator_denetim", "ref_denetim",
        "arayuz_kontrol", "tedarik_denetim"]),
    ("Circuit simulation", "kicad", [
        "zincir_sim", "tx_zincir_sim", "lpf_sim", "filtre_sim",
        "filtre_tasarim", "katlanma_tasarim", "tolerans_sim", "bias_sim",
        "pdn_sim", "kazanc_butcesi", "termal_hesap", "manyetik_hesap",
        "guc_yolu"]),
    ("Layout and routing", "kicad", [
        "gercek_yerlesim", "plan_yerlesim", "kat_plani", "ayir",
        "elle_cek", "dikis", "ipek", "montaj_isaret", "dsn_yaz",
        "ses_oku", "olc", "olc_yol", "uzunluk_olc", "yerlesim_kalite",
        "drc_duzelt", "pcb_kur", "ecp5_saat", "ball_atama"]),
    ("Gateware verification", "gateware/formal", ["cdc_denetim"]),
    ("Package assembly", "ardc", ["topla"]),
    ("Licensing", "kicad", ["telif"]),
]


def ilk_satir(yol):
    """Modul aciklamasinin ilk anlamli satiri."""
    try:
        metin = open(yol, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r'^"""(.*?)"""', metin, re.S | re.M)
    if not m:
        return None
    for satir in m.group(1).split("\n"):
        s = satir.strip()
        if s:
            return s
    return None


# INGILIZCE ACIKLAMALAR — ELLE, OTOMATIK CEVIRI DEGIL.
#
# Araclarin kendi aciklamalari Turkce ve oyle kalmali; depo Turkce
# calisiliyor. Ama TOOLS.md genel depoya gidiyor ve orasi Ingilizce.
#
# Otomatik ceviri YAPILMIYOR: yanlis cevrilmis bir aciklama,
# aciklamasiz kalmaktan kotudur — okuyan kisi yanlis seye guvenir.
# Eslenmemis arac RAPOR EDILIYOR ve tabloda Turkce satiriyla
# geciyor, yani eksik gorunur kaliyor.
INGILIZCE = {
    "temel_denetim": "Compares symbol pins against footprint pads",
    "ped_denetim": "Finds copper pads that have no net",
    "netlist_denetim": "Checks pin-to-net assignment from the schematic netlist",
    "sema_denetim": "Compares a symbol pin name against the net it carries",
    "regulator_denetim": "Checks each regulator part number against its output rail",
    "kondansator_denetim": "Checks capacitor value, package and voltage together",
    "ref_denetim": "Finds reference designator conflicts and silently lost parts",
    "arayuz_kontrol": "Checks the board-to-board connector agreement",
    "tedarik_denetim": "Verifies that every BOM line can be ordered, with the right properties",
    "zincir_sim": "Simulates the receive chain from the antenna to the ADC pin",
    "tx_zincir_sim": "Simulates the transmit chain, including the DAC images",
    "lpf_sim": "Measures the harmonic filters of the power amplifier",
    "filtre_sim": "Measures the receive band filters",
    "filtre_tasarim": "Synthesises the receive band filters",
    "katlanma_tasarim": "Searches for a transmission zero against alias folding",
    "tolerans_sim": "Worst-case and Monte Carlo analysis over component tolerance",
    "bias_sim": "Simulates the PA bias servo: stability, start-up and fault",
    "pdn_sim": "Measures the impedance of the power distribution network",
    "kazanc_butcesi": "Computes the drive the final stage needs, from the devices",
    "termal_hesap": "Computes the thermal path and the heatsink requirement",
    "manyetik_hesap": "Computes the toroid winding and core for each inductor",
    "guc_yolu": "Checks trace width against the current it carries",
    "gercek_yerlesim": "Places the parts from the net list and the design rules",
    "plan_yerlesim": "Plans the placement regions",
    "kat_plani": "Defines the layer stack",
    "ayir": "Separates parts whose courtyards overlap",
    "elle_cek": "Pre-routes the connections that the router must not choose",
    "dikis": "Adds ground stitching vias",
    "ipek": "Places the silkscreen text",
    "montaj_isaret": "Adds fiducials and test points",
    "dsn_yaz": "Exports the design to the router, with the copper pours",
    "ses_oku": "Imports the routed result back into the board",
    "olc": "Measures the board: parts, nets, area",
    "olc_yol": "Measures placement quality by pad-to-pad distance",
    "uzunluk_olc": "Measures the real length of the routed traces, in bundles",
    "yerlesim_kalite": "Scores the placement",
    "drc_duzelt": "Corrects the design rule violations that can be corrected",
    "pcb_kur": "Builds the board file from the net list",
    "ecp5_saat": "Checks the FPGA clock pin assignment",
    "ball_atama": "Assigns the FPGA ball map",
    "cdc_denetim": "Checks clock-domain crossings against the two-stage rule",
    "topla": "Builds the ARDC package by running the tools",
    "telif": "The single source of the copyright and licence text",
}


def ingilizce(ad, turkce):
    return INGILIZCE.get(ad, turkce)


if __name__ == "__main__":
    satirlar = ["# Tools", "",
                "Every tool in this repository, with what it does.", "",
                "**This file is generated.** `python3 docs/arac_listesi.py`",
                "writes it from the first line of each tool's own",
                "description. A hand-written list loses entries as tools are",
                "added, and the reader cannot see that it happened.", ""]
    eksik = []
    toplam = 0
    for baslik, dizin, adlar in GRUPLAR:
        satirlar.append("## %s" % baslik)
        satirlar.append("")
        satirlar.append("| Tool | What it does |")
        satirlar.append("|---|---|")
        for ad in adlar:
            yol = os.path.join(KOK, dizin, ad + ".py")
            if not os.path.exists(yol):
                eksik.append("%s/%s.py yok" % (dizin, ad))
                continue
            s = ilk_satir(yol)
            if not s:
                eksik.append("%s/%s.py aciklamasiz" % (dizin, ad))
                s = "—"
            if ad not in INGILIZCE:
                eksik.append("%s/%s.py ingilizce aciklamasi yok" % (dizin, ad))
            satirlar.append("| `%s/%s.py` | %s |"
                            % (dizin, ad, ingilizce(ad, s)))
            toplam += 1
        satirlar.append("")

    # listede olmayan araclar
    kayip = []
    for dizin in ("kicad", "gateware/formal", "ardc"):
        d = os.path.join(KOK, dizin)
        if not os.path.isdir(d):
            continue
        bilinen = set()
        for _, dz, adlar in GRUPLAR:
            if dz == dizin:
                bilinen |= set(adlar)
        for f in sorted(os.listdir(d)):
            if f.endswith(".py") and f[:-3] not in bilinen:
                kayip.append("%s/%s" % (dizin, f))

    satirlar.append("Total: %d tools." % toplam)
    satirlar.append("")
    open(os.path.join(KOK, "docs", "TOOLS.md"), "w",
         encoding="utf-8").write("\n".join(satirlar))

    print("docs/TOOLS.md yazildi — %d arac" % toplam)
    for x in eksik:
        print("  EKSIK: %s" % x)
    if kayip:
        print("  LISTEDE OLMAYAN (gruplara ekle):")
        for x in kayip:
            print("     %s" % x)
    sys.exit(1 if eksik else 0)
