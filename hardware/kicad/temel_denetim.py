#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""TEMEL DENETIM — sembol ile ayak izi birbirini tutuyor mu.

    python3 temel_denetim.py          # uc kart
    python3 temel_denetim.py A

NEDEN EN ALTTAN BASLIYORUZ. Bir sema hatasi yerlesimi ve
yonlendirmeyi bosa cikarir: saatlerce bakir cekilir, sonra kart
calismaz. Bu oturumda kart olduren hatalarin HEPSI bu katmandaydi
ve hicbiri ERC'de gorunmedi:

  AD9251     sembolde acik ped "0", ayak izinde "65"  -> ADC toprak
                                                        pedi havada
  PE4312 x5  sembolde "Pad", ayak izinde "21"
  GDT x4     sembolde 1 ve 3, ayak izinde 1 ve 2      -> anten
                                                        korumasi olu
  Kristal    2 pinli sembol, 4 pedli ayak izi         -> XO govdeye
                                                        gidiyordu,
                                                        PHY saatsiz
  RTL8211F   QFN-48 6x6 secilmis, cip WQFN-40 5x5     -> parca
                                                        lehimlenemez

Ortak kok: SEMBOLUN PIN NUMARASI ILE AYAK IZININ PED NUMARASI
TUTMUYOR. Tutmayinca netlist o baglantiyi sessizce dusuruyor. ERC
semaya bakiyor ve teli goruyor; DRC bagsiz pedi ihlal saymiyor.

UC DENETIM:

  1 SEMBOLDE VAR, AYAK IZINDE YOK. O pine yazilan ag hicbir yere
    gitmiyor. En tehlikelisi bu: sema dogru gorunur.

  2 AYAK IZINDE VAR, SEMBOLDE YOK. Ped agsiz kaliyor. Ya parca
    yanlis (RTL8211F'de oldugu gibi) ya da sembol eksik. Bakirsiz
    pedler (macun acikliklari) haric tutuluyor.

  3 PED SAYISI TUTMUYOR. Yukaridakilerin ozeti; ayri veriliyor
    cunku ayak izinin BASKA BIR PARCAYA ait oldugunu en hizli bu
    gosteriyor.

CIKIS KODU 1 ise zincir durur.
"""
import collections
import glob
import os
import re
import sys

import pcbnew

KARTLAR = {
    "A": ("A_main/dogrudan_sdr_A.kicad_pcb", "A_main"),
    "C": ("C_rf/dogrudan_sdr_C.kicad_pcb", "C_rf"),
    "D": ("D_pa/dogrudan_sdr_D.kicad_pcb", "D_pa"),
}

# Bu pedler bakirsiz: acik pedin uzerindeki macun acikliklari
# (pencere bolmesi). Sembolde karsiliklari YOK ve olmamali.
# dsn_yaz da bunlari disari yazmiyor — ayni gerekce.


def sembol_pinleri(dizin):
    """({sembol: {ped: tip}}, {referans: sembol}) — semalardan.

    Kaynak sema, kutuphane dosyasi DEGIL. Sebep: kutuphane elle
    duzeltilip ureteci (gen_symbols.py) eski kalabiliyor — bu
    projede tam olarak bu oldu ve bes duzeltme geri alinacakti.
    Karta giden sey semanin icine gomulu olan, o yuzden olcut o.

    PIN BLOGUNU ILERI ARAMAYLA OKUYORUZ. Once tek bir duzenli
    ifadeyle "(pin tip ... (name ...) (number ...)" yakalamaya
    calistim; (name) blogunun icinde ic ice parantezler var ve
    ifade cogu sembolde tutmadi. Sonuc: sembollerin cogu "0 pinli"
    goruldu ve arac 240 sahte bulgu uretti. Simdi her "(pin "
    isaretinden sonra ILK "(number" araniyor — sirasi sabit.

    ESLEME DEGERDEN DEGIL lib_id'DEN. Deger dizesiyle eslemek
    ("LM358" ile "LM358N") yanlis sembolu tutturuyor; sema her
    ornegin lib_id'sini zaten yaziyor.
    """
    tip = {}
    ref_sembol = {}
    for f in glob.glob(os.path.join(dizin, "*.kicad_sch")):
        s = open(f, errors="ignore").read()
        i = s.find("(lib_symbols")
        son = s.find("\n\t(symbol", i) if i >= 0 else -1
        if i >= 0:
            kut = s[i:son if son > 0 else len(s)]
            for parca in re.split(r'\n\t\t\t\(symbol "', kut)[1:]:
                ad = parca[:parca.index('"')]
                kok = re.sub(r"_\d+_\d+$", "", ad)
                d = tip.setdefault(kok, {})
                for m in re.finditer(r"\(pin (\w+) ", parca):
                    j = parca.find('(number "', m.end())
                    if j < 0:
                        continue
                    num = parca[j + 9:parca.index('"', j + 9)]
                    d[num] = m.group(1)
        # ornekler: lib_id + Reference
        for blok in re.split(r"\n\t\(symbol\n", s)[1:]:
            m = re.search(r'\(lib_id "([^"]+)"', blok)
            r = re.search(r'\(property "Reference" "([^"]+)"', blok)
            if m and r:
                ref_sembol[r.group(1)] = m.group(1)
    return tip, ref_sembol


def kart_isle(ad):
    yol, dizin = KARTLAR[ad]
    tip, ref_sembol = sembol_pinleri(dizin)
    b = pcbnew.LoadBoard(yol)

    bulgu = collections.defaultdict(list)
    eslesmeyen = set()
    semasiz = set()

    for f in sorted(b.GetFootprints(), key=lambda x: x.GetReference()):
        ref = f.GetReference()
        deger = f.GetValue()
        if not re.match(r"^[A-Z]+\d", ref):
            continue
        lid = ref_sembol.get(ref)
        anahtar = None
        if lid:
            for aday in (lid, lid.split(":")[-1]):
                if aday in tip and tip[aday]:
                    anahtar = aday
                    break
        if anahtar is None:
            # SEMASI OLMAYAN PARCALAR. Montaj delikleri, fiducial'lar
            # ve test noktalari karta dogrudan ekleniyor (pcb_kur ve
            # montaj_isaret), sembolleri yok. Karsilastirilacak bir
            # sey olmadigi icin bunlar EKSIK KAPSAM DEGIL.
            if re.match(r"^(H|FID|TP)\d", ref):
                semasiz.add(ref)
            else:
                eslesmeyen.add("%s (%s)" % (ref, lid or deger))
            continue

        sembol_ped = set(tip[anahtar])
        ayak_ped = set()
        for p in f.Pads():
            n = p.GetNumber()
            if not n:
                continue           # bakirsiz macun acikligi
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                continue           # mekanik delik
            ayak_ped.add(n)

        eksik = sembol_ped - ayak_ped      # sembolde var, ayak izinde yok
        fazla = ayak_ped - sembol_ped      # ayak izinde var, sembolde yok

        if eksik:
            bulgu["1 sembolde var, AYAK IZINDE YOK (ag hicbir yere gitmiyor)"] \
                .append("%-7s %-18s pin %s" % (ref, deger[:18],
                                               ",".join(sorted(eksik))))
        if fazla:
            bulgu["2 ayak izinde var, SEMBOLDE YOK (ped agsiz kalir)"] \
                .append("%-7s %-18s ped %s" % (ref, deger[:18],
                                               ",".join(sorted(fazla))))
        if len(sembol_ped) != len(ayak_ped):
            bulgu["3 PED SAYISI TUTMUYOR (ayak izi baska parcaya ait olabilir)"] \
                .append("%-7s %-18s sembol %d, ayak izi %d"
                        % (ref, deger[:18], len(sembol_ped), len(ayak_ped)))

    print("=" * 70)
    print("KART %s" % ad)
    n = 0
    for baslik in sorted(bulgu):
        print("%s  — %d" % (baslik, len(bulgu[baslik])))
        for satir in bulgu[baslik][:12]:
            print("   " + satir)
        if len(bulgu[baslik]) > 12:
            print("   ... %d tane daha" % (len(bulgu[baslik]) - 12))
        n += len(bulgu[baslik])
    if semasiz:
        print("   (%d parca semasiz: montaj deligi / fiducial / test "
              "noktasi — karsiligi yok, denetlenmez)" % len(semasiz))
    if eslesmeyen:
        print("   UYARI: %d parcanin sembolu bulunamadi, DENETLENMEDI:"
              % len(eslesmeyen))
        for x in sorted(eslesmeyen)[:8]:
            print("      " + x)
    if n == 0:
        print("   bulgu yok")
    print("=> KART %s: %d bulgu" % (ad, n))
    return n


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    toplam = 0
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        if k in KARTLAR:
            toplam += kart_isle(k)
    print("TOPLAM %d bulgu" % toplam)
    sys.exit(1 if toplam else 0)
