#!/usr/bin/env python3
"""Kartlar arasi arayuz tutarliligini dogrular.

Uc kart ayri projeler; KiCad birini digerine karsi kontrol etmiyor.
Bir kartta ATT1_DATA, otekinde ATT_DATA yazarsan sema temiz gorunur
ve baslik takildiginda sinyaller yanlis yere gider. Bir kez oldu.

Yontem: her kartin netlist'ini cikar, kart arasi baslik/koaks
konnektorlerine bagli aglari topla, karsilastir.
"""
import re, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
KARTLAR = {"A": ("A_main", "dogrudan_sdr_A"),
           "C": ("C_rf", "dogrudan_sdr_C"),
           "D": ("D_pa", "dogrudan_sdr_D")}
# kart arasi konnektor referanslari
ARAYUZ = {"A": ("J63", "J65", "J66"), "C": ("J80", "J81", "J82"),
          "D": ("J31", "J32")}


def netler(dizin, proj):
    out = f"/tmp/if_{proj}.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist",
                    os.path.join(HERE, dizin, proj + ".kicad_sch"),
                    "-o", out, "--format", "kicadsexpr"],
                   capture_output=True, check=True)
    t = open(out, encoding="utf-8").read()
    d = {}
    for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)',
                         t, re.S):
        nm, body = m.groups()
        d[nm] = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body)
    return d


def arayuz_agi(d, refs):
    """Kart arasi konnektore bagli ag adlari."""
    out = set()
    for nm, pins in d.items():
        if any(r in refs for r, _ in pins):
            out.add(nm)
    return out


kartlar = {k: netler(*v) for k, v in KARTLAR.items()}
ayd = {k: arayuz_agi(kartlar[k], ARAYUZ[k]) for k in kartlar}

YOKSAY = {"GND", "GND_HDR", "+3V3", "+5V", "+12V", "VIN_PROT", "CHASSIS"}


def baslik_pinleri(d, ref):
    """{pin_no: ag_adi} — bir konnektorun pin pin haritasi."""
    out = {}
    for nm, pins in d.items():
        for r, pn in pins:
            if r == ref:
                out[pn] = nm
    return out


# ---- PIN PIN karsilastirma. Ag KUMESI eslesse bile pinler kaymissa
# baslik takildiginda sinyaller yanlis yere gider; bir kez oldu:
# A'nin 17. pininde RLY_SER_OUT, D'nin 17. pininde PA_ADC_DOUT vardi.
CIFTLER = [("A", "J66", "D", "J31"), ("A", "J63", "C", "J80"),
           ("A", "J65", "C", "J81"), ("C", "J90", "D", "J32")]
pin_hata = 0
for ka, ra, kb, rb in CIFTLER:
    pa = baslik_pinleri(kartlar[ka], ra)
    pb = baslik_pinleri(kartlar[kb], rb)
    if not pa or not pb:
        print(f"\n=== {ka}.{ra} <-> {kb}.{rb}: konnektor bulunamadi")
        pin_hata += 1
        continue
    fark = [(p, pa.get(p), pb.get(p)) for p in sorted(set(pa) | set(pb), key=int)
            if pa.get(p) != pb.get(p)
            and not (pa.get(p) in YOKSAY and pb.get(p) in YOKSAY)]
    if fark:
        print(f"\n=== {ka}.{ra} <-> {kb}.{rb}: {len(fark)} PIN UYUSMUYOR")
        for p, x, y in fark:
            print(f"    pin {p:>3}:  {ka}={x}   {kb}={y}")
        pin_hata += len(fark)
    else:
        print(f"\n=== {ka}.{ra} <-> {kb}.{rb}: {len(pa)} pin, hepsi eslesiyor")
hata = 0
for a, b in (("A", "C"), ("A", "D"), ("C", "D")):
    ortak = (ayd[a] & ayd[b]) - YOKSAY
    sadece_a = (ayd[a] - ayd[b]) - YOKSAY
    sadece_b = (ayd[b] - ayd[a]) - YOKSAY
    print(f"\n=== {a} <-> {b} ===")
    print(f"  eslesen  : {len(ortak)}  {sorted(ortak)}")
    if a == "A" and b == "C":
        bekle = sadece_a & {n for n in sadece_a if n.startswith(("ATT", "RLY", "TR"))}
        if bekle:
            print(f"  ** {a}'da var, {b}'de YOK: {sorted(bekle)}")
            hata += len(bekle)
print()
# RF kuyruklar ayri: koaks konnektorler
rf_a = {n for n in kartlar["A"] if n.startswith(("RF_", "TX"))}
rf_c = {n for n in kartlar["C"] if n.startswith(("RX", "TX"))}
print(f"A RF aglari  : {sorted(n for n in rf_a)[:8]}")
print(f"C RF cikislari: {sorted(n for n in rf_c if n.endswith('_OUT'))[:6]}")

toplam = hata + pin_hata
print("\nSONUC:", "TUTARLI" if toplam == 0 else f"{toplam} UYUSMAZLIK")
sys.exit(1 if toplam else 0)
