#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""TEDARIK DENETIMI — her BOM satiri gercekten siparis edilebiliyor mu.

    python3 tedarik_denetim.py            # uc kart
    python3 tedarik_denetim.py C          # tek kart
    python3 tedarik_denetim.py C --yaz    # bulunan kodlari kaydet

NEDEN VAR. BOM'da "BASE" yazan satirlarin dogrulanmis bir tedarik
kodu YOKTU. bom.py'deki pasif_ara() sadece BICIMI taniyip
("100nF", "82nH" gibi) her degere korlemesine "BASE" donuyordu;
parcanin var olup olmadigina bakmiyordu. Kendi yorumunda da yaziyor:
"Gercek LCSC kodu siparişte doldurulacak."

Etkilenen: C kartinda 184 adet, D kartinda 61 adet — filtre
bankasinin butun bobin ve kondansatorleri dahil. Bir deger stokta
yoksa dizgi durur ya da parca DEGISTIRILIR; degistirilen bobin
filtreyi baska bir filtre yapar ve bunu kimse fark etmez.

UC SEY DOGRULANIYOR, "var mi" yetmiyor:

  1 PAKET VE DEGER BIREBIR. "82nH" arayinca 8.2nH ve 820nH de
    donuyor; paket 0603 isterken 0402 de donuyor. Ikisi de tam
    eslesmeli, yoksa ayak izi tutmaz ya da filtre kayar.

  2 STOK, GEREKEN ADEDIN USTUNDE. Dort kanal x yedi bant carpiminda
    tek deger 16 adete cikabiliyor; ustune fire payi.

  3 PARCANIN GERCEK OZELLIKLERI — ISIN ASIL YERI BURASI.

    BOBIN Q'SU. Filtre simulasyonlari Q=40 varsayiyor. Bu sorguda
    cikan 82nH cok katmanli bobinlerin Q'su 8-12 @ 100 MHz. Yani
    simule edilen filtre ile siparis edilebilen filtre AYNI DEVRE
    DEGIL: dusuk Q ekleme kaybini buyutur ve bant kenarlarini
    yuvarlar. Arac Q'yu describe alanindan cikariyor ve simulasyon
    varsayimindan dusukse BAGIRIYOR.

    KONDANSATOR DIELEKTRIGI. Filtre kondansatoru C0G/NP0 olmali.
    X7R'in kapasitesi gerilimle ve sicaklikla kayar, kayip acisi
    buyuktur; ayni degeri X7R ile takmak filtreyi bozar ve bunu
    sadece calisir haldeyken olcerek gorursun.

VERI DIS KAYNAKTAN GELIYOR VE VERI OLARAK ISLENIYOR. API cevabindaki
hicbir alan calistirilmiyor, sadece sayi ve metin olarak okunuyor.

Cevaplar diske onbelleklenip tekrar tekrar sorgu atilmiyor.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time

UC = ("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/"
      "smtGood/selectSmtComponentList")
ONBELLEK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "logs", "tedarik_onbellek.json")

KARTLAR = {"A": "A_main/BOM_A.csv",
           "C": "C_rf/BOM_C.csv",
           "D": "D_pa/BOM_D.csv"}

# Filtre simulasyonlarinin varsaydigi bobin Q'su. Bulunan parca
# bunun altindaysa simulasyon gercegi anlatmiyor demektir.
Q_VARSAYIM = {"C": 40.0, "D": 200.0, "A": 40.0}

FIRE = 1.25          # dizgide fire payi
STOK_RAHAT = 500     # bunun altinda stok "gecer ama kirilgan"

# RF/filtre kondansatoru siniri. Bunun ALTINDAKI her kondansator
# filtre elemani sayiliyor ve C0G/NP0 sart. Ustu (10nF, 2.2uF ...)
# ayirma ve yigin kondansatoru, X7R/X5R normal.
C0G_SINIR = 10e-9

# Bobin Q'sunun HANGI FREKANSTA verildigi onemli. Uretici Q'yu
# kendi sectigi bir frekansta yaziyor ve genellikle parcanin en
# parlak oldugu yeri seciyor: 22 nH icin "Q=88@900MHz" gibi. O bobin
# bizde 50 MHz'te calisacak ve 900 MHz'teki Q 50 MHz hakkinda
# neredeyse hicbir sey soylemiyor. Bu yuzden Q ancak calisma
# frekansinin bu carpani icinde verilmisse KARSILASTIRILIYOR;
# disindaysa "bilinmiyor" sayiliyor ve uyari veriliyor.
Q_FREKANS_PAYI = 4.0


def calisma_frekansi(kart, val):
    """Bu degerdeki bobin hangi frekansta calisiyor (Hz)?

    C kartinda deger dogrudan bandi soyluyor: filtre tablosundaki
    hangi bantta geciyorsa o bandin ortasi. Bulunamazsa None ve Q
    frekans denetimi atlanir (yanlis bir varsayimla uyari uretmek,
    hic uyarmamaktan kotudur).
    """
    if kart != "C":
        return None
    try:
        import zincir_sim
        bantlar = zincir_sim.bantlari_oku()
    except Exception:
        return None
    kapsam = {
        "160m": 1.9e6, "80_60m": 4.4e6, "40_30m": 8.6e6,
        "20_17m": 16.0e6, "15_10m": 25.0e6, "6m": 52.0e6,
    }
    cz = deger_coz(val)
    if not cz:
        return None
    hedef = cz[0]
    for ad, Lp, Cp, Ls, Cs, Ct, Cx in bantlar:
        for nh in (Lp, Ls):
            if abs(nh * 1e-9 - hedef) <= hedef * 0.02:
                return kapsam.get(ad)
    return None


def onbellek_yukle():
    try:
        return json.load(open(ONBELLEK, encoding="utf-8"))
    except Exception:
        return {}


def onbellek_yaz(d):
    os.makedirs(os.path.dirname(ONBELLEK), exist_ok=True)
    json.dump(d, open(ONBELLEK, "w", encoding="utf-8"))


def sorgu(anahtar, ob):
    """JLCPCB parca aramasi. Doner: liste (ham kayitlar)."""
    if anahtar in ob:
        return ob[anahtar]
    govde = json.dumps({"currentPage": 1, "pageSize": 100,
                        "keyword": anahtar, "componentLibraryType": None})
    r = subprocess.run(
        ["curl", "-s", "--max-time", "45", "-X", "POST", UC,
         "-H", "Content-Type: application/json",
         "-H", "User-Agent: Mozilla/5.0", "-d", govde],
        capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        lst = d["data"]["componentPageInfo"]["list"]
    except Exception:
        lst = []
    ob[anahtar] = lst
    onbellek_yaz(ob)
    time.sleep(0.4)
    return lst


# ------------------------------------------------------------ ayrıstirma
BIRIM = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1.0}


def deger_coz(s):
    """"82nH" -> (8.2e-08, "H") ; "560pF" -> (5.6e-10, "F")."""
    m = re.fullmatch(r"([\d.]+)\s*([pnum]?)(H|F|R|k|M)", s.strip())
    if not m:
        return None
    v = float(m.group(1)) * BIRIM.get(m.group(2), 1.0)
    tur = m.group(3)
    if tur in ("R", "k", "M"):
        v = float(m.group(1)) * {"R": 1.0, "k": 1e3, "M": 1e6}[tur]
        tur = "R"
    return (v, tur)


def paket_coz(fp):
    m = re.search(r"_(\d{4})_", fp)
    return m.group(1) if m else None


def q_cikar(aciklama):
    """describe icinden bobin Q'su: "8@100MHz" -> (8.0, 100e6)."""
    m = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)\s*@\s*(\d+(?:\.\d+)?)\s*(k|M|G)?Hz",
                  aciklama)
    if not m:
        return None
    carp = {"k": 1e3, "M": 1e6, "G": 1e9, None: 1.0}[m.group(3)]
    return (float(m.group(1)), float(m.group(2)) * carp)


def dielektrik(aciklama):
    m = re.search(r"\b(C0G|NP0|X7R|X5R|Y5V|X6S|X7S)\b", aciklama, re.I)
    return m.group(1).upper() if m else None


def aday_uygun(kayit, hedef_v, tur, paket):
    """Kayit birebir tutuyor mu — paket ve deger."""
    if (kayit.get("componentSpecificationEn") or "").strip() != paket:
        return False
    ad = (kayit.get("erpComponentName") or "") + " " + \
         (kayit.get("describe") or "")
    # degeri metinden cikar: birimli her sayiyi dene
    birim = {"H": "H", "F": "F", "R": "Ω"}[tur]
    for m in re.finditer(r"([\d.]+)\s*([pnumμ]?)%s" % birim, ad):
        try:
            v = float(m.group(1)) * BIRIM.get(
                m.group(2).replace("μ", "u"), 1.0)
        except ValueError:
            continue
        if abs(v - hedef_v) <= hedef_v * 0.02:
            return True
    return False


def sec(kayitlar, hedef_v, tur, paket, adet, kart):
    """En iyi aday. Doner: (kayit, notlar) ya da (None, sebep)."""
    uygun = [k for k in kayitlar if aday_uygun(k, hedef_v, tur, paket)]
    if not uygun:
        return None, "paket %s + deger eslesen kayit yok" % paket
    stoklu = [k for k in uygun if (k.get("stockCount") or 0) >= adet * FIRE]
    if not stoklu:
        en = max((k.get("stockCount") or 0) for k in uygun)
        return None, ("stok yetersiz: en fazla %d, gereken %d"
                      % (en, int(adet * FIRE)))

    # FILTRE KONDANSATORUNDE DIELEKTRIK, KUTUPHANE TIERININ ONUNDE.
    # Ilk surumde once "temel kutuphane mi" diye bakiyordum ve arac
    # 6800pF ile 470pF filtre kondansatorlerine X7R secti — ikisi de
    # bant filtresinin sont kolu. X7R'in kapasitesi uygulanan
    # gerilimle ve sicaklikla kayar, kayip acisi C0G'nin kat kat
    # ustundedir. Ucuz olmasi filtreyi kaydirmasini telafi etmiyor.
    filtre_kond = (tur == "F" and hedef_v < C0G_SINIR)
    if filtre_kond:
        c0g = [k for k in stoklu
               if dielektrik(k.get("describe") or "") in ("C0G", "NP0")]
        if not c0g:
            return None, ("%s icin C0G/NP0 yok (bulunanlar X7R/X5R) — "
                          "filtre kondansatoru olarak kullanilamaz" % paket)
        stoklu = c0g

    def puan(k):
        q = q_cikar(k.get("describe") or "")
        return (
            1 if k.get("componentLibraryType") == "base" else 0,
            q[0] if (tur == "H" and q) else 0,
            k.get("stockCount") or 0,
        )
    return max(stoklu, key=puan), None


def kart_isle(kart, yaz=False):
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       KARTLAR[kart])
    satirlar = list(csv.DictReader(open(yol, encoding="utf-8")))
    ob = onbellek_yukle()
    bulgu, bulunan = [], {}
    q_uyari = []

    print("=" * 70)
    print("KART %s — %s" % (kart, KARTLAR[kart]))
    for r in satirlar:
        if (r.get("LCSC") or "").strip() != "BASE":
            continue
        val = r["Comment"].strip()
        fp = r["Footprint"]
        adet = len([x for x in r["Designator"].split(",") if x.strip()])
        cz = deger_coz(val)
        paket = paket_coz(fp)
        if not cz or not paket:
            bulgu.append("%-9s %-28s deger ya da paket okunamadi" % (val, fp))
            continue
        hedef_v, tur = cz
        tip = {"H": "inductor", "F": "capacitor", "R": "resistor"}[tur]
        kayitlar = sorgu("%s %s %s" % (val, paket, tip), ob)
        kayit, sebep = sec(kayitlar, hedef_v, tur, paket, adet, kart)
        if kayit is None:
            bulgu.append("%-9s %-8s x%-4d %s" % (val, paket, adet, sebep))
            continue
        kod = kayit.get("componentCode")
        bulunan[val] = kod
        ac = kayit.get("describe") or ""
        ek = ""
        if tur == "H":
            q = q_cikar(ac)
            f_cal = calisma_frekansi(kart, val)
            if not q:
                ek = "Q BILINMIYOR"
                q_uyari.append((val, "veri sayfasinda Q yok"))
            elif f_cal and not (f_cal / Q_FREKANS_PAYI <= q[1]
                                <= f_cal * Q_FREKANS_PAYI):
                ek = "Q=%.0f@%.0fMHz (calisma ~%.0f MHz)" % (
                    q[0], q[1] / 1e6, f_cal / 1e6)
                q_uyari.append((val, "Q %.0f MHz'te verilmis, parca %.0f "
                                "MHz'te calisiyor — karsilastirilamaz"
                                % (q[1] / 1e6, f_cal / 1e6)))
            else:
                ek = "Q=%.0f@%.0fMHz" % (q[0], q[1] / 1e6)
                if q[0] < Q_VARSAYIM[kart]:
                    q_uyari.append((val, "Q=%.0f, simulasyon %.0f varsayiyor"
                                    % (q[0], Q_VARSAYIM[kart])))
        elif tur == "F":
            d = dielektrik(ac)
            ek = d or "dielektrik bilinmiyor"
        stok = kayit.get("stockCount") or 0
        if stok < STOK_RAHAT:
            ek += "  ** STOK INCE **"
        print("   %-9s %-6s x%-4d %-9s stok %-8d %-5s %s"
              % (val, paket, adet, kod, kayit.get("stockCount") or 0,
                 kayit.get("componentLibraryType") or "?", ek))

    if bulgu:
        print("   --- BULUNAMAYAN ---")
        for x in bulgu:
            print("   " + x)
    print("=> KART %s: %d satir kodlandi, %d satir BULUNAMADI"
          % (kart, len(bulunan), len(bulgu)))

    if q_uyari:
        print()
        print("   ** BOBIN Q UYARISI — simulasyon Q=%.0f varsayiyor **"
              % Q_VARSAYIM[kart])
        print("   Asagidaki parcalarin gercek Q'su daha dusuk. Dusuk Q")
        print("   ekleme kaybini buyutur ve bant kenarlarini yuvarlar;")
        print("   yani olculen filtre tepkisi kartta CIKMAZ.")
        for val, sebep in sorted(set(q_uyari)):
            print("      %-9s %s" % (val, sebep))
    if yaz and bulunan:
        hedef = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "logs", "tedarik_%s.json" % kart)
        json.dump(bulunan, open(hedef, "w", encoding="utf-8"), indent=1)
        print("   kodlar yazildi: %s" % hedef)
    return len(bulgu), len(q_uyari)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kartlar", nargs="*", default=None)
    ap.add_argument("--yaz", action="store_true")
    a = ap.parse_args()
    t_bulgu = t_q = 0
    for k in (a.kartlar or ["A", "C", "D"]):
        if k in KARTLAR:
            b, q = kart_isle(k, a.yaz)
            t_bulgu += b
            t_q += q
    print()
    print("TOPLAM %d satir kodlanamadi, %d bobin Q uyarisi" % (t_bulgu, t_q))
    sys.exit(1 if t_bulgu else 0)
