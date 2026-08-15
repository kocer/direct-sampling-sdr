#!/usr/bin/env python3
"""Kondansator degeri / paketi / gerilimi tutarli mi?

    python3 kondansator_denetim.py          # uc kart
    python3 kondansator_denetim.py D

NEDEN VAR. BOM'a "100uF 1206" yazip 50 V'luk bir raya koymak mumkun
gorunuyor ama O PARCA YOK: 1206 paketinde 100 uF ancak 6.3 V'ta
uretiliyor. Siparis eden ya 6.3 V'luk alip 50 V raya takiyor (patlar),
ya da parcayi bulamayip projeyi bekletiyor. Ikisi de kartin uzerinde
gorunmuyor; DRC boyle bir sey bilmiyor.

D kartinda uc tane boyle parca bulundu:
    C212  100uF 1206  -> DRN_CT (50 V)
    C605   22uF 0603  -> +12V
    C602  470uF D10mm -> +50V   (470uF/63V tipik 12.5-16 mm govde)

TABLO NEREDEN. X5R/X7R seramikte belirli bir paket hacminde elde
edilebilen en buyuk kapasite gerilimle hizla dusuyor. Asagidaki
degerler yaygin ureticilerin (Murata, Samsung, TDK) kataloglarindaki
UST SINIR; tipik stok parcalar bunun altinda. Sinira dayanan bir secim
"var ama pahali ve tek kaynak" demektir, o yuzden UYARI veriyoruz.

DC BIAS AYRICA VAR. Sinifina yakin gerilimde calisan bir X5R
kapasitesinin yarisindan cogunu kaybeder. Bu arac onu OLCMUYOR;
sadece parcanin var olup olmadigina bakiyor. Ayirma kondansatorlerinde
gercek kapasite icin sinifin en az iki kati gerilim secilmeli.
"""
import collections
import os
import re
import sys

import pcbnew

# paket -> {gerilim: en buyuk kapasite (uF)}
# ILK TABLOM COK MUHAFAZAKARDI ve yanlis alarm veriyordu: 0402'de
# 10 uF / 6.3 V gercekten uretiliyor (Murata GRM155R60J106). Fazla
# uyaran bir denetci okunmaz olur, o yuzden sinirlar gercek katalog
# ust degerlerine cekildi. Simdi kalan uyarilarin hepsi gercek.
SINIR = {
    "0402": {6.3: 10.0,  16: 1.0,   25: 0.47, 50: 0.1,  100: 0.022},
    "0603": {6.3: 22.0,  16: 4.7,   25: 2.2,  50: 1.0,  100: 0.1},
    "0805": {6.3: 47.0,  16: 22.0,  25: 10.0, 50: 2.2,  100: 1.0},
    "1206": {6.3: 100.0, 16: 47.0,  25: 22.0, 50: 10.0, 100: 2.2},
    "1210": {6.3: 220.0, 16: 100.0, 25: 47.0, 50: 22.0, 100: 10.0},
    "1812": {6.3: 470.0, 16: 220.0, 25: 100.0, 50: 47.0, 100: 22.0},
}

# ag -> uzerindeki gerilim (V)
RAY = {
    "+50V": 50, "VIN50": 50, "DRN_CT": 50, "DRN_A": 50, "DRN_B": 50,
    "ANT_OUT": 50, "PA_LPF_OUT": 50,
    "+12V": 12, "D2_CT": 12, "SW_12V": 12,
    "VIN_PROT": 18,
    "+5V": 5, "+3V3": 3.3, "+3V3_A": 3.3, "+3V3_CLK": 3.3,
    "+2V5": 2.5, "+1V8": 1.8, "+1V8_A": 1.8, "+1V8_D": 1.8,
    "+1V8_CLK": 1.8, "+1V1": 1.1,
}

KARTLAR = {
    "A": "A_main/dogrudan_sdr_A.kicad_pcb",
    "C": "C_rf/dogrudan_sdr_C.kicad_pcb",
    "D": "D_pa/dogrudan_sdr_D.kicad_pcb",
}


def uf(s):
    """'100nF' -> 0.1 ; '22uF' -> 22 ; '470pF' -> 0.00047"""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([pnuµm]?)F", s)
    if not m:
        return None
    v = float(m.group(1))
    return v * {"p": 1e-6, "n": 1e-3, "u": 1.0, "µ": 1.0, "m": 1e3,
                "": 1.0}[m.group(2)]


def paket(fp):
    m = re.search(r"_(\d{4})_", fp)
    return m.group(1) if m else None


def gerekli_sinif(ray_v):
    """Rayin ustundeki ilk standart gerilim sinifi."""
    for s in (6.3, 16, 25, 50, 100):
        if s >= ray_v:
            return s
    return 100


def kart_dene(ad):
    b = pcbnew.LoadBoard(KARTLAR[ad])
    bulgu = []
    for f in b.GetFootprints():
        if not f.GetReference().startswith("C"):
            continue
        deger = f.GetValue()
        kap = uf(deger)
        if kap is None:
            continue
        fp = f.GetFPIDAsString()
        pk = paket(fp)
        nets = [p.GetNetname() for p in f.Pads()]
        ray = max((RAY.get(n, 0) for n in nets), default=0)
        if ray == 0:
            continue
        sinif = gerekli_sinif(ray)

        if pk and pk in SINIR:
            enb = SINIR[pk].get(sinif)
            if enb is not None and kap > enb:
                bulgu.append((f.GetReference(), deger, pk, ray, sinif, enb,
                              "PAKETTE BU KAPASITE BU GERILIMDE YOK"))
            elif enb is not None and kap > enb * 0.9:
                bulgu.append((f.GetReference(), deger, pk, ray, sinif, enb,
                              "sinira yakin — tek kaynak / pahali olabilir"))
        elif "CP_Radial" in fp:
            m = re.search(r"D(\d+(?:\.\d+)?)mm", fp)
            cap = float(m.group(1)) if m else 0
            # kaba: 470uF/63V ~ 12.5-16 mm, 100uF/63V ~ 10 mm
            gerek = 10.0 if kap <= 100 else (12.5 if kap <= 220 else 16.0)
            if sinif >= 50 and cap < gerek:
                bulgu.append((f.GetReference(), deger, "D%.0fmm" % cap, ray,
                              sinif, gerek,
                              "elektrolitik govdesi kucuk (>=%.1f mm gerekir)" % gerek))
    print("=" * 72)
    print("KART %s: %d supheli kondansator" % (ad, len(bulgu)))
    for r, d, pk, ray, sinif, enb, neden in sorted(bulgu):
        print("   %-6s %-10s %-7s ray %4.1f V (sinif %g V)  %s"
              % (r, d, pk, ray, sinif, neden))
    return sum(1 for x in bulgu if "YOK" in x[6] or "govdesi" in x[6])


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    t = 0
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        if k in KARTLAR:
            t += kart_dene(k)
    print("\n=> %d parca fiziksel olarak temin edilemez" % t)
    sys.exit(1 if t else 0)
