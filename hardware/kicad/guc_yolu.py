#!/usr/bin/env python3
"""Guc yollarini SERI IZLE, genisligi akima gore denetle.

    python3 guc_yolu.py            # uc karti da dener
    python3 guc_yolu.py A          # tek kart

NEDEN VAR. Genislik tablosu (dsn_yaz.ag_sinifi) agi ADINDAN taniyor.
Ama bir besleme yolu tek bir agdan ibaret degil: konnektorden
regulatore giderken sigortadan, ters polarite MOSFET'inden, ferritten
geciyor ve HER GECISTE AG ADI DEGISIYOR. Ara aglarin cogu KiCad'in
otomatik verdigi isimlerle kaliyor — "Net-(Q1-S)" gibi. Tablo onlari
tanimiyor, varsayilana dusuyorlar.

AYNI HATA IKI KEZ YAPILDI:
  D karti: VIN50, +50V ile ayni 6.67 A'i tasiyor ama tabloda yoktu,
    250 um'de kaldi. 2 oz bakirda 0.25 mm 1.4 A tasir; 6.67 A'da
    dengeye gelecegi sicaklik ~350 C, yani iz buharlasir.
  A karti: J1 (XT60) -> Net-(J1-Pin_1) -> Q1 -> Net-(Q1-S) -> F1 ->
    VIN_PROT. VIN_PROT tabloda 800 um, ama ondan ONCEKI iki ag ayni
    akimi tasiyip 250 um'de kaliyordu.

DRC BUNU GORMEZ. DRC genislik olcer, AKIM BILMEZ. Bir iz yuke gore
uc kat ince olabilir ve DRC tertemiz gecer.

YONTEM. Bilinen besleme aglarindan basla, SERI parcalardan gecerek
gereksinimi yay. Seri parca = akimi oldugu gibi gecirev iki uclu
eleman: sigorta, MOSFET (drain-source), bobin, ferrit, olcu direnci,
0R. Bunlarin iki ucundan gecen akim AYNIDIR, yani genislik
gereksinimi de aynidir.

ATLANANLAR. Toprak dokum tasiyor, ayri denetleniyor. Yuksek degerli
dirençler (>10R) akim yolu degil, gerilim bolucu ya da cekme —
onlardan yayilmiyor.
"""
import collections
import os
import re
import sys

import pcbnew

KARTLAR = {
    "A": ("A_main/dogrudan_sdr_A.kicad_pcb", 1),   # (dosya, oz bakir)
    "C": ("C_rf/dogrudan_sdr_C.kicad_pcb",   1),
    "D": ("D_pa/dogrudan_sdr_D.kicad_pcb",   2),
}

# Kaynak: her kartta bilinen besleme aglari ve TASIDIKLARI AKIM (A).
# Akim, o rayin sigortasindan ya da yukunden geliyor; ikisinden
# BUYUGU alinir, cunku arizada akimi sinirlayan sey sigortadir.
KAYNAK = {
    "A": {
        "VIN_PROT": 2.0,     # F1 = 2 A sigorta; iz sigortadan once acilmamali
        "+3V3":     1.2,     # iki PHY, FPGA bucki, ADC/DAC LDO'lari
        "+1V1":     1.0,     # ECP5 cekirdek
        "+1V8":     0.5, "+1V8_A": 0.5, "+1V8_D": 0.4, "+1V8_CLK": 0.3,
        "+2V5":     0.3, "+3V3_A": 0.3, "+3V3_CLK": 0.2,
    },
    "C": {
        "+3V3":  0.6,        # role surucusu + zayiflaticilar
        "+5V":   1.0,
        "VIN_PROT": 2.0,
    },
    # PARALEL CIHAZLARDA AKIM BOLUNUYOR — arac bunu KENDI BULAMAZ.
    #
    # Seri yayilim "bu elemandan gecen akim aynidir" varsayiyor ve
    # dallanmayi gormuyor. D kartinda dort final PARALEL: toplam
    # 6.67 A'i paylasiyorlar. Ilk halinde SRC1..4'e de 6.67 A
    # atanmisti ve 2.1 mm iz cikti — gercek 1.67 A, yani 0.6 mm
    # yetiyor. Bosa giden bakir yol tikiyor: D'nin yonlendirmesi
    # 2 katman ve 150 aga ragmen iki saati gecti, cunku 55 ag
    # 1 mm'nin ustundeydi.
    #
    # Dogru dagilim:
    #   DRN_CT  6.67 A   iki kolu birden besliyor
    #   DRN_A   3.33 A   Q10+Q11
    #   DRN_B   3.33 A   Q12+Q13
    #   SRC1..4 1.67 A   cihaz basina
    "D": {
        "+50V":   6.67,      # A sinifi 100 W, 50 V
        "VIN50":  6.67,      # giris rayi, ayni akim
        "DRN_CT": 6.67,
        "DRN_A":  3.33, "DRN_B": 3.33,
        "SRC1":   1.67, "SRC2": 1.67, "SRC3": 1.67, "SRC4": 1.67,
        "+12V":   1.0, "D2_CT": 1.0,
        "+5V":    0.5, "+3V3": 0.5,
    },
}

# Seri gecis yapan parca aileleri. Deger de bakiliyor: buyuk direnc
# akim yolu degil.
# DIYOTLAR SERI SAYILMIYOR.
# Ilk halde D* de listedeydi ve LED'lerin katot aglari ile role
# bobinlerinin flyback aglari rayin TUM akimini miras aldi:
# LED_STATUS_K 1.2 A istedi, gercekte 5 mA cekiyor. Diyot bir yuk
# ya da koruma elemani; akimi gecirdigi yer besleme yolu degil.
# Ters polarite diyotu varsa KAYNAK'a elle yazilir.
SERI_ONEK = ("F", "L", "FB")               # sigorta, bobin, ferrit
DIRENC_ESIK = 10.0                          # ohm; ustu akim yolu sayilmaz

ATLA = re.compile(r"^(GND|AGND|GND_|.*_GND)$")


def deger_ohm(s):
    """'0R', '4R7', '100', '10k' -> ohm; cozulemezse None."""
    s = (s or "").strip().upper().replace("OHM", "").replace("Ω", "")
    m = re.match(r"^(\d+(?:\.\d+)?)([RKM]?)(\d*)$", s)
    if not m:
        m = re.match(r"^(\d+)([RKM])(\d+)$", s)
        if not m:
            return None
    tam, birim, kesir = m.group(1), m.group(2), m.group(3)
    try:
        v = float(tam + ("." + kesir if kesir else ""))
    except ValueError:
        return None
    return v * {"": 1.0, "R": 1.0, "K": 1e3, "M": 1e6}[birim]


def ipc_genislik(akim, oz, dt=10.0):
    """IPC-2221 dis katman, um cinsinden gerekli genislik.

        I = 0.048 * dT^0.44 * A^0.725      (A = mil^2)
    ters cevirince A = (I / (0.048*dT^0.44))^(1/0.725)
    1 oz = 1.378 mil kalinlik.
    """
    k = 0.048 * (dt ** 0.44)
    alan_mil2 = (akim / k) ** (1.0 / 0.725)
    genislik_mil = alan_mil2 / (1.378 * oz)
    return genislik_mil * 25.4


def yukle(yol):
    b = pcbnew.LoadBoard(yol)
    if b is None:
        sys.exit("HATA: kart okunamadi: %s" % yol)
    return b


def seri_baglantilar(b):
    """{ag: [(ag2, ref)]} — seri bir parcanin oteki ucu."""
    kenar = collections.defaultdict(list)
    for f in b.Footprints():
        ref = f.GetReference()
        onek = re.match(r"^([A-Z]+)", ref)
        if not onek:
            continue
        onek = onek.group(1)

        # Iki uclu olmayan parcalar seri gecis yapmaz (regulator,
        # entegre). Onlarin girisi ve cikisi FARKLI akimlar tasir.
        pedler = [p for p in f.Pads() if p.GetNetname()]
        agler = sorted({p.GetNetname() for p in pedler})

        # MOSFET UC UCLU — IKILI KURALA TAKILIYORDU.
        # Ters polarite koruma MOSFET'i (A kartinda Q1) tam da bu
        # yuzden atlaniyordu: uc pedi var, kural iki ag ariyordu ve
        # J1'in girisi (Net-(J1-Pin_1)) hicbir gereksinim almadi.
        # Oysa XT60'tan giren akimin tamami oradan geciyor.
        #
        # Drain-source akimi gecirir, GATE gecirmez. SOT-23 MOSFET
        # duzeninde ped 1 = gate; kalan ikisi arasindan yayiyoruz.
        # Farkli bir dizilim varsa asagidaki cikti gosterir, gozle
        # dogrulanabilir.
        if onek == "Q":
            gd = sorted({p.GetNetname() for p in pedler
                         if p.GetPadName() != "1" and p.GetNetname()})
            if len(gd) == 2 and not (ATLA.match(gd[0]) or ATLA.match(gd[1])):
                kenar[gd[0]].append((gd[1], ref + "(D-S)"))
                kenar[gd[1]].append((gd[0], ref + "(D-S)"))
            continue

        if len(agler) != 2:
            continue
        if onek == "R":
            o = deger_ohm(f.GetValue())
            if o is None or o > DIRENC_ESIK:
                continue
        elif onek not in SERI_ONEK:
            continue

        a, c = agler
        if ATLA.match(a) or ATLA.match(c):
            continue
        kenar[a].append((c, ref))
        kenar[c].append((a, ref))
    return kenar


def iz_genislikleri(b):
    w = collections.defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK":
            continue
        n = t.GetNetname()
        if n:
            w[n].append(t.GetWidth() / 1000.0)
    return w


def kart_dene(ad):
    yol, oz = KARTLAR[ad]
    b = yukle(yol)
    kenar = seri_baglantilar(b)
    izler = iz_genislikleri(b)
    dokum = {z.GetNetname() for z in b.Zones()}

    # gereksinimi seri yollardan yay
    gerek = dict(KAYNAK.get(ad, {}))
    # ELLE VERILEN DEGER NIHAI — yayilim onu YUKSELTEMEZ.
    #
    # Yayilim "seri elemandan gecen akim aynidir" varsayiyor ve
    # DALLANMAYI goremiyor. D kartinda dort final paralel: Q10'un
    # drain'i DRN_A'da (3.33 A, iki cihaz) ama Q10'dan gecen akim
    # 1.67 A. Yayilim SRC1'e 3.33 yaziyordu ve elle verdigim 1.67'yi
    # eziyordu — arac kendi bilmedigi seyi biliyormus gibi davraniyor.
    #
    # Artik KAYNAK'ta adi gecen ag kilitli; yayilim yalnizca listede
    # OLMAYAN aglari dolduruyor. Yani araca ne bildigimi soyluyorum,
    # o da bilmediklerimi turetiyor.
    kaynak_agi = set(gerek)
    yol_izi = {}
    kuyruk = collections.deque((n, n, []) for n in gerek)
    while kuyruk:
        ag, kok, iz = kuyruk.popleft()
        for komsu, ref in kenar.get(ag, []):
            if komsu in kaynak_agi:
                continue                      # elle verilmis, dokunma
            yeni = gerek[kok] if komsu not in gerek else max(gerek[komsu], gerek[kok])
            if komsu in gerek and gerek[komsu] >= yeni:
                continue
            gerek[komsu] = yeni
            yol_izi[komsu] = iz + [ref]
            kuyruk.append((komsu, kok, iz + [ref]))

    print("=" * 66)
    print("KART %s   (%d oz dis bakir)" % (ad, oz))
    print("=" * 66)

    bulgu = 0
    for n in sorted(gerek, key=lambda x: -gerek[x]):
        if n in dokum:
            continue
        akim = gerek[n]
        istenen = ipc_genislik(akim, oz)
        var = izler.get(n)
        tur = "kaynak" if n in kaynak_agi else "TURETILDI: " + " -> ".join(yol_izi.get(n, []))
        if var is None:
            durum = "iz yok (yonlendirilmemis)"
            isaret = " "
        elif min(var) + 1 < istenen:
            durum = "en ince %.0f um  < gerekli %.0f um" % (min(var), istenen)
            isaret = "!"
            bulgu += 1
        else:
            durum = "en ince %.0f um  >= %.0f um" % (min(var), istenen)
            isaret = " "
        print("%s %-16s %5.2f A  %-34s  %s" % (isaret, n, akim, durum, tur))

    print("\n%d ag akima gore INCE" % bulgu)
    return bulgu


if __name__ == "__main__":
    hedef = sys.argv[1:] or ["A", "C", "D"]
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    toplam = sum(kart_dene(k) for k in hedef if k in KARTLAR)
    sys.exit(1 if toplam else 0)
