#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""CDC YAPISAL DENETIMI — saat alanlari arasi gecisler kurallara uyuyor mu.

    python3 formal/cdc_denetim.py

NEDEN VAR — VE NEDEN FORMAL ISPAT YETMIYOR.

fifo_cdc_formal.v iki bagimsiz saatle FIFO'yu kanitliyor ve geciyor.
Ama o ispati MUTASYONLA sinadim ve sonuc kotuydu:

    senkronlayici tek kademeye indirildi   -> ispat GECTI
    gray kod kaldirilip ikili gecirildi    -> ispat GECTI

Yani ispat, CDC'nin en klasik iki hatasini yakalamiyor. Sebep temel:
formal cozucu yazmaclari IDEAL modelliyor, metastabilite diye bir sey
yok. Iki kademeli senkronlayici ve gray kod tam da metastabiliteye
karsi var; ideal semantikte ikisinin de yoklugu islevsel bir hata
uretmiyor. "CDC kanitlandi" demek bu yuzden yanlis olurdu.

Formalin yakaladigi sey degerli ve gercek: isaretci aritmetigi,
dolu/bos mantigi, veri butunlugu. Yakalayamadigi sey YAPISAL ve
yapisal olarak denetlenmeli — bu aracin isi o.

DENETLENEN IKI KURAL:

  1 IKI KADEME. Bir saat alanindan digerine gecen her sinyal, hedef
    alanda en az IKI ardisik yazmactan gecmeli. Tek kademe, gelen
    kenarin kurulum penceresine denk gelmesi halinde metastabil bir
    degeri dogrudan mantiga verir.

  2 ILK KADEME BIRLESIMSEL KULLANILMAZ. Ilk senkronlayici yazmacinin
    cikisi, yalnizca ikinci yazmaca gitmeli. Baska bir yere de
    dallanirsa, o dal metastabil degeri gorur ve iki kademenin butun
    faydasi gider. Bu hata gozle cok kolay kaciyor cunku sema dogru
    gorunur.

NASIL: yosys netlisti JSON olarak veriyor; yazmaclarin saatleri ve
veri konileri oradan cikariliyor. Kaynak dosyaya degil, SENTEZLENMIS
DEVREYE bakiliyor — yorum satiri "burasi senkronlayici" dese de
netlist baska bir sey soyluyorsa netlist hakli.
"""
import json
import os
import subprocess
import sys

RTL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rtl")

# Cok saatli moduller. Tek saatli modullerde gecis olamaz.
#
# ust: butun cipte dort saat alani var — clk_sys (80 MHz VCXO),
# clk_eth (PLL'den 125 MHz), adc1/2_dco (ADC'den gelen, kaynak
# senkron) ve rgmii_rxc (PHY'den gelen). Asil denetlenmesi gereken
# yer burasi; fifo_gecis tek basina dogru olsa bile ust duzeyde
# baska bir gecis kacak olabilir.
HEDEFLER = ["fifo_gecis", "ust"]

# GEREKCELI ISTISNALAR — kaynak sinyal adina gore.
#
# Istisna listesi tehlikeli bir seydir: buyudukce arac koreliyor.
# O yuzden her satirin gerekcesi burada ve gerekce OLCULEBILIR
# olmali, "boyle olsun" degil.
ISTISNA = {
    "adc_desen_a":
        "VERI, niteleyicisi desen_dene. Yazilim once deseni yaziyor, "
        "sonra denetimi aciyor; desen, dene yukseldiginde coktan "
        "kararli. Cok bitlik veriyi bit bit senkronlamak zaten yanlis "
        "olurdu — bitler farkli cevrimlerde gecip ara bir deger "
        "uretebilirdi.",
    "adc_desen_b":
        "Ayni gerekce: desen_dene ile niteleniyor.",
}

FF_TURLERI = {"$dff", "$adff", "$sdff", "$dffe", "$adffe", "$sdffe",
              "$aldff", "$dlatch"}


def netlist(modul):
    """yosys ile JSON netlist uret."""
    cikti = "/tmp/cdc_%s.json" % modul
    # ust modul butun hiyerarsiyi istiyor ve DUZLESTIRILMELI:
    # gecisler alt modullerin sinirlarindan geciyor, hiyerarsi
    # duruyorsa koni analizi modul sinirinda durur ve gecisi hic
    # gormez.
    if modul == "ust":
        kaynak = "read_verilog -sv %s/*.v; " % RTL
        duz = "flatten; "
    else:
        kaynak = "read_verilog -sv %s/%s.v; " % (RTL, modul)
        duz = ""
    betik = (kaynak + "hierarchy -top %s; proc; %sopt_clean; "
             "write_json %s" % (modul, duz, cikti))
    r = subprocess.run(["yosys", "-q", "-p", betik],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-800:])
        raise SystemExit("yosys basarisiz: %s" % modul)
    return json.load(open(cikti))


def bit_listesi(x):
    return [b for b in x if isinstance(b, int)]


def coz(mod):
    """Doner: (ff_listesi, cikis_biti -> ff indeksi).

    HUCRE DUZEYINDE, BIT DUZEYINDE DEGIL. Bit duzeyine indirmeyi
    denedim ve daha kotu oldu: yosys birden fazla mantiksal yazmaci
    tek hucrede birlestiriyor, bit indisleri kaynaktaki sinyallere
    karsilik gelmiyor ve dogru RTL yirmi iki bulgu verdi.

    Hucre duzeyinin tek acigi, IKI KADEMELI SENKRONLAYICININ TEK
    HUCREYE sigmasi (reg [1:0] sn; sn <= {sn[0], x};). Onu ayri
    tanimak gerekiyor — asagida kaydirma_mi().
    """
    ffler = []
    suren = {}
    for ad, h in mod["cells"].items():
        if h["type"] not in FF_TURLERI:
            continue
        i = len(ffler)
        clk = tuple(bit_listesi(h["connections"].get("CLK", [])))
        d = bit_listesi(h["connections"].get("D", []))
        q = bit_listesi(h["connections"].get("Q", []))
        ffler.append({"ad": ad, "clk": clk, "d": d, "q": q})
        for b in q:
            suren[b] = i
    return ffler, suren


def kaydirma_mi(f):
    """Hucre kendi cikisini girisine aliyor mu — ic kaydirmali zincir.

    reg [1:0] sn; sn <= {sn[0], x};  yosys'te TEK bir 2 bitlik $dff
    olur: D = {sn[0], x}, Q = {sn[1], sn[0]}. Yani D, kendi Q'sunun
    bir bitini iceriyor. Bu desen bir senkronlayici zinciridir ve
    hucre icinde en az iki kademe demektir.

    Bu ayrimi yapmayan bir arac, dogru yazilmis senkronlayiciya
    "ilk kademe cikisi cok yere dallaniyor" der — kendi ikinci
    kademesini dallanma sanarak.
    """
    return bool(set(f["d"]) & set(f["q"])) and len(f["q"]) >= 2


# KARA KUTU ILKELLERIN PORT YONLERI.
#
# yosys, davranis modeli olmayan hucreler icin port_directions
# vermiyor ve arac ust modulde cakildi. Bu ilkeller tam da gecisin
# oldugu yerler (IDDRX1F rgmii_rxc alaninda ornekliyor), yani
# "tanimadigim hucreyi atla" demek gecisleri kacirmak olurdu.
ILKEL_YON = {
    "IDDRX1F":  {"SCLK": "i", "RST": "i", "D": "i", "Q0": "o", "Q1": "o"},
    "ODDRX1F":  {"SCLK": "i", "RST": "i", "D0": "i", "D1": "i", "Q": "o"},
    "EHXPLLL":  {"CLKI": "i", "CLKFB": "i", "RST": "i", "STDBY": "i",
                 "CLKOP": "o", "CLKOS": "o", "LOCK": "o"},
    "DP16KD":   {},          # blok RAM: veri yolu, gecis tasimiyor
}


def yon(h, port):
    """Port giris mi cikis mi. Kara kutuda tabloya bakiyor."""
    pd = h.get("port_directions")
    if pd:
        return pd.get(port)
    tablo = ILKEL_YON.get(h["type"])
    if tablo is None:
        return None
    y = tablo.get(port)
    return {"i": "input", "o": "output"}.get(y)


def cikis_haritasi(mod):
    """bit -> onu suren hucre. BIR KEZ kuruluyor.

    Once bu harita koni() icinde her cagrida yeniden kuruluyordu.
    fifo_gecis'te (12 yazmac) fark etmiyordu; ust modulde 584 yazmac
    var ve arac saatlerce koserdi.
    """
    hc = {}
    for ad, h in mod["cells"].items():
        for port, baglanti in h["connections"].items():
            if yon(h, port) == "output":
                for b in bit_listesi(baglanti):
                    hc[b] = (ad, h)
    return hc


def koni(mod, bitler, suren, hucre_cikis, derinlik=40):
    """bitler'i suren mantigin geriye dogru kapanisi: ulasilan FF'ler."""
    gorulen = set()
    yigin = list(bitler)
    ffler_bulunan = set()
    adim = 0
    while yigin and adim < derinlik * 200:
        adim += 1
        b = yigin.pop()
        if b in gorulen:
            continue
        gorulen.add(b)
        if b in suren:
            ffler_bulunan.add(suren[b])
            continue                     # FF'te dur, otesine gecme
        if b in hucre_cikis:
            ad, h = hucre_cikis[b]
            for port, baglanti in h["connections"].items():
                if yon(h, port) == "input":
                    yigin.extend(bit_listesi(baglanti))
    return ffler_bulunan


def kullanim_sayisi(mod, bitler):
    """Bu bitleri kac ayri hucre girisi tuketiyor."""
    n = 0
    for ad, h in mod["cells"].items():
        for port, baglanti in h["connections"].items():
            if h["port_directions"].get(port) != "input":
                continue
            if set(bit_listesi(baglanti)) & set(bitler):
                n += 1
                break
    return n


def denetle(modul):
    j = netlist(modul)
    mod = j["modules"][modul]
    ffler, suren = coz(mod)
    hc = cikis_haritasi(mod)
    saatler = {f["clk"] for f in ffler if f["clk"]}
    print("=" * 66)
    print("MODUL %s — %d yazmac, %d saat alani"
          % (modul, len(ffler), len(saatler)))
    if len(saatler) < 2:
        print("   tek saat alani, gecis olamaz")
        return 0

    # bit -> sinyal adi (istisna eslesmesi icin)
    ad_bit = {}
    for ad, h in mod.get("netnames", {}).items():
        for b in bit_listesi(h["bits"]):
            ad_bit.setdefault(b, []).append(ad)

    def kaynak_adlari(k):
        return set(sum((ad_bit.get(b, []) for b in ffler[k]["q"]), []))

    bulgu = []
    istisna_gorulen = set()
    for i, f in enumerate(ffler):
        if not f["clk"]:
            continue
        kaynaklar = koni(mod, f["d"], suren, hc)
        yabanci = [k for k in kaynaklar
                   if ffler[k]["clk"] and ffler[k]["clk"] != f["clk"]]
        if not yabanci:
            continue
        # f = birinci kademe. Cikisi baska nereye gidiyor?
        # ILK KADEME CIKISINI KAC AYRI YAZMAC TUKETIYOR.
        #
        # Burada da hucre degil YAZMAC sayiyoruz: arada reset
        # coklayicisi gibi birlesimsel hucreler olmasi normal, ve
        # onlari saymak yine yanlis alarm uretirdi. Kural, ilk
        # kademenin ikinci kademeden BASKA bir yazmaci beslememesi.
        tuketen_ff = [g for g in ffler
                      if g is not f and i in koni(mod, g["d"], suren, hc)]
        # IKINCI KADEME ARANIRKEN KONI IZLENMELI, BIT ESLESMESI DEGIL.
        #
        # Ilk surumde ikinci kademenin D'sinin ilk kademenin Q'suna
        # DOGRUDAN bagli olmasini bekliyordum ve arac dogru RTL'e iki
        # yanlis alarm verdi. Sebep: senkron resetli bir yazmacta D,
        # bir coklayicinin cikisi (rst ? 0 : q1), yani bitler
        # eslesmiyor. Arada mantik olmasi normal; onemli olan ikinci
        # yazmacin girisinin ILK yazmaca DAYANMASI.
        ikinci = [g for g in ffler
                  if g is not f and g["clk"] == f["clk"]
                  and i in koni(mod, g["d"], suren, hc)]
        # kaynagin tamami gerekceli istisnaysa atla
        istisna_adlari = set()
        hepsi_istisna = True
        for k in yabanci:
            adlar = kaynak_adlari(k) & set(ISTISNA)
            if adlar:
                istisna_adlari |= adlar
            else:
                hepsi_istisna = False
        if hepsi_istisna and istisna_adlari:
            istisna_gorulen |= istisna_adlari
            continue

        if kaydirma_mi(f):
            # ic kaydirmali zincir: kademe sayisi hucre genisligi
            continue
        if not ikinci:
            bulgu.append("%s: alanlar arasi gecisin IKINCI KADEMESI YOK"
                         % f["ad"])
        elif len(tuketen_ff) > 1:
            bulgu.append("%s: ilk kademe cikisi %d yazmaci besliyor "
                         "(sadece ikinci kademeye gitmeli)"
                         % (f["ad"], len(tuketen_ff)))

    for a in sorted(istisna_gorulen):
        print("   [gerekceli istisna] %s" % a)
        print("      %s" % ISTISNA[a])
    for x in bulgu:
        print("   ** " + x)
    if not bulgu:
        print("   iki kademe kurali saglaniyor")
    print("=> %s: %d bulgu" % (modul, len(bulgu)))
    return len(bulgu)


if __name__ == "__main__":
    toplam = 0
    for m in (sys.argv[1:] or HEDEFLER):
        toplam += denetle(m)
    print()
    print("TOPLAM %d bulgu" % toplam)
    sys.exit(1 if toplam else 0)
