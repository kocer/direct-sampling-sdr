#!/usr/bin/env python3
"""SEMA netlist'inden pin-ag denetimi — KART GEREKMEZ.

    python3 netlist_denetim.py            # uc kart
    python3 netlist_denetim.py A

NEDEN AYRI BIR ARAC. sema_denetim.py .kicad_pcb okuyor; yani bir
sema duzeltmesini dogrulamak icin karti netlistten YENIDEN KURMAK
gerekiyor. Yonlendirici kosarken bunu yapmak koşan işi çöpe atiyor.
Bu arac dogrudan `kicad-cli sch export netlist` ciktisindan
calisiyor: sema duzeltmesi ANINDA dogrulanabiliyor.

NE BAKIYOR
  1 Belirli bir pinin belirli bir agda olmasi (BEKLENEN tablosu).
    Veri sayfasindan dogrulanmis, kritik ve SESSIZ hatalar:
    kapatma pinleri, mod secme pinleri, regulator kondansatorleri.
  2 Bir entegrenin butun besleme pinlerinin yaninda o rayda
    kondansator bulunup bulunmadigi (SEMA duzeyinde: ayni agda
    en az bir kondansator var mi).
  3 Bagsiz kalmis (hicbir dugumu paylasmayan) tek dugumlu aglar.

BEKLENEN tablosu ELLE yazilmis ve her satirin yaninda kaynagi var.
Arac veri sayfasi okumuyor; okunmus bilgiyi KILITLIYOR ki bir daha
kimse geri almasin.
"""
import collections
import os
import re
import subprocess
import sys

KARTLAR = {
    "A": "A_main/dogrudan_sdr_A.kicad_sch",
    "C": "C_rf/dogrudan_sdr_C.kicad_sch",
    "D": "D_pa/dogrudan_sdr_D.kicad_sch",
}

# (referans, pin) -> (beklenen ag, gerekce)
BEKLENEN = {
    "A": {
        ("U62", "6"): ("GND",
                       "TLV3501 SHDN AKTIF-YUKSEK (TI SBOS321E 7.4.1): "
                       "yuksekte cip kapali, cikis yuksek empedans. "
                       "+3V3'e bagliydi -> 10 MHz referans girisi olu."),
        ("U62", "2"): ("GND", "V-"),
        ("U62", "4"): ("+3V3", "V+"),
        # kristal: 1 ve 3 elektrot, 2 ve 4 metal govde
        ("Y610", "1"): ("PHY1_XI", "kristal elektrodu"),
        ("Y610", "3"): ("PHY1_XO", "kristal elektrodu"),
        ("Y610", "2"): ("GND", "metal govde"),
        ("Y610", "4"): ("GND", "metal govde"),
        ("Y626", "1"): ("PHY2_XI", "kristal elektrodu"),
        ("Y626", "3"): ("PHY2_XO", "kristal elektrodu"),
        # ADP150 / TPS7A20: giris ve cikis 1 uF ZORUNLU (kararlilik)
        ("C10", "1"): ("+3V3", "U3 giris kondansatoru"),
        ("C11", "1"): ("+1V8", "U3 cikis kondansatoru"),
        ("C22", "1"): ("+2V5", "U9 giris kondansatoru"),
        ("C23", "1"): ("+1V8_CLK", "U9 cikis kondansatoru"),
    },
    "C": {
        # PE4312 P/S = YUKSEK -> seri arayuz (veri sayfasi s.5:
        # "P/S = LOW selects the parallel interface and P/S = HIGH
        # selects the serial interface")
        ("U40", "13"): ("+3V3", "P/S=HIGH -> seri mod"),
        ("U43", "13"): ("+3V3", "P/S=HIGH -> seri mod"),
        # VSS_EXT/GND topraga = dahili negatif gerilim ureteci acik
        ("U40", "12"): ("GND", "normal mod (veri sayfasi Tablo 2 not 1)"),
        # PE4312 pin 3 SERI 10k UZERINDEN (veri sayfasi s.5)
        ("U40", "3"): ("ATT1_DAT", "seri 10k sonrasi dugum"),
        ("U43", "3"): ("ATT4_DAT", "seri 10k sonrasi dugum"),
        # DRV8833 VCP ve VINT kondansatorleri (TI SLVSAR1)
        ("U70", "11"): ("U70_VCP", "sarj pompasi kondansatoru VM'e"),
        ("U70", "14"): ("U70_VINT", "ic regulator kondansatoru GND'ye"),
        ("U85", "11"): ("U85_VCP", "sarj pompasi kondansatoru VM'e"),
        ("U85", "14"): ("U85_VINT", "ic regulator kondansatoru GND'ye"),
    },
    "D": {
        ("U10", "13"): ("+3V3", "P/S=HIGH -> seri mod"),
        ("U10", "12"): ("GND", "normal mod"),
        # AD8318 ENBL -> VPSI (veri sayfasi: "Connect to VPSI for
        # normal operation")
        ("U60", "16"): ("+5V", "ENBL=VPSI, normal calisma"),
        ("U61", "16"): ("+5V", "ENBL=VPSI, normal calisma"),
        # INA240 D paketi: 1 IN-, 2 GND, 6 VS, 8 IN+  (SBOS662C Tablo 6-1)
        ("U31", "2"): ("GND", "INA240 D paketinde pin 2 = GND"),
        ("U31", "6"): ("+5V", "INA240 D paketinde pin 6 = VS"),
        ("U10", "3"): ("ATT_DAT_Q", "PE4312 pin 3 seri 10k sonrasi"),
    },
}

# Besleme sayilan ag adlari.
BESLEME = re.compile(r"^(\+\d|PHY\d_1V0|VCXO_VDD)")
KAP = re.compile(r"^C\d+$")


def netlist(sch):
    """{ag: [(ref, pin)]} — kicad-cli ciktisindan."""
    out = "/tmp/netlist_denetim.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist", sch, "-o", out],
                   check=True, capture_output=True)
    s = open(out, encoding="utf-8").read()
    ag = {}
    for blok in re.finditer(
            r'\(net\s*\(code "[^"]*"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)',
            s, re.S):
        ad = blok.group(1)
        ag[ad] = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)',
                            blok.group(2))
    return ag


def kart_dene(k):
    ag = netlist(KARTLAR[k])
    pin_ag = {}
    for ad, dugumler in ag.items():
        for ref, pin in dugumler:
            pin_ag[(ref, pin)] = ad

    print("=" * 72)
    print("KART %s   %d ag" % (k, len(ag)))
    hata = 0

    print("\n1) veri sayfasindan kilitlenmis pin-ag beklentileri:")
    for (ref, pin), (beklenen, neden) in sorted(BEKLENEN.get(k, {}).items()):
        var = pin_ag.get((ref, pin))
        if var == beklenen:
            print("   OK  %-5s pin %-3s = %-9s" % (ref, pin, var))
        else:
            print("   !!  %-5s pin %-3s = %-9s BEKLENEN %s" %
                  (ref, pin, var, beklenen))
            print("       %s" % neden)
            hata += 1

    # 2) besleme rayinda kondansator (SEMA duzeyi: ayni agda var mi)
    print("\n2) besleme pini olan entegrenin rayinda hic kondansator yok:")
    yok = 0
    kapli = {ad for ad, d in ag.items()
             if any(KAP.match(r) for r, _p in d)}
    for ad, dugumler in sorted(ag.items()):
        if not BESLEME.match(ad) or ad in kapli:
            continue
        ics = sorted({r for r, _p in dugumler if re.match(r"^U\d", r)})
        if ics:
            print("   !! %-10s uzerinde kondansator YOK — %s"
                  % (ad, ", ".join(ics[:8])))
            yok += 1
    if not yok:
        print("   yok")
    hata += yok

    # 3) tek dugumlu ag = hicbir yere gitmeyen baglanti
    print("\n3) tek dugumlu ag (bir uc havada):")
    tek = [(a, d[0]) for a, d in sorted(ag.items())
           if len(d) == 1 and not a.startswith("unconnected-")]
    for a, (r, p) in tek:
        print("   !! %-22s yalniz %s pin %s" % (a, r, p))
    if not tek:
        print("   yok")
    hata += len(tek)

    print("\n=> KART %s: %d bulgu" % (k, hata))
    return hata


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    t = sum(kart_dene(k) for k in (sys.argv[1:] or ["A", "C", "D"])
            if k in KARTLAR)
    print("\nTOPLAM %d bulgu" % t)
    sys.exit(1 if t else 0)
