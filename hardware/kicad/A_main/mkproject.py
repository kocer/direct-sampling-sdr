#!/usr/bin/env python3
"""
A karti KiCad proje iskeletini uretir: kok sema + hiyerarsik sayfalar
+ kutuphane tablolari.

Calistir:  python3 mkproject.py
Dogrula:   kicad-cli sch erc dogrudan_sdr_A.kicad_sch -o /tmp/erc.rpt
Ac:        kicad dogrudan_sdr_A.kicad_pro
"""
import json, os, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = "dogrudan_sdr_A"
VER = 20260306          # KiCad 10.0.5'in yazdigi surum

SHEET_UUIDS = {}
ROOT_UUID = ""

SHEETS = [
    ("01_power",      "Guc agaci",            "9-18V giris, TPS62130 x2, ADP150 x4, ters polarite"),
    ("02_clock",      "Saat dagitimi",        "ABLNO-V 80MHz VCXO + ADCLK846 1:6 LVDS fanout"),
    ("03_adc",        "ADC x2",               "AD9251 x2 cogullamali, ADT1-1WT x4, banka 6"),
    ("04_dac",        "DAC x2",               "AD9767 x2, cift port + interleaved, banka 2/1"),
    ("05_sdram",      "SDRAM",                "W9825G6KH-6I 32MB, banka 7 + 0"),
    ("06_ethernet",   "Ethernet x2",          "RTL8211F x2 + HR911105A x2, banka 3"),
    ("07_fpga_power", "FPGA guc + konfig",    "ECP5 birim 1 ve 8, W25Q128, JTAG"),
    ("08_control",    "Kontrol",              "PE4312 x2, GPS, VCXO DAC, roleler, banka 0/1"),
]

def u():
    return str(uuid.uuid4())

def root():
    global ROOT_UUID
    ROOT_UUID = u()
    parts = [
        f'(kicad_sch (version {VER}) (generator "mkproject") (uuid "{ROOT_UUID}")',
        '  (paper "A3")',
        '  (title_block',
        f'    (title "{PROJ} — dogrudan orneklemeli HF/VHF/UHF transceiver")',
        '    (rev "A")',
        '    (company "TEVITOL amator telsiz kulubu / TA4DTA")',
        '    (comment 1 "Lisans: CERN-OHL-S v2 (donanim) · GPL-3.0 (HDL) · CC-BY-SA 4.0 (dok)")',
        '    (comment 2 "Baglantilar kicad/NETLIST.md sartnamesinden")',
        '  )',
        '  (lib_symbols)',
    ]
    # hiyerarsik sayfa kutulari, 2 sutun. UUID'ler sheet_uuids.json'a
    # kaydediliyor; sayfa ureticileri sembol ornegi yolunda kullaniyor.
    for i, (name, title, desc) in enumerate(SHEETS):
        su = u(); SHEET_UUIDS[name] = su
        col, row = i % 2, i // 2
        x = 30.0 + col * 120.0
        y = 30.0 + row * 40.0
        parts += [
            f'  (sheet (at {x} {y}) (size 90 26)',
            '    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)',
            '    (fields_autoplaced yes)',
            '    (stroke (width 0.1524) (type solid))',
            '    (fill (color 0 0 0 0))',
            f'    (uuid "{su}")',
            f'    (property "Sheetname" "{title}" (at {x} {y-0.7} 0)',
            '      (show_name no) (do_not_autoplace no)',
            '      (effects (font (size 1.27 1.27)) (justify left bottom)))',
            f'    (property "Sheetfile" "{name}.kicad_sch" (at {x} {y+26.9} 0)',
            '      (show_name no) (do_not_autoplace no)',
            '      (effects (font (size 1.27 1.27)) (justify left top)))',
            # YOL: kok semanin UUID'si onek, ve HER SAYFAYA AYRI numara.
            # "/" yazilirsa ya da hepsi ayni sayfa numarasini alirsa KiCad
            # acilista "bir hata bulundu ve duzeltildi" diyor.
            '    (instances (project "' + PROJ + '"',
            f'      (path "/{ROOT_UUID}" (page "{i + 2}"))))',
            '  )',
        ]
    parts += [
        '  (sheet_instances',
        '    (path "/" (page "1"))',
        '  )',
        ')',
    ]
    return "\n".join(parts) + "\n"

def blank(name, title, desc, page):
    return f'''(kicad_sch (version {VER}) (generator "mkproject") (uuid "{u()}")
  (paper "A3")
  (title_block
    (title "{title}")
    (rev "A")
    (company "{PROJ}")
    (comment 1 "{desc}")
  )
  (lib_symbols)
  (text "{title}\\n\\n{desc}\\n\\nBaglantilar: ../NETLIST.md" (at 30 40 0)
    (effects (font (size 2 2)) (justify left top)))
)
'''

def main():
    global SHEET_UUIDS
    SHEET_UUIDS = {}
    open(os.path.join(HERE, f"{PROJ}.kicad_sch"), "w").write(root())
    SHEET_UUIDS["__root__"] = ROOT_UUID
    json.dump(SHEET_UUIDS, open(os.path.join(HERE, "sheet_uuids.json"), "w"), indent=1)
    for i, (name, title, desc) in enumerate(SHEETS):
        fn = os.path.join(HERE, f"{name}.kicad_sch")
        if os.path.exists(fn) and "schlib" in open(fn, encoding="utf-8").read()[:200]:
            continue     # doldurulmus sayfayi EZME
        open(fn, "w").write(blank(name, title, desc, i + 2))

    pro = {
        "meta": {"filename": f"{PROJ}.kicad_pro", "version": 1},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [], "text_variables": {},
    }
    open(os.path.join(HERE, f"{PROJ}.kicad_pro"), "w").write(json.dumps(pro, indent=2))

    open(os.path.join(HERE, "sym-lib-table"), "w").write(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "dogrudan-sdr")(type "KiCad")'
        '(uri "${KIPRJMOD}/../lib/dogrudan-sdr.kicad_sym")(options "")(descr "proje sembolleri"))\n)\n')
    open(os.path.join(HERE, "fp-lib-table"), "w").write(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "dogrudan-sdr")(type "KiCad")'
        '(uri "${KIPRJMOD}/../lib/dogrudan-sdr.pretty")(options "")(descr "proje ayak izleri"))\n)\n')
    print(f"{len(SHEETS)} sayfa + kok + kutuphane tablolari yazildi")

if __name__ == "__main__":
    main()
