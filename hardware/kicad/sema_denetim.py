#!/usr/bin/env python3
"""Sembol pin ADI ile bagli oldugu AG'i karsilastir.

    python3 sema_denetim.py           # uc kart
    python3 sema_denetim.py A

NEDEN VAR. ped_denetim.py agsiz pedi buluyor: bir pin hicbir yere
gitmiyorsa yakalaniyor. Ama pin YANLIS yere gidiyorsa hicbir arac
sikayet etmiyor — ped'in agi var, netlist tutarli, ERC susuyor, DRC
susuyor. Kart uretilir ve VDD toprakta olur.

Bu tam da bu projede olan hata sinifi:
  - RTL8211F'e QFN-48 6x6 ayak izi secilmisti (cip WQFN-40 5x5):
    pedlerin YARISI kayik, yani her pin komsusunun agina baglandi.
  - 25 MHz kristalin XO ucu 4 pedli ayak izinin GOVDE pedine
    gidiyordu; ped'in agi vardi (XO), yani agsiz degildi, ama
    kristal calismiyordu.
Ikisi de burada goruluyordu: "XO adli pin GND'de" / "VDD adli pin
sinyal aginda".

YONTEM. Sembol kutuphanesinden pin ADI ve TURU okunuyor, karttan o
pin numarasinin agi okunuyor, ikisi eslestiriliyor. Sonra ad kaliplari
denetleniyor:

  1 TOPRAK ADLI PIN TOPRAKTA MI      GND/VSS/AGND/EP/PAD/EPAD
  2 BESLEME ADLI PIN BESLEMEDE MI    VDD/VCC/AVDD/VBAT/VIN/VEE
    (ve besleme pini TOPRAKTA OLMAMALI — en oldurucu hali bu)
  3 NC ADLI PIN BAGLI MI             veri sayfasi "baglamayin" diyorsa
  4 AYIRMA KONDANSATORU              her entegrenin her besleme rayina
    yakininda (15 mm) en az bir X7R ayirma kondansatoru
  5 ACIK PED (EP) TOPRAKTA MI        termal ped havada kalmasin

DIKKAT — BU ARAC KESIN DEGIL. Pin adlari uretici uretici degisiyor
(VDD_1, VDDIO, VCCA...), ve mesru istisnalar var: LM5164'un VIN'i bir
50 V rayinda, INA240'in IN+ pini shunt'un ustunde. Cikan her satir
GOZLE dogrulanmali; arac neyi neden supheli buldugunu yaziyor ki
dogrulanabilsin.
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

# Toprak sayilan ag adlari.
TOPRAK_AG = re.compile(r"^(GND|AGND|DGND|PGND|VSS|GND[_A-Z0-9]*|.*_GND)$")
# Besleme sayilan ag adlari: KiCad guc sembolleri "+3V3" gibi yaziyor.
BESLEME_AG = re.compile(r"^(\+[\d]|VIN|VCC|VDD|VBUS|VBAT|VIN50|DRN_|SW_|"
                        r"D2_CT|VCXO_VDD)")

# Toprak pini olmasi beklenen ADLAR.
TOPRAK_PIN = re.compile(
    r"^(GND|GND\d|AGND|DGND|PGND|VSS|VSSA|VSSD|AVSS|DVSS|"
    r"EP|PAD|EPAD|GND_PAD|THERMAL|~)$", re.I)
# Besleme pini olmasi beklenen ADLAR.
BESLEME_PIN = re.compile(
    r"^(VDD|VCC|AVDD|DVDD|VDDA|VDDD|VDDIO|VCCIO|VCCA|VCCD|AVCC|DVCC|"
    r"VBAT|VEE|VS|V\+|VIN|VDD[_A-Z0-9]*|VCC[_A-Z0-9]*|AVDD[_A-Z0-9]*|"
    r"DVDD[_A-Z0-9]*)$", re.I)
NC_PIN = re.compile(r"^(NC|N\.C\.|DNC|NC\d+)$", re.I)

# Ayirma kondansatoru sayilan degerler (uF cinsinden ust sinir).
AYIRMA_UST = 10.0
YAKIN_MM = 15.0


def uf(s):
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([pnuµm]?)F", s or "")
    if not m:
        return None
    return float(m.group(1)) * {"p": 1e-6, "n": 1e-3, "u": 1.0,
                                "µ": 1.0, "m": 1e3, "": 1.0}[m.group(2)]


def sema_libid(kok):
    """{referans: lib_id} — sema dosyalarindan."""
    out = {}
    for dosya in sorted(os.listdir(kok)):
        if not dosya.endswith(".kicad_sch"):
            continue
        s = open(os.path.join(kok, dosya), encoding="utf-8").read()
        for m in re.finditer(
                r'\(symbol\s+\(lib_id "([^"]+)"\).*?'
                r'\(property "Reference" "([^"]+)"', s, re.S):
            out.setdefault(m.group(2), m.group(1))
    return out


def pin_bilgi(kok, lib_id, _c={}):
    """{pin_no: ad} — kutuphaneden.

    schlib.pins() kullaniliyor, KENDI REGEX'IM DEGIL. Ilk halinde
    sym_def blogunu kendim tariyordum ve TURETILMIS sembolleri
    (extends) kaciriyordum: MCP4922, LM358, W25Q128JVS, TPS7A20,
    MCP9700 sessizce "kutuphanede yok" sayilip DENETIM DISI kaldi.
    Yedi entegre hic bakilmadan gecmisti. schlib.pins() extends
    zincirini zaten takip ediyor.
    """
    anahtar = (kok, lib_id)
    if anahtar in _c:
        return _c[anahtar]
    sys.path.insert(0, kok)
    sys.modules.pop("schlib", None)
    import schlib
    sys.path.pop(0)
    try:
        out = {num: v[3] for num, v in schlib.pins(lib_id).items()}
    except Exception:
        out = {}
    _c[anahtar] = out
    return out


def kart_dene(ad):
    yol, kok = KARTLAR[ad]
    b = pcbnew.LoadBoard(yol)
    libid = sema_libid(kok)

    # kondansatorler: (ag, konum) — ayirma araniyor
    kaplar = []
    for f in b.GetFootprints():
        if not f.GetReference().startswith("C"):
            continue
        k = uf(f.GetValue())
        if k is None or k > AYIRMA_UST:
            continue
        agler = {p.GetNetname() for p in f.Pads() if p.GetNetname()}
        if not any(TOPRAK_AG.match(n) for n in agler):
            continue                       # toprak ucu yoksa ayirma degil
        p = f.GetPosition()
        for n in agler:
            if not TOPRAK_AG.match(n):
                kaplar.append((n, p.x / 1e6, p.y / 1e6, f.GetReference()))

    # BESLEME RAYINI ADINDAN DEGIL YAPISINDAN TANI.
    # Ad kalibi ("+3V3") kartin kendi urettigi raylari kaciriyor:
    # RTL8211F'in ic regulatoru PHY1_1V0'i uretiyor, cipin AVDD10 /
    # DVDD10 pinleri oraya bagli ve bu DOGRU. Arac bunu "besleme
    # pini besleme aginda degil" diye sekiz kez sikayet ediyordu.
    # Yapisal olcut: uzerinde GND'ye giden en az iki ayirma
    # kondansatoru olan ag bir besleme rayidir.
    kap_say = collections.Counter(n for (n, _x, _y, _r) in kaplar)
    def besleme_mi(n):
        return bool(BESLEME_AG.match(n)) or kap_say[n] >= 2

    bulgu = collections.defaultdict(list)
    kutuphanesiz = []

    for f in sorted(b.GetFootprints(), key=lambda x: x.GetReference()):
        ref = f.GetReference()
        if not re.match(r"^U\d", ref):
            continue                       # yalniz entegreler
        lid = libid.get(ref)
        if not lid:
            continue
        pb = pin_bilgi(kok, lid)
        if not pb:
            kutuphanesiz.append("%s (%s)" % (ref, lid))
            continue
        ped_ag = {}
        for p in f.Pads():
            n = p.GetNumber()
            if n:
                ped_ag.setdefault(n, p.GetNetname())

        beslemeler = set()
        for num, pad in sorted(pb.items()):
            ag = ped_ag.get(num)
            if ag is None:
                continue                   # ped_denetim'in isi
            # KiCad "unconnected-(U4-NC-Pad4)" adini GERCEKTEN bagli
            # olmayan pede veriyor; bu bir ag degil, ag YOKLUGUNUN adi.
            # Ilk halinde NC denetimi bunu "NC pini bir aga bagli"
            # sayip 19 yanlis alarm veriyordu.
            bagli = not ag.startswith("unconnected-")
            pad_t = pad.strip()

            if TOPRAK_PIN.match(pad_t) and bagli and not TOPRAK_AG.match(ag):
                bulgu["1 toprak adli pin TOPRAKTA DEGIL"].append(
                    "%-6s %-16s pin %-4s ad %-10s -> %s"
                    % (ref, f.GetValue()[:16], num, pad_t, ag))

            if BESLEME_PIN.match(pad_t) and bagli:
                if TOPRAK_AG.match(ag):
                    bulgu["2a BESLEME PINI TOPRAKTA (oldurucu)"].append(
                        "%-6s %-16s pin %-4s ad %-10s -> %s"
                        % (ref, f.GetValue()[:16], num, pad_t, ag))
                elif not besleme_mi(ag):
                    bulgu["2b besleme adli pin besleme aginda degil"].append(
                        "%-6s %-16s pin %-4s ad %-10s -> %s"
                        % (ref, f.GetValue()[:16], num, pad_t, ag))
                else:
                    beslemeler.add(ag)

            if NC_PIN.match(pad_t) and bagli and not TOPRAK_AG.match(ag):
                bulgu["3 NC adli pin bir aga bagli"].append(
                    "%-6s %-16s pin %-4s ad %-10s -> %s"
                    % (ref, f.GetValue()[:16], num, pad_t, ag))

        # 4) ayirma kondansatoru
        p = f.GetPosition()
        fx, fy = p.x / 1e6, p.y / 1e6
        for ray in sorted(beslemeler):
            n = sum(1 for (a, cx, cy, _r) in kaplar
                    if a == ray and abs(cx - fx) < YAKIN_MM
                    and abs(cy - fy) < YAKIN_MM)
            if n == 0:
                bulgu["4 besleme rayinda YAKIN ayirma kondansatoru yok"].append(
                    "%-6s %-16s ray %-10s (%.0f mm cevresinde hic yok)"
                    % (ref, f.GetValue()[:16], ray, YAKIN_MM))

    print("=" * 74)
    print("KART %s" % ad)
    if kutuphanesiz:
        print("   (kutuphanede bulunamayan sembol: %s)"
              % ", ".join(kutuphanesiz[:8]))
    t = 0
    for k in sorted(bulgu):
        print("\n%s  — %d" % (k, len(bulgu[k])))
        for satir in bulgu[k]:
            print("   " + satir)
        t += len(bulgu[k])
    if not t:
        print("   bulgu yok")
    print("\n=> KART %s: %d bulgu" % (ad, t))
    return t


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    toplam = sum(kart_dene(k) for k in (sys.argv[1:] or ["A", "C", "D"])
                 if k in KARTLAR)
    print("\nTOPLAM %d bulgu" % toplam)
    sys.exit(1 if toplam else 0)
