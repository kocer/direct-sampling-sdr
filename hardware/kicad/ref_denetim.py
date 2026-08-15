#!/usr/bin/env python3
"""Referans catismasi ve sessiz parca kaybi denetimi.

    python3 ref_denetim.py            # uc kart
    python3 ref_denetim.py D

NEDEN VAR — IKI KEZ AYNI HATA.
Sema ureticileri referanslari elle sayiyor:

    gen_04_detect.py:  s.sym(DET, f"U{30 + i}", "AD8318ACPZ", ...)   -> U30 U31
    gen_03_bias.py:    s.sym(INA, f"U{30 + n}", "INA240A1DR", ...)   -> U31..U34

Ikisi de U31 istiyor. KiCad ayni referansi TEK PARCA sayip birlestiriyor
ve SESSIZCE geciyor: kartta iki AD8318 ve UC INA240 kaliyor, dorduncusu
hic olusmuyor. Yani

  - 1. kanalin akim olcum yukselteci KARTTA YOK. A sinifi bir katta
    bias geri beslemesi yoksa cihaz isindikca akim artar, artan akim
    daha cok isitir — termal kacis. 100 W'lik bir final boyle gider.
  - Yansiyan guc dedektorunun toprak pini shunt'in ustune baglaniyor,
    yani SWR korumasi da yanlis okuyor.

Ayni sinif hata daha once T11'de olmustu (surucu ve cikis
transformatoru ayni referansi aldi). Iki kez tekrarlayan bir hata
artik tesadufi degil; denetimi arac yapiyor.

NE BAKIYOR
  1 Ayni referansin FARKLI degerlerle gecmesi (gercek catisma).
    Cok birimli parcalar (LM358'in iki opampi) ayni referansi
    paylasir ve DEGERLERI AYNIDIR — onlar atlaniyor.
  2 Ureticilerin URETMEYI amacladigi referans sayisi ile kartta
    olusan sayinin tutmamasi: parca tipi basina say.
  3 Referans dizisindeki BOSLUKLAR (U30, U32, U33 var ama U31 yok
    gibi) — cogu zaman catismanin izi.
"""
import collections
import os
import re
import sys

import pcbnew

KARTLAR = {
    "A": ("A_main/dogrudan_sdr_A.kicad_pcb", "A_main"),
    "C": ("C_rf/dogrudan_sdr_C.kicad_pcb", "C_rf"),
    "D": ("D_pa/dogrudan_sdr_D.kicad_pcb", "D_pa"),
}

# gen_*.py icinde uretilen referanslari yakala:
#   s.sym(SYM, f"U{30 + i}", "DEGER", ...)   ya da   s.sym(SYM, "R210", "61R9", ...)
SYM_CAGRI = re.compile(
    r's\.sym\(\s*\w+\s*,\s*(f?"[^"]+")\s*,\s*"([^"]+)"', re.S)
# f-string icindeki taban sayi: f"U{30 + i}" -> ("U", 30)
F_TABAN = re.compile(r'^f"([A-Z]+)\{(\d+)\s*\+')


def ureticiden(kok):
    """gen_*.py dosyalarindan (dosya, referans_kalibi, deger) uret."""
    out = []
    for ad in sorted(os.listdir(kok)):
        if not (ad.startswith("gen_") and ad.endswith(".py")):
            continue
        s = open(os.path.join(kok, ad), encoding="utf-8").read()
        for ref, deger in SYM_CAGRI.findall(s):
            out.append((ad, ref, deger))
    return out


def kart_dene(ad):
    yol, kok = KARTLAR[ad]
    b = pcbnew.LoadBoard(yol)

    # --- karttaki referanslar
    deger = collections.defaultdict(set)
    tip = collections.Counter()
    for f in b.GetFootprints():
        deger[f.GetReference()].add(f.GetValue())
        tip[f.GetValue()] += 1

    print("=" * 70)
    print("KART %s   %d parca" % (ad, len(deger)))

    bulgu = 0

    # 1a) SEMADA ayni referans FARKLI SEMBOLLE — asil kanit burada.
    #
    # Kartta bakmak GEC KALIYOR: KiCad catisan iki sembolu tek parcaya
    # indirmis oluyor ve geriye tek bir footprint kaliyor, yani kanit
    # silinmis. Sema dosyasinda ise iki ayri sembol ornegi duruyor.
    #
    # Cok birimli parcalar (LM358'in iki opampi) ayni referansi ayni
    # lib_id ile paylasir — onlar mesru, atlaniyor.
    print("\n1a) SEMADA ayni referans farkli sembolle:")
    sema = collections.defaultdict(set)
    for dosya in sorted(os.listdir(kok)):
        if not dosya.endswith(".kicad_sch"):
            continue
        s = open(os.path.join(kok, dosya), encoding="utf-8").read()
        for blok in re.finditer(
                r'\(symbol\s+\(lib_id "([^"]+)"\).*?'
                r'\(property "Reference" "([^"]+)"', s, re.S):
            lib, ref = blok.group(1), blok.group(2)
            sema[ref].add((lib, dosya))
    sema_catis = {r: v for r, v in sema.items()
                  if len({l for l, _ in v}) > 1}
    if sema_catis:
        for r, v in sorted(sema_catis.items()):
            print("   !! %-6s" % r)
            for lib, dosya in sorted(v):
                print("        %-24s %s" % (dosya, lib))
            bulgu += 1
    else:
        print("   yok")

    # 1) ayni referans, farkli deger (kartta)
    print("\n1b) kartta ayni referans FARKLI degerle:")
    catis = {r: v for r, v in deger.items() if len(v) > 1}
    if catis:
        for r, v in sorted(catis.items()):
            print("   !! %-6s %s" % (r, sorted(v)))
            bulgu += 1
    else:
        print("   yok")

    # 2) ureticilerin istedigi taban sayilar cakisiyor mu
    print("\n2) uretici taban sayilari (f\"X{taban + i}\") cakismasi:")
    taban = collections.defaultdict(list)
    for dosya, ref, dgr in ureticiden(kok):
        m = F_TABAN.match(ref)
        if m:
            taban[(m.group(1), int(m.group(2)))].append((dosya, dgr))
    for (onek, t), kim in sorted(taban.items()):
        farkli = {d for _, d in kim}
        if len(kim) > 1 and len(farkli) > 1:
            print("   !! %s%d tabanini %d ureteci paylasiyor:" % (onek, t, len(kim)))
            for dosya, dgr in kim:
                print("        %-22s %s" % (dosya, dgr))
            bulgu += 1
    if not any(len(k) > 1 and len({d for _, d in k}) > 1 for k in taban.values()):
        print("   yok")

    # 3) referans dizisinde bosluk
    print("\n3) referans dizisinde bosluk (catismanin izi):")
    grup = collections.defaultdict(list)
    for r in deger:
        m = re.match(r"^([A-Z]+)(\d+)$", r)
        if m:
            grup[m.group(1)].append(int(m.group(2)))
    # BOSLUGUN KENDISI ANLAMLI DEGIL — numaralandirma tercihi olabilir.
    # Anlamli olan: boslugun IKI YANINDAKI parcalarin AYNI DEGERDE
    # olmasi, yani simetrik bir gruptan bir uye eksik. INA240 hatasi
    # tam boyle gorunuyordu: U32 U33 U34 var, U31 yok, ucu de ayni
    # deger.
    bos = 0
    tek = {r: list(v)[0] for r, v in deger.items() if len(v) == 1}
    for onek, no in sorted(grup.items()):
        no.sort()
        for a, c in zip(no, no[1:]):
            if not (1 < c - a <= 3):
                continue
            da = tek.get("%s%d" % (onek, a))
            dc = tek.get("%s%d" % (onek, c))
            if da and da == dc:
                print("   !! %s%d ve %s%d ayni deger (%s) ama aradaki %s YOK"
                      % (onek, a, onek, c, da,
                         ", ".join("%s%d" % (onek, x) for x in range(a + 1, c))))
                bos += 1
    if not bos:
        print("   yok")

    # 4) tip sayilari
    print("\n4) parca tipi sayilari (gozle dogrula, simetrik olmali):")
    for v, n in sorted(tip.items(), key=lambda x: -x[1]):
        if n <= 8 and not re.match(r"^\d", v):
            print("   %-26s %d" % (v[:26], n))

    print("\n=> %d catisma bulgusu" % bulgu)
    return bulgu


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    t = 0
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        if k in KARTLAR:
            t += kart_dene(k)
    sys.exit(1 if t else 0)
