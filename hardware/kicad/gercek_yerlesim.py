#!/usr/bin/env python3
"""Gercek yerlesim: kritik parcalar ELLE, gerisi onlarin dibine.

    python3 gercek_yerlesim.py A

Neden bu dosya var: kuvvet-guduml u eniyileme baglanti uzunlugunu
kisaltiyor ama BASILAMAYAN kart uretiyordu — 19 konnektorun 18'i
kartin ortasinda kaliyordu. Kartin ortasina kablo takilamaz.

Ve daha onemlisi: bu aletin butun degeri FAZ UYUMU. Onu saglayan sey
kisa yol degil, ESIT ve OZDES yol:
  - saat tamponu iki ADC'nin TAM ORTASINDA, LVDS ciftleri esit
  - dort alis zinciri BIREBIR AYNI geometri, sadece otelenmis
  - dort veris zinciri ayni
Bunlari algoritma bulamaz, cunku olctugu sey toplam uzunluk; simetri
onun amac fonksiyonunda yok.

Yontem: blok = AG DESENIYLE bulunan parca kumesi. RX zinciri A1'e ait
parcalar RF_A1 / SEC_A1 / VIN_A1 aglarina bagli olanlardir. Bu sema
degisse de gecerli kalir; referans numarasi elle yazilmiyor.
"""
import math, os, re, subprocess, sys
import pcbnew

MM = 1000000
HERE = os.path.dirname(os.path.abspath(__file__))
GUC = re.compile(r"^(GND|\+|VIN_PROT|CHASSIS|GND_HDR|GND_STRAP|GND_MODE)")


# ref -> sema sayfasi. padnetler dolduruyor.
# NEDEN: "regulatorun kendi cikis kondansatoru" ile "ayni raydaki
# baska bir entegrenin ayristirma kondansatoru" agdan ayirt
# edilemiyor — ikisi de {+3V3, GND}. Sema sayfasi ayirt ediyor:
# regulatorun kondansatoru guc sayfasinda cizildi.
SAYFA = {}


def padnetler(dizin, proj):
    out = f"/tmp/gy_{proj}.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist",
                    os.path.join(HERE, dizin, proj + ".kicad_sch"),
                    "-o", out, "--format", "kicadsexpr"],
                   capture_output=True, check=True)
    t = open(out, encoding="utf-8").read()
    pn = {}
    SAYFA.clear()
    for m in re.finditer(
            r'\(comp\s*\(ref "([^"]+)"\).*?\(sheetpath\s*\(names "([^"]*)"\)',
            t, re.S):
        SAYFA[m.group(1)] = m.group(2).strip("/")
    for m in re.finditer(
            r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', t, re.S):
        ag, body = m.groups()
        for ref, pad in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body):
            pn.setdefault(ref, {})[pad] = ag
    return pn


def ag_ile(pn, desen, haric=()):
    """Deseni tutan aga bagli parcalar, ag sirasina gore."""
    r = re.compile(desen)
    bulunan = {}
    for ref, padlar in pn.items():
        if ref in haric:
            continue
        for ag in padlar.values():
            m = r.match(ag)
            if m:
                # sira: desendeki grup numarasi varsa ona gore
                s = bulunan.get(ref, 99)
                bulunan[ref] = min(s, r.match(ag).lastindex or 0
                                   if r.match(ag).groups() else 0)
    return bulunan


# Kenar montaj konnektorlerinde GOVDE KARTIN DISINA bakmali.
# SMA ayak izinde govde pedlerden +X yonune uzuyor (courtyard merkezi
# +5.7 mm'de). Sol kenara 0 derece ile koyunca govde kartin ICINE
# bakiyor — konnektor takilamaz. KiCad'de donme ekrandan saat yonunun
# tersi, Y ekseni asagi: 180 sol, 0 sag, 90 ust, 270 alt.
# Pedin dis yuzu kenardan bu kadar iceride.
# 0.3 -> 0.6 -> 0. Once "DSN sinirini 0.5 mm iceri cekince ped
# tamamen yonlendirilebilir alanda kalsin" diye 0.6 yazmistim. O
# gerekce yanlisti: yonlendiricinin pedin TAMAMINI gormesi gerekmiyor,
# bir yerinden tutmasi yetiyor ve launch pedi 5.08 mm derin — 0.5 mm
# kirpildiktan sonra 4.58 mm erisilebilir bakir kaliyor.
# Bosluk birakmanin bedeli ise gercek: bu konnektorun toprak
# tirnaklari kartin kenarina KENETLENIYOR (kart, konnektorun yarigina
# giriyor). Ped kenardan geride kalirsa tirnak pede degmez ve RF
# girisinin toprak donusu hic olusmaz.
# Hedef: pedin dis ucu Edge.Cuts cizgisinin DIS SINIRIYLA hizali.
# 0.0 denedim: ped dis ucu tam merkez cizgide olunca DRC her kenar
# montaj pedinde copper_edge_clearance veriyor (A 45, C 60, D 10).
# Sebep olculdu: Edge.Cuts bir CIZGI ve genisligi 0.1 mm, yani
# -0.05..+0.05 arasini kapliyor. KiCad boslugu cizginin SEKLINE gore
# olcuyor, merkezine gore degil; ped 0.00'da baslayinca cizginin ic
# yarisiyla 0.05 mm ortusuyor ve bosluk NEGATIF cikiyor. Negatif
# boslugu hicbir kural (min 0mm dahil) karsilayamaz, o yuzden
# .kicad_dru muafiyeti de kurtarmiyordu.
# 0.05 mm iceri: ped cizginin dis sinirina dayaniyor, bosluk tam 0
# oluyor ve muafiyet gecerli hale geliyor. Frezenin yolu merkez
# cizgi oldugu icin fiziksel olarak hala hizali — 0.05 mm, kesim
# toleransinin (+-0.15 mm) ucte biri.
PED_ICERI = 0.05
KART_OLCU = [0, 0]   # uygula() dolduruyor

KENAR_ACI = {"sol": 180, "sag": 0, "ust": 90, "alt": 270}


def kenar_aci(x, y, en, boy):
    """En yakin kenara gore govdeyi disari cevirecek aci."""
    d = {"sol": x, "sag": en - x, "ust": y, "alt": boy - y}
    return KENAR_ACI[min(d, key=d.get)]


def koy(fps, ref, x, y, aci=None, kondu=None, kenar=False,
        kenar_govde=False):
    """Parcayi (x, y) noktasina koy — GOVDESININ MERKEZI orada olacak.

    AYAK IZI ORIJINI GOVDE MERKEZI DEGIL. Cogu parcada ikisi cakisir
    ama THT rolelerde ve konnektorlerde orijin genelde 1 numarali
    pedde duruyor: G2RL-2'de aradaki fark 12 mm. Orijine gore
    koyunca role govdesi kat planinin 12 mm disina tasiyor ve
    surucusunun uzerine oturuyordu. Once yerlestir, sonra courtyard
    merkezinin nereye dustugune bak, farki geri al.
    """
    fp = fps.get(ref)
    if fp is None:
        return False
    if aci is not None:
        fp.SetOrientationDegrees(aci)
    hedef = pcbnew.VECTOR2I(int(round(x * 20) / 20 * MM),
                            int(round(y * 20) / 20 * MM))
    fp.SetPosition(hedef)
    # KENAR MONTAJ: GOVDE DISARI, PEDLER ICERI.
    # Once ayak izini kenardan 0.5 mm iceri koyuyordum. Govde dogru
    # tarafa bakiyordu ama PEDLER kartin disina tasti — uc kartta
    # toplam 208 ped. Lehimlenecek bakir orada yok; konnektor
    # takilamaz.
    # Dogrusu pedlerin DIS yuzunu kart kenariyla hizalamak: pedler
    # tamamen bakirin uzerinde, govde kenarin otesine sarkiyor.
    # THT KENAR PARCASI: GOVDE ICERI, ON YUZ KENARLA HIZALI.
    # RJ45'in butun pedleri govdenin icinde; pede gore hizalarsak
    # govde disari sarkar ve kart uzerinde yeri kalmaz. Ama jak
    # kenardan 7 mm iceri de kalamaz — o zaman kablo fisi kartin
    # kenarina carpar, takilmaz. Dogrusu COURTYARD'in dis yuzunu
    # kart kenariyla hizalamak.
    if kenar_govde:
        katm = (pcbnew.B_CrtYd if fp.GetLayer() == pcbnew.B_Cu
                else pcbnew.F_CrtYd)
        try:
            c = fp.GetCourtyard(katm).BBox()
        except Exception:
            c = None
        if c is not None and c.GetWidth() > 0 and KART_OLCU[0]:
            en_k, boy_k = KART_OLCU
            sol, sag = c.GetLeft() / MM, c.GetRight() / MM
            ust, alt = c.GetTop() / MM, c.GetBottom() / MM
            d = {"sol": x, "sag": en_k - x, "ust": y, "alt": boy_k - y}
            yon = min(d, key=d.get)
            q = fp.GetPosition()
            dx = dy = 0.0
            if yon == "sol":
                dx = -sol
            elif yon == "sag":
                dx = en_k - sag
            elif yon == "ust":
                dy = -ust
            else:
                dy = boy_k - alt
            fp.SetPosition(pcbnew.VECTOR2I(int(q.x + dx * MM),
                                           int(q.y + dy * MM)))
        if kondu is not None:
            kondu.add(ref)
        return True
    if kenar:
        pedler = list(fp.Pads())
        if pedler and KART_OLCU[0]:
            en_k, boy_k = KART_OLCU
            # PED KUTUSU DONMUS HALDE ALINMALI.
            # Once GetSizeX()/GetSizeY() kullaniyordum. Bunlar pedin
            # KENDI cercevesindeki olculer — donme uygulanmamis.
            # Ustelik butun pedlerin en buyugu alinip hem x hem y icin
            # ayni sayi kullaniliyordu; SMA'da 5.08 mm'lik launch pedi
            # ile 1.6 mm'lik toprak pedleri karisti.
            #
            # Hata YONE GORE ISARET DEGISTIRIYORDU, o yuzden tek bir
            # duzeltmeyle kapanmiyordu:
            #   180 derece (sol/sag kenar) : ped 1.14 mm KART DISINDA
            #    90 derece (ust kenar)     : ped 0.65 mm ICERIDE
            # Disari tasan bakir uretimde YOK — freze onu kesiyor,
            # 5.08 mm'lik launch pedi 3.94 mm'ye iniyor ve kenarda
            # kesilmis bakir kaliyor. Iceride kalan da kotu: bu
            # konnektorun toprak tirnaklari kartin kenarina
            # KENETLENIYOR, 0.65 mm boslukta tirnak pede degmiyor ve
            # RF girisinin toprak donusu hic olusmuyor.
            #
            # GetBoundingBox() donmeyi zaten uygulanmis veriyor.
            kutular = [q.GetBoundingBox() for q in pedler]
            sol = min(q.GetLeft() for q in kutular) / MM
            sag = max(q.GetRight() for q in kutular) / MM
            ust = min(q.GetTop() for q in kutular) / MM
            alt = max(q.GetBottom() for q in kutular) / MM
            # hangi kenara yakinsa o kenara hizala
            d = {"sol": x, "sag": en_k - x, "ust": y, "alt": boy_k - y}
            yon = min(d, key=d.get)
            p = fp.GetPosition()
            dx = dy = 0.0
            if yon == "sol":
                dx = (PED_ICERI - sol)
            elif yon == "sag":
                dx = (en_k - PED_ICERI) - sag
            elif yon == "ust":
                dy = (PED_ICERI - ust)
            else:
                dy = (boy_k - PED_ICERI) - alt
            fp.SetPosition(pcbnew.VECTOR2I(int(p.x + dx * MM),
                                           int(p.y + dy * MM)))
        if kondu is not None:
            kondu.add(ref)
        return True
    kat = pcbnew.B_CrtYd if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_CrtYd
    try:
        c = fp.GetCourtyard(kat).BBox()
        if c.GetWidth() > 0:
            m = c.GetCenter()
            fp.SetPosition(pcbnew.VECTOR2I(
                hedef.x + (hedef.x - m.x), hedef.y + (hedef.y - m.y)))
    except Exception:
        pass
    if kondu is not None:
        kondu.add(ref)
    return True


# ==================================================================== A karti
# Kat plani, 200 x 210 mm:
#
#   0     20      55        95       135      175  200
# 0 +--------------------------------------------------+
#   | RX1 SMA==zincir==>[ADC ]        [SDRAM]   [GUC]  |
# 45| RX2 SMA==zincir==>[U20 ]                         |
#   |                                                  |
# 85|   [VCXO]  [ADCLK846]    [ FPGA U10 ]   [PHY1][MJ]|
#   |            ^ iki ADC'nin TAM ORTASI    [PHY2][MJ]|
# 125| RX3 SMA==zincir==>[ADC ]                        |
#   | RX4 SMA==zincir==>[U21 ]                         |
# 165| [DAC U30][DAC U31] ==> trafo ==> TX SMA (alt)   |
# 210+--------------------------------------------------+

# ECP5 BGA-256'da banka konumlari (ayak izi merkezine gore, olculdu):
#   banka 6 ADC   sol-ALT     banka 7 SDRAM  sol-UST
#   banka 2 DAC   sag-UST     banka 3 PHY    sag-ALT
#   banka 0/1 kontrol  UST
# Cevre parcalar KENDI BANKALARININ tarafina konuyor. Yanlis tarafa
# koymak veri yolunun kalibin altindan gecmesi demek: 15-32 hatlik bir
# yol butun cipi dolasir, hem uzar hem birbirine kuple olur.
A_EN, A_BOY = 235, 225
# alis kanallari: (ad, y, ADC referansi)
# Alis: dort SMA sol kenarda, ADC'ler banka 6 hizasinda (sol-ALT)
A_RX = [("A1", 120, "U20"), ("B1", 145, "U20"),
        ("A2", 180, "U21"), ("B2", 205, "U21")]
A_ADC_Y = {"U20": 132.5, "U21": 192.5}
# zincir icindeki x konumlari (kanal y'sine gore)
A_ZINCIR_X = dict(sma=6, term=18, trafo=30, seri=44, dif=51)
A_ADC_X = 64
# saat: IKI ADC'NIN ORTASI
A_SAAT_Y = (A_ADC_Y["U20"] + A_ADC_Y["U21"]) / 2      # = 87.5
A_VCXO = (30, A_SAAT_Y)
A_BUF = (A_ADC_X, A_SAAT_Y)          # ADCLK846, ADC'lerle AYNI X
# veris kanallari: (ad, x) — alt kenarda SMA
A_TX = [("1", 150), ("2", 172), ("3", 194), ("4", 216)]
A_TX_SMA_Y = 0.5      # DAC banka 2 = sag-UST, veris UST kenardan cikiyor
A_DAC = {"U30": (180, 40), "U31": (180, 68)}


def yerlesim_A(fps, pn, kondu):
    n = 0
    # ---------- dort alis zinciri, BIREBIR AYNI geometri
    for ad, y, adc in A_RX:
        # zincirdeki parcalar: ag adindan bulunuyor
        sma = [r for r, p in pn.items() if f"RF_{ad}" in p.values()
               and r.startswith("J")]
        term = [r for r, p in pn.items() if f"RF_{ad}" in p.values()
                and r.startswith("R")]
        trafo = [r for r, p in pn.items() if f"RF_{ad}" in p.values()
                 and r.startswith("T")]
        seri = sorted(r for r, p in pn.items()
                      if any(v.startswith(f"SEC_{ad}_") for v in p.values())
                      and r.startswith("R"))
        dif = [r for r, p in pn.items()
               if sum(1 for v in p.values() if v.startswith(f"VIN_{ad}_")) == 2
               and r.startswith("C")]
        for r in sma:
            # sol kenar: govde disari
            n += koy(fps, r, 0.5, y, KENAR_ACI["sol"], kondu, kenar=True)
        for r in term:
            n += koy(fps, r, A_ZINCIR_X["term"], y + 5, 90, kondu)
        for r in trafo:
            n += koy(fps, r, A_ZINCIR_X["trafo"], y, 0, kondu)
        for i, r in enumerate(seri[:2]):
            n += koy(fps, r, A_ZINCIR_X["seri"], y - 2.5 + i * 5, 0, kondu)
        for r in dif:
            # 90 DEGIL 270 — FARK CIFTI CAPRAZLANMASIN.
            # Seri dirençlerde P ustte (y-2.5), N altta (y+2.5).
            # Kondansator 90 derecede ped 1'i ALTA aliyordu:
            #     R'de  P 117.50  N 122.50
            #     C'de  P 120.78  N 119.22     <- ters
            # Iki ag kondansatorde yer degistiriyor, yani bakir
            # cizilirken caprazlanmak zorunda ve tek katmanda
            # caprazlanma imkansiz: yonlendirici bir bacaga VIA
            # koyuyor — tam ADC'nin analog girisinde, kartin en
            # hassas noktasinda. Via hem endüktans hem cift icinde
            # uzunluk farki demek.
            # 270 derece ped sirasini ters ceviriyor ve dizilim
            # dirençlerle ortusuyor. Dort kanalda da ayni.
            n += koy(fps, r, A_ZINCIR_X["dif"], y, 270, kondu)
    # ---------- ADC'ler
    for adc, y in A_ADC_Y.items():
        n += koy(fps, adc, A_ADC_X, y, 0, kondu)
    # ---------- saat adasi: tampon iki ADC'nin TAM ORTASINDA
    n += koy(fps, "Y10", *A_VCXO, 0, kondu)
    n += koy(fps, "U15", *A_BUF, 0, kondu)
    # ---------- LVDS SONLANDIRMASI ALICININ DIBINDE
    # R220/R221 genel dolguya dusuyordu: ADC'nin saat pininden 23.4 ve
    # 11.3 mm otede. 100R sonlandirma hattin SONUNDA ise ise yarar;
    # 23 mm geride birakilirsa aradaki parca sonlandirilmamis bir sap
    # olur. Sinyal sonlandirmayi gecip ADC'ye gidiyor, empedans
    # suregelmedigi icin yansiyip geri donuyor. FR4'te 23 mm ~155 ps,
    # gidis-donus ~310 ps; o yansima ornekleme kenarinin uzerine
    # biniyor ve kenar jitter'ine donusuyor.
    # Bu kartta jitter butcesi 81 fs (VCXO 60 fs + ADCLK846 54 fs) ve
    # 30 MHz'te 96 dB SNR tavani ona dayaniyor. Sonlandirmayi yanlis
    # yere koymak, 60 fs'lik osilatoru ve ADCLK846'yi secmenin butun
    # anlamini goturuyor.
    # Iki sonlandirma da kendi ADC'sine gore AYNI geometride: saat
    # pininin 3.6 mm solunda. Boylece iki kanalin sapi da ozdes.
    for adc, r in (("U20", "R220"), ("U21", "R221")):
        if adc not in fps or r not in fps:
            continue
        sp = [q.GetPosition() for q in fps[adc].Pads()
              if q.GetNetname().startswith(f"ADCLK_{adc}")]
        if not sp:
            continue
        px = min(q.x for q in sp) / MM
        py = sum(q.y for q in sp) / len(sp) / MM
        n += koy(fps, r, px - 3.6, py, 90, kondu)
    # ---------- FPGA saatinin LVDS alicisi, TAMPONUN DIBINDE
    # U18 (SN65LVDS2) tampondan gelen LVDS cifti tek uclu 3.3 V
    # CMOS'a cevirip FPGA'nin K16 saat ball'una veriyor. Genel
    # dolguya birakinca U15'ten 28.8 mm oteye dustu: diferansiyel
    # cift o mesafeyi kart ortasindan gecerek kat ediyor ve
    # yol boyunca ortak mod gurultusu topluyor.
    # 12 mm oteye, FPGA tarafina: cift kisa kaliyor, tek uclu
    # cikis da zaten gurultuye LVDS'ten daha dayanikli oldugu icin
    # uzun olan kismi o tasiyor.
    # R222 (100R sonlandirma) ALICININ dibinde olmali — sonlandirma
    # hattin sonunda ise ise yariyor, ortasinda degil.
    n += koy(fps, "U18", A_BUF[0] + 12, A_BUF[1] - 7, 0, kondu)
    n += koy(fps, "R222", A_BUF[0] + 12, A_BUF[1] - 11, 90, kondu)
    # ---------- FPGA, SDRAM
    n += koy(fps, "U10", 130, 120, 0, kondu)
    # SDRAM banka 7 = sol-UST
    n += koy(fps, "U50", 95, 65, 0, kondu)
    # ---------- ethernet: PHY ic, magjack SAG KENARDA
    # PHY banka 3 = sag-ALT
    for i, (phy, mj, y) in enumerate((("U40", "J40", 150), ("U41", "J41", 190))):
        n += koy(fps, phy, 195, y, 0, kondu)
        # magjack THT: govdesi kart uzerinde, on yuzu kenarla hizali
        n += koy(fps, mj, A_EN - 1, y, 270, kondu, kenar_govde=True)
    # ---------- DAC ve veris zinciri, ALT
    for d, (x, y) in A_DAC.items():
        n += koy(fps, d, x, y, 0, kondu)
    for ad, x in A_TX:
        sma = [r for r, p in pn.items() if f"TX_{ad}" in p.values()
               and r.startswith("J")]
        trafo = [r for r, p in pn.items() if f"TX_{ad}" in p.values()
                 and r.startswith("T")]
        son = sorted(r for r, p in pn.items()
                     if any(v.startswith(f"IOUT{ad}") for v in p.values())
                     and r.startswith("R"))
        for r in sma:
            # UST kenar: govde yukari/disari
            n += koy(fps, r, x, 0.5, KENAR_ACI["ust"], kondu, kenar=True)
        for r in trafo:
            n += koy(fps, r, x, 16, 0, kondu)
        for i, r in enumerate(son[:2]):
            n += koy(fps, r, x - 6 + i * 12, 26, 90, kondu)
    # ---------- guc: SAG UST KOSE, ADC'den en uzak
    # XT60 govdesi buyuk (kablo girisi dahil ~25 mm); regulatorler
    # onun altina kaymali, yoksa U1 XT60'in icine giriyor.
    n += koy(fps, "J1", 14, 6, 0, kondu)
    # IKI BUCK YAPISKAN GRUP OLARAK. Once U1/U2 ve L1/L2 tek tek
    # konuyordu ve bobin 20 mm oteye dusuyordu: bir alicinin en
    # yuksek dv/dt'li dugumu, on ucun 20 mm yaninda 2 cm'lik bir
    # bakir levha olarak duruyordu. Simdi zincir bir butun:
    #   [giris C] [IC] [bobin] [cikis C]
    # Blok saga uzaniyor (aci=0), IC x=20'de basliyor, en fazla
    # ~16 mm yer kapliyor — sag komsusu LED sirasi x=92'de.
    n += regulator_blok(fps, pn, kondu, "U1", "L1", 28, 42, 0,
                        cin=("C4", "C3"), cout=("C1",))
    n += regulator_blok(fps, pn, kondu, "U2", "L2", 28, 66, 0,
                        cin=("C6", "C5"), cout=("C2",))
    # ---------- durum LED'leri: UST KENAR, SOL. Kartin o kosesi bostu
    # ve LED'in gorunur olmasi gerekiyor — kasada on panele en yakin
    # yer burasi. DC surulduklerinden FPGA'ya olan uzun yol onemsiz.
    # x=24'ten baslatmistim; orasi guc girisi kosesi (XT60 + ters
    # kutup FET'i) ve LED sirasi onlari sikistirdi. 92'den sonrasi
    # gercekten bos.
    for i in range(4):
        lx = 92 + i * 14
        n += koy(fps, f"D{60 + i}", lx, 8, 90, kondu)
        n += koy(fps, f"R{60 + i}", lx, 15, 90, kondu)

    # ---------- konfig, kontrol: SAG ALT
    # 10 MHz referans SMA: sol kenar
    n += koy(fps, "J61", 0.5, 75, KENAR_ACI["sol"], kondu, kenar=True)
    # magjack'ler sag kenarda, agiz disari
    # KART ARASI KONNEKTORLER ALT KENARDA, magjack'ler sag kenarda.
    # Ucu de sag kenara koymustum, iki PHY magjack'i (y=150 ve 190)
    # ayni kenari paylasiyor ve ust uste biniyorlardi. Ayrica C ve D
    # kartlarina giden RF baglantilari zaten alt-sol RF/DAC bolgesine
    # ait; alt kenar hem cakismayi bitiriyor hem yolu kisaltiyor.
    for r, (x, y) in (("U11", (150, 130)), ("J10", (A_EN - 10, 118)),
                      ("SW1", (150, 145)),
                      # Alt sira sola sikistirildi: J66 sag ucta dururken 2 mm'lik kenar
                      # kusagi onu iceri itti ve J41 magjack'inin govdesine girdi.
                      ("J60", (40, A_BOY - 8)), ("J62", (68, A_BOY - 8)),
                      ("J64", (96, A_BOY - 8)), ("J63", (126, A_BOY - 8)),
                      ("J65", (158, A_BOY - 8)), ("J66", (188, A_BOY - 8))):
        n += koy(fps, r, x, y, 0, kondu)
    return n


def ayristirma_topa(fps, pn, kondu):
    """Her ayristirma kondansatorunu BESLEDIGI TOPUN dibine koy.

    "Entegrenin yanina" yetmiyor. Pin basina 100nF'in tek anlami o
    BACAGIN dibinde olmasi: kondansatorden topa giden yolun endüktansi
    kondansatorun faydasini yiyor. BGA'da her besleme topunun altina
    bir tane dusmeli, sirayla degil.

    Ayni raya birden cok kondansator varsa her biri AYRI topa gidiyor.
    """
    n = 0
    # ray -> o raya bagli, henuz kullanilmamis toplar (entegre basina)
    kullanilan = {}
    for ref in sorted(fps):
        padlar = pn.get(ref, {})
        if not ref.startswith("C") or len(padlar) != 2:
            continue
        # YAPISKAN GRUBUN KONDANSATORUNE DOKUNMA.
        # Bu fonksiyon ayristirma kondansatorlerini besledikleri
        # BACAGIN dibine tasiyor ve bunu `kondu`ya bakmadan yapiyordu:
        # regulator blogunun giris/cikis kondansatorlerini de alip
        # goturdu (D'de C650/C651 blogun 200 mm otesine dustu).
        # Regulator kondansatoru ayristirma kondansatoru DEGIL;
        # yeri cevrim geometrisiyle belirlendi, bacak yakinligiyla
        # degil.
        if ref in BLOK_SABIT:
            continue
        aglar = set(padlar.values())
        if "GND" not in aglar:
            continue
        ray = next((a for a in aglar if a != "GND"), None)
        if not ray or not ray.startswith("+"):
            continue
        # RAYIN BUTUN ENTEGRELERINE DAGIT.
        # Once "bu rayi en cok kullanan entegre" diye tek bir hedef
        # seciyordum. +3V3 gibi genis bir rayda otuz kondansatorun
        # hepsi FPGA'ya gidiyordu; onun ball'lari bitince gerisi genel
        # dolguya dusuyordu ve kartin ortasinda besleme bacagindan
        # 30 mm uzakta dikey bir kolon olusuyordu. 75 kondansatorun
        # sadece 23'u bacaginin 3 mm yakinindaydi.
        # Simdi rayin butun (entegre, ped) ciftleri tek havuzda ve
        # entegreler ARASINDA dolasarak veriliyor: her entegre kendi
        # bacak sayisiyla orantili pay aliyor, kimse ac kalmiyor.
        havuz = kullanilan.get(ray)
        if havuz is None:
            per_ic = []
            for r in sorted(kondu):
                if not r.startswith("U") or r not in fps:
                    continue
                ps = [q for q in fps[r].Pads() if q.GetNetname() == ray]
                if ps:
                    per_ic.append((r, ps))
            # entegreler arasinda dolasarak sirala
            havuz = []
            i = 0
            while any(ps for _, ps in per_ic):
                for r, ps in per_ic:
                    if ps:
                        havuz.append((r, ps.pop(0)))
                i += 1
            kullanilan[ray] = havuz
        if not havuz:
            continue
        # Kondansator pedden COK ise bastan dolas: ayni bacaga ikinci
        # bir kondansator zararsiz (biri yuksek frekans, oteki toplu).
        ic, pad = havuz[n % len(havuz)] if len(havuz) else (None, None)
        ic, pad = havuz.pop(0) if havuz else (ic, pad)
        havuz.append((ic, pad))
        if pad is None:
            continue
        q = pad.GetPosition()
        # SIK ADIMLI GOVDEDE ALT YUZEYE. BGA'da toplar 0.8 mm adimla
        # diziliyor; aralarina 0402 sigmaz — 104 cakisma boyle cikti.
        # Dogrusu kondansatoru kartin ALTINA, topun TAM ALTINA koymak:
        # yol sadece via boyu kadar, endüktans en az. Zaten butun
        # ciddi BGA tasarimlari boyle yapiyor.
        ped_sayisi = len(list(fps[ic].Pads()))
        if ped_sayisi > 100:
            # BGA ALTI, KABA IZGARADA. Top basina bir kondansator
            # fiziksel olarak imkansiz: toplar 0.8 mm adimla, 0402'nin
            # courtyard'i 1.5 mm. Alt yuzeye gecirmek de yetmedi, orada
            # da ust uste bindiler (244 cakisma).
            # Gercek tasarimlar BGA altina 8-12 kondansator koyar,
            # 2.5 mm izgarada; her biri en yakin topa via ile baglanir.
            # Via boyu kadar yol, ki asil onemli olan o.
            c = fps[ic].GetPosition()
            sayac = kullanilan.setdefault(("izgara", ic), [0])
            k = sayac[0]
            sayac[0] += 1
            sut = 5
            gx = c.x / MM - 5.0 + (k % sut) * 2.5
            gy = c.y / MM - 5.0 + (k // sut) * 2.5
            fp = fps[ref]
            if fp.GetLayer() != pcbnew.B_Cu:
                fp.Flip(fp.GetPosition(), False)
            koy(fps, ref, gx, gy, 0, kondu)
        else:
            c = fps[ic].GetPosition()
            dx = 1 if q.x >= c.x else -1
            dy = 1 if q.y >= c.y else -1
            # HEDEF ENTEGRE BIR YAPISKAN GRUBUN ICINDEYSE DAHA UZAGA.
            # Blogun etrafinda 0.5 mm'lik dikisler var; bacagin 1.9 mm
            # yaninda yer YOK. Oraya konan kondansator iki sabit parca
            # arasina sikisip kaliyordu: ayirici onu bir taraftan
            # itip oteki taraftan geri itiyor, cakisma hic
            # cozulmuyordu (A'da C227).
            uzak = 6.5 if ic in BLOK_SABIT else 1.9
            koy(fps, ref, q.x / MM + dx * uzak, q.y / MM + dy * uzak,
                0, kondu)
        n += 1
    return n


def guc_bacaklari(kart):
    """Netlist'ten (ref, ped) -> pintype == power_in kumesi.

    NEDEN GEREKLI. Bir entegrenin bir guc rayina bagli olmasi, o
    bacagin BESLEME oldugu anlamina gelmiyor. C kartinda +3V3'e
    yirmi yedi entegre bagli ama bunlarin on altisi DRV8833 ve
    tek baglantilari ~SLEEP, yani lojik girisi. Ayni sekilde
    74HC595'in ~SRCLR'i ve PE4312'nin P/S'i de raya cekilmis
    lojik girisleri.

    Bu ayrimi yapmadan olcunce C'de "42 besleme bacagina 15
    kondansator" cikiyor ve kart 27 kondansator eksik gorunuyor.
    Gercekte 15 besleme bacagi var ve 15 kondansator: yeterli.
    Ayrim yapilmadan bu fonksiyon da 27 entegreyi 15 kondansatorle
    doyurmaya calisip kondansatorleri ileri geri tasiyordu.

    KiCad netlist'i pintype tasiyor; kaynak orasi.
    """
    import re
    yol = "/tmp/pcb_dogrudan_sdr_%s.net" % kart
    try:
        s = open(yol, errors="ignore").read()
    except OSError:
        return None
    # DUGUM BAZLI AYRISTIRMA. Tek bir regex ile denedim ve SIFIR
    # sonuc verdi: pasif pinlerde node icinde uc alan var, entegre
    # pinlerinde arada bir de (pinfunction "VCC") duruyor ve
    # ardisik desen kiriliyor. Alanlari blok icinde ayri ayri
    # ariyoruz.
    out = set()
    for blok in s.split("(node")[1:]:
        blok = blok[:400]
        r = re.search(r'\(ref "([^"]+)"\)', blok)
        pn_ = re.search(r'\(pin "([^"]+)"\)', blok)
        tp = re.search(r'\(pintype "([^"]+)"\)', blok)
        if r and pn_ and tp and tp.group(1).startswith("power_in"):
            out.add((r.group(1), pn_.group(1)))
    return out or None


def ac_kalanlara_kondansator(fps, pn, kondu, sinir_mm=5.0, kart=None):
    """Yakininda kondansatoru olmayan her entegreye bir tane cek.

    NEDEN AYRI BIR GECIS. ayristirma_topa raya bagli butun entegreler
    arasinda dolasarak dagitiyor ve bu, cok bacakli parcalar icin
    calisiyor. Ama az bacakli bir parca (bir LDO'nun tek cikis
    bacagi gibi) havuzda tek sira aliyor ve kondansator sayisi
    yetmeyince eli bos kaliyor.

    Olculdu: A kartinda U4 ve U9 (ADP150) icin en yakin kondansator
    31 ve 21 mm otedeydi. ADP150 veri sayfasi cikisa yakin 1 uF
    istiyor; 31 mm oteki bir cikis kondansatoru regulatoru kararli
    yapmaz. C kartinda dort PE4312'nin dordu de ayni durumdaydi.

    Bu gecis en sonda kosuyor: her (entegre, guc rayi) cifti icin
    sinir_mm icinde bir kondansator var mi diye bakiyor, yoksa o
    raydaki EN YAKIN kondansatoru bacagin dibine tasiyor. Tasinan
    kondansator baska bir entegrenin tek kondansatoru ise
    dokunulmuyor — birini doyurup otekini ac birakmak kazanc degil.
    """
    import math
    tasinan = 0
    # SADECE KUCUK DEGERLI KONDANSATOR AYIRMA SAYILIR.
    #
    # Once her kondansatoru sayiyordum. Olculdu: A'da U11'in 5.5 mm
    # yakininda 10 uF, 16.3 mm'de 47 uF var — ikisi de TOPLU
    # kondansator. En yakin 100 nF ise 17.0 mm'de. Bu gecis "yakinda
    # kondansator var" deyip gecti, oysa 10 uF'nin ESR ve ESL'i
    # yuksek frekansta ayirma yapmiyor; besleme bacaginin ihtiyaci
    # olan seyi vermiyor.
    #
    # Sinir 1 uF: X7R 0402/0603'te 100 nF ve 1 uF ayirma, 10 uF ve
    # ustu toplu. sema_denetim ayni ayrimi yapiyor (AYIRMA_UST).
    def _kucuk(ref):
        v = fps[ref].GetValue().strip().lower().replace(" ", "")
        m = re.match(r"([\d.]+)\s*([pnu\u00b5m]?)f?", v)
        if not m:
            return False
        try:
            x = float(m.group(1))
        except ValueError:
            return False
        carp = {"p": 1e-6, "n": 1e-3, "u": 1.0, "\u00b5": 1.0, "m": 1e3, "": 1.0}
        return x * carp.get(m.group(2), 1.0) <= 1.0        # uF

    # ray -> kondansator listesi
    ray_kond = {}
    for ref in sorted(fps):
        padlar = pn.get(ref, {})
        if not ref.startswith("C") or len(padlar) != 2:
            continue
        aglar = set(padlar.values())
        if "GND" not in aglar:
            continue
        ray = next((a for a in aglar if a != "GND"), None)
        if ray and ray.startswith("+") and _kucuk(ref):
            ray_kond.setdefault(ray, []).append(ref)

    def yakin_sayisi(ic_ref, ray, disla=None):
        o = fps[ic_ref].GetPosition()
        n = 0
        for c in ray_kond.get(ray, ()):
            if c == disla or c not in fps:
                continue
            q = fps[c].GetPosition()
            if math.hypot(q.x - o.x, q.y - o.y) <= sinir_mm * MM:
                n += 1
        return n

    gb = guc_bacaklari(kart) if kart else None
    for ic in sorted(fps):
        if not ic.startswith("U") or ic not in fps:
            continue
        if gb is not None:
            # SADECE GERCEK BESLEME BACAGI OLAN RAYLAR
            raylar = {v for k, v in pn.get(ic, {}).items()
                      if v.startswith("+") and (ic, k) in gb}
        else:
            raylar = {v for v in pn.get(ic, {}).values() if v.startswith("+")}
        for ray in sorted(raylar):
            if not ray_kond.get(ray):
                continue
            if yakin_sayisi(ic, ray) > 0:
                continue
            # o entegrenin bu raydaki bacagi
            hedef_pad = next((q for q in fps[ic].Pads()
                              if q.GetNetname() == ray), None)
            if hedef_pad is None:
                continue
            hp = hedef_pad.GetPosition()
            # en yakin, VAZGECILEBILIR kondansator
            adaylar = []
            for c in ray_kond[ray]:
                if c not in fps:
                    continue
                q = fps[c].GetPosition()
                d = math.hypot(q.x - hp.x, q.y - hp.y)
                # bu kondansator baska bir entegrenin TEK kondansatoru mu
                vazgecilmez = False
                for u2 in fps:
                    if not u2.startswith("U") or u2 == ic:
                        continue
                    if ray not in pn.get(u2, {}).values():
                        continue
                    if yakin_sayisi(u2, ray) == 1 and \
                       yakin_sayisi(u2, ray, disla=c) == 0:
                        vazgecilmez = True
                        break
                if not vazgecilmez:
                    adaylar.append((d, c))
            if not adaylar:
                continue
            adaylar.sort()
            _, sec = adaylar[0]
            # BOS YER ARA, SABIT OFSET KOYMA.
            # Once bacagin +2.4/+2.4 kosesine koyuyordum. O nokta
            # doluysa parca uzerine biniyor ve ayir.py sonradan onu
            # uzaga itiyor — yani kondansator yine bacagindan
            # uzaklasiyor. Olculdu: bu yuzden D'de uc INA240 ve
            # A'da flash bellek kondansatorsuz kaliyordu.
            # Bacagin cevresinde halka halka bos nokta ariyoruz;
            # bulunamazsa dokunmuyoruz (kotu bir yer, hic yerden iyi
            # degil).
            import math as _m
            w, h = olcu(fps[sec])
            yer = None
            for yaricap in (2.0, 2.8, 3.6, 4.6, 5.6):
                for k2 in range(12):
                    ac = 2 * _m.pi * k2 / 12.0
                    cx = hp.x / MM + yaricap * _m.cos(ac)
                    cy = hp.y / MM + yaricap * _m.sin(ac)
                    cakisti = False
                    for r2, f2 in fps.items():
                        if r2 == sec:
                            continue
                        o2 = f2.GetPosition()
                        w2, h2 = olcu(f2)
                        if abs(o2.x / MM - cx) < (w + w2) / 2 and \
                           abs(o2.y / MM - cy) < (h + h2) / 2:
                            cakisti = True
                            break
                    if not cakisti:
                        yer = (cx, cy)
                        break
                if yer:
                    break
            if yer is None:
                continue
            koy(fps, sec, yer[0], yer[1], 0, kondu)
            tasinan += 1
    return tasinan


def adc_referans(fps, pn, kondu):
    """ADC referans agi: VREF / RBIAS / VCM — iki cipte OZDES yerlesim.

    RBIAS %1 direnci olcek hatasini belirliyor, VREF kondansatoru
    referans gurultusunu. Ikisi de cipin dibinde ve IKI CIPTE AYNI
    yerde olmali; farkli yerlesim iki cip arasinda kalici kazanc
    farki birakir ve dort kanalin genlik esitligi bozulur.
    """
    n = 0
    for adc in ("U20", "U21"):
        if adc not in fps:
            continue
        c = fps[adc].GetPosition()
        cx, cy = c.x / MM, c.y / MM
        for desen, dx, dy in ((f"VREF_{adc}", -9, 7), (f"RBIAS_{adc}", -9, 10),
                              ("VCM_", -9, 13)):
            for ref in sorted(fps):
                if ref in kondu or not ref.startswith(("R", "C")):
                    continue
                if any(v.startswith(desen) for v in pn.get(ref, {}).values()):
                    koy(fps, ref, cx + dx, cy + dy, 90, kondu)
                    n += 1
                    break
    return n


def kalanlar(fps, pn, kondu, en, boy, sadece_ic=False):
    """Konmamislari: ayristirma besledigi bacaga, otekiler komsusuna.

    SADECE_IC KIPI VE NEDEN VAR.
    Zincir once yerlesim_X ile kritik parcalari koyuyor, sonra
    ayristirma_topa ile ayirma kondansatorlerini dagitiyor, en sonda
    burasi kaliyor. Sorun: ayristirma_topa havuzunu YERLESMIS
    entegrelerden kuruyor. Acik kurali olmayan bir entegre (A'daki
    ADP150'ler U4..U9, C'deki dort PE4312) o an daha yerlesmedigi
    icin havuza hic girmiyor ve kondansator alamiyordu.

    Sonra buraya dusuyorlardi, ve buradaki kural da yardimci
    olmuyordu: kondansator, rayda EN COK BACAGI olan entegreye
    gidiyor — +3V3'te bu FPGA. Yani artan butun kondansatorler
    FPGA'ya gidiyor, kucuk entegrelere hicbir sey kalmiyordu.

    Olculdu (bu iki hata birlikte): C kartinda entegre-ray ciftlerinin
    %100'unde en yakin kondansator 5 mm'den uzakti, en kotusu 69 mm.
    A'da %77, en kotusu 91 mm. 45 mm uzaktaki bir ayirma
    kondansatorunun dongu enduktansi ~45 nH; 10 MHz'te |Z| ~ 2.8 ohm,
    oysa miliohm gerekiyor. Kondansator semada gorunur, BOM'da vardir,
    karta dizilir ve hicbir ise yaramaz.

    Cozum iki asama: once BUTUN entegreler yerlessin (sadece_ic=True),
    sonra ayristirma_topa hepsine dagitsin, en sonda kalan pasifler.

    Kritik parcalar yerine oturdu; buradan sonrasi ikincil. Ama yine de
    rastgele degil: her parca EN COK BAGLI oldugu, halihazirda konmus
    komsusunun dibine gidiyor.
    """
    kom = {}
    ag_uye = {}
    for ref, padlar in pn.items():
        for ag in set(padlar.values()):
            if not GUC.match(ag):
                ag_uye.setdefault(ag, set()).add(ref)
    for ag, u in ag_uye.items():
        if len(u) > 12:
            continue
        for a in u:
            kom.setdefault(a, set()).update(u - {a})

    yerli = set(kondu)
    for tur in range(8):
        yeni = 0
        for ref in sorted(fps):
            if ref in yerli:
                continue
            if sadece_ic and not ref.startswith("U"):
                continue
            padlar = pn.get(ref, {})
            aglar = set(padlar.values())
            hedef = None
            # ayristirma kondansatoru: besledigi entegrenin GUC BACAGINA
            if ref.startswith("C") and len(padlar) == 2 and "GND" in aglar:
                ray = next((a for a in aglar if a != "GND"), None)
                if ray:
                    # KUMEYI SIRALI DOLAS. `yerli` bir set ve icinde
                    # metin var; Python metin karmasini her surecte
                    # farkli tohumluyor, yani bu liste her kosuda
                    # baska sirada geliyordu. Asagidaki max() esitligi
                    # ILK GORDUGU lehine bozuyor, o yuzden ayni ray
                    # uzerinde ayni sayida bacagi olan iki entegreden
                    # hangisinin secildigi kosudan kosuya degisiyordu:
                    # D kartinda C110 bir kosuda x=71.0'e, otekinde
                    # x=21.6'ya dustu. Yerlesim tekrarlanmayinca bir
                    # kurulumdan alinan SES otekine uymuyor — kisa
                    # devrelerin bilinen sebebi bu.
                    ic = sorted(r for r in yerli if r.startswith("U")
                                and ray in pn.get(r, {}).values())
                    if ic:
                        # EN COK BACAKLI DEGIL, EN AZ KONDANSATORLU.
                        # Onceki kural rayda en cok bacagi olan
                        # entegreyi seciyordu; +3V3'te bu FPGA, yani
                        # artan her kondansator oraya gidiyordu ve
                        # regulatorler ac kaliyordu. Simdi o rayda
                        # halihazirda EN AZ kondansatoru olan entegre
                        # seciliyor; esitlikte ada gore, yani sonuc
                        # tekrarlanabilir.
                        def _yakin_sayisi(r):
                            o = fps[r].GetPosition()
                            n = 0
                            for c2 in yerli:
                                if not c2.startswith("C"):
                                    continue
                                if ray not in pn.get(c2, {}).values():
                                    continue
                                p2 = fps[c2].GetPosition()
                                if abs(p2.x - o.x) < 5 * MM and \
                                   abs(p2.y - o.y) < 5 * MM:
                                    n += 1
                            return n
                        en_iyi = min(ic, key=lambda r: (_yakin_sayisi(r), r))
                        for pad in fps[en_iyi].Pads():
                            if pad.GetNetname() == ray:
                                p = pad.GetPosition()
                                hedef = (p.x / MM + 2.4, p.y / MM + 2.4)
                                break
            if hedef is None:
                # Ayni gerekce: kom[] degerleri de set. Ortalama
                # sirasiz da ayni cikardi ama kayan nokta toplami
                # sirayla degisiyor ve koy() 0.05 mm izgaraya
                # yuvarliyor — esik ustunde bir parca oynuyordu.
                aday = sorted(r for r in kom.get(ref, ()) if r in yerli)
                if not aday:
                    continue
                xs = [fps[r].GetPosition().x / MM for r in aday]
                ys = [fps[r].GetPosition().y / MM for r in aday]
                hedef = (sum(xs) / len(xs) + 3.5, sum(ys) / len(ys) + 3.5)
            # KONDU'YA DA EKLE. Buradaki koy() cagrisi kondu'yu
            # almiyordu, yani bu asamada yerlesen hicbir parca
            # "yerlesmis" sayilmiyordu ve sonraki adimlar onlari
            # gormuyordu.
            koy(fps, ref, min(max(hedef[0], 8), en - 8),
                min(max(hedef[1], 8), boy - 8), kondu=kondu)
            yerli.add(ref)
            yeni += 1
        if not yeni:
            break
    return [r for r in fps if r not in yerli]


def olcu(fp, pay=1.4):
    try:
        kat = (pcbnew.B_CrtYd if fp.GetLayer() == pcbnew.B_Cu
               else pcbnew.F_CrtYd)
        c = fp.GetCourtyard(kat).BBox()
        if c.GetWidth() > 0:
            return c.GetWidth() / MM + pay, c.GetHeight() / MM + pay
    except Exception:
        pass
    b = fp.GetBoundingBox()
    return b.GetWidth() / MM + pay, b.GetHeight() / MM + pay


# ------------------------------------------------------- YAPISKAN GRUP
#
# NEDEN VAR. Anahtarlamali bir regulatorde uc dugum kritik:
#
#   GIRIS CEVRIMI   giris kondansatoru -> IC -> toprak -> geri
#                   Akim burada KESIKLI: her anahtarlama periyodunda
#                   sifirdan tepe akima ziplayip geri dusuyor. di/dt
#                   en yuksek burada, yani yayilan alan da. Cevrim
#                   alani ne kadar buyukse o kadar iyi bir anten.
#   ANAHTAR DUGUMU  IC -> bobin
#                   Gerilim burada 0 ile Vin arasinda nanosaniyelerde
#                   gidip geliyor: dv/dt en yuksek dugum. Bakir alani
#                   ne kadar genisse kapasitif kuplaj o kadar cok.
#   CIKIS CEVRIMI   bobin -> cikis kondansatoru -> toprak
#                   Akim surekli, en az kritik olani; yine de uzun
#                   olursa cikis dalgalanmasi ve toprak gurultusu.
#
# OLCULEN (ayak izi merkezleri arasi mm — once / sonra):
#              giris          bobin          cikis
#     A/U1     4.0 -> 3.4    20.0 -> 4.5   16.1 -> 3.1
#     A/U2     3.5 -> 3.4    20.0 -> 4.5    4.1 -> 3.1
#     C/U90   54.4 -> 3.4    10.0 -> 4.5   48.0 -> 3.2
#     D/U50   12.2 -> 5.2     9.8 -> 6.1   10.3 -> 3.1
#     D/U51  185.0 -> 3.4     9.3 -> 4.5   15.5 -> 3.2
# Ped-ped olculunce (elektriksel olarak onemli olan o) hepsi
# 2.0-3.2 mm arasinda. D/U50 biraz genis cunku LM5164 SOIC-8'in
# govdesi 4.9 mm ve 47uH bobin 3 mm — fizik siniri, yerlesim degil.
#
# D/U51'in eski 185 mm'lik giris cevrimi kartin bir ucundan otekine
# gidiyordu. A'daki 20 mm'lik anahtar dugumu ise mikrovolt dinleyen
# bir alicinin 20 mm yaninda duran bir verici gibi calisiyordu.
#
# A/U1, A/U2 ve C/U90'da GIRIS KONDANSATORU HIC YOKTU (semada da
# yoktu, sadece yerlesimde uzak degildi). Eklendi: A'da C3/C4 ve
# C5/C6, C'de C83/C84, D/U51'de C650/C651, D/U50'de C663 (2.2uF
# 100 V seramik). Bir buck'ta kesikli akimi verecek kondansator
# yoksa o akim kaynagin kendisinden, yani kablodan cekilir.
#
# COZUM. Regulator + giris kondansatoru + bobin + cikis kondansatoru
# TEK BLOK. Blok kendi ic geometrisiyle kuruluyor, sonra bir butun
# olarak konumlandiriliyor; parcalari `kondu` kumesine giriyor,
# yani ne ayirici ne de genel dolgu onlari birbirinden ayirabiliyor.
# Ayni mekanizma ayristirma kondansatorleri icin de kullanilacak.
BLOK_SABIT = set()
BLOK_KULLANILDI = set()   # bir bloga girmis kondansator ikinciye girmez
BLOK_ARA = 0.5            # blok icinde courtyard'lar arasi bosluk, mm


def _cap_ada(fps, pn, ag, sayfa=None, en_fazla=2):
    """Iki bacagi {ag, GND} olan kondansatorler — KUCUKTEN BUYUGE.

    Kucukten baslamak onemli: yuksek frekans cevrimini kapatan sey
    seramik olan, elektrolitik degil. 470 uF'lik toplu enerji
    kondansatorunu IC'nin dibine cakmak yer israfi; 100 nF'i 20 mm
    oteye atmak ise cevrimin ta kendisini bozuyor.
    Sayfa suzgeci: ayni raydaki BASKA entegrelerin ayristirma
    kondansatorlerini kapmayalim diye (bir kartta +3V3'e bagli 200
    kondansator var, regulatorun kendi cikisi bunlardan biri).
    """
    out = []
    for ref, padlar in sorted(pn.items()):
        if not ref.startswith("C") or len(padlar) != 2:
            continue
        if set(padlar.values()) != {ag, "GND"}:
            continue
        if sayfa is not None and SAYFA.get(ref) != sayfa:
            continue
        if ref in BLOK_KULLANILDI or ref not in fps:
            continue
        out.append(ref)
    # KUCUK OLAN ONCE. Sira referans adina gore olursa 470 uF'lik
    # elektrolitik IC'nin dibine, 100 nF 20 mm oteye dusebiliyor —
    # tam tersi. Esitlikte referans adi: sonuc tekrarlanabilir kalsin.
    out.sort(key=lambda r: (round(olcu(fps[r], 0)[0] * olcu(fps[r], 0)[1], 3), r))
    return out[:en_fazla] if en_fazla else out


def regulator_blok(fps, pn, kondu, ic, bobin, x, y, aci=0, sayfa=None,
                   cin=None, cout=None):
    """Anahtarlamali regulatoru cevresiyle birlikte TEK BLOK koy.

    ic     regulator referansi (blok merkezi burada)
    bobin  anahtar dugumune bagli bobin
    x, y   blogun capasi = IC'nin govde merkezi
    aci    blogun uzanma yonu: 0 saga, 90 asagi, 180 sola, 270 yukari
           (KiCad'de Y ekseni asagi bakiyor)

    Dizilim, akim yonunde:  [giris C] [IC] [bobin] [cikis C]
    Boylece giris cevrimi de anahtar dugumu de mumkun olan en kisa
    hale geliyor ve cikis kondansatoru bobinin hemen ardinda.
    """
    if ic not in fps or bobin not in fps:
        return 0
    un = pn.get(ic, {})
    ln = pn.get(bobin, {})
    ortak = (set(un.values()) & set(ln.values())) - {"GND", ""}
    if not ortak:
        return 0
    # ANAHTAR DUGUMUNU DOGRU SEC. IC ile bobin IKI ag paylasiyor:
    # anahtar dugumu (SW) ve cikis rayi — TPS62130'un VOS bacagi da
    # cikisa bagli. Alfabetik ilkini almak "+3V3"u anahtar dugumu
    # sanmaya yol aciyordu; o durumda cikis kondansatoru hic
    # bulunamiyor (blok cikissiz kaliyor, olculdu).
    # Anahtar dugumu ISIMSIZ ve az bacakli olan: ray isimleri "+"
    # ile basliyor, anahtar dugumu ise semada etiketlenmemis.
    sw = sorted(ortak, key=lambda a: (a.startswith("+"),
                                      len([1 for p in pn.values()
                                           if a in p.values()]), a))[0]
    vout = sorted(set(ln.values()) - {sw, "GND", ""})
    vout = vout[0] if vout else None
    # giris rayi: IC'nin en cok bacaginin bagli oldugu, cikis/anahtar
    # olmayan ray. TPS62130'da VIN iki bacak, bu onu tek basina
    # secmeye yetiyor.
    sayim = {}
    for ag in un.values():
        if ag in ("GND", "", sw, vout):
            continue
        sayim[ag] = sayim.get(ag, 0) + 1
    vin = max(sorted(sayim), key=lambda a: sayim[a]) if sayim else None
    # KONDANSATORLERI ELLE VERMEK ESAS, OTOMATIK BULMA YEDEK.
    # Ag + sayfa suzgeci yetmiyor: guc sayfasinda +3V3'e bagli on
    # kondansator var (LDO girisleri, cikislari, regulatorun kendi
    # cikisi) ve hepsi ayni olcude. Hangisinin blogun parcasi
    # oldugunu netlist bilmiyor, SEMAYI YAZAN biliyor.
    sayfa = sayfa if sayfa is not None else SAYFA.get(ic)
    cin = list(cin) if cin else (_cap_ada(fps, pn, vin, sayfa) if vin else [])
    cout = (list(cout) if cout else
            (_cap_ada(fps, pn, vout, sayfa) if vout else []))
    BLOK_KULLANILDI.update(cin)
    BLOK_KULLANILDI.update(cout)

    ileri = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[aci % 360]
    yan = (-ileri[1], ileri[0])

    # YONLER ONCE, OLCU SONRA. olcu() courtyard'i O ANKI donusuyle
    # okuyor; once yerlestirip sonra dondurursek blok icindeki
    # araliklar yanlis hesaplanir ve parcalar ust uste biner.
    fps[bobin].SetOrientationDegrees(aci)
    # IC'NIN DONMESINI PEDLER SECSIN, ZINCIR YONU DEGIL.
    # Blok yonu karttaki bos yere gore seciliyor; ama VIN bacaklari
    # zincirin ters ucunda kalirsa giris cevrimi govdenin etrafindan
    # dolasiyor. Olculdu: ayni merkez mesafesinde ped-ped 2.1 mm ile
    # 6.4 mm arasinda degisiyor, tek fark govdenin donusu.
    # Dort donusu de deneyip VIN pedlerini giris kondansatoruna,
    # anahtar pedini bobine bakan yone getireni seciyoruz.
    en_iyi, en_iyi_puan = aci, None
    for deneme in (0, 90, 180, 270):
        fps[ic].SetOrientationDegrees((aci + deneme) % 360)
        c0 = fps[ic].GetPosition()

        def izdusum(ag):
            v = [((q.GetPosition().x - c0.x) / MM * ileri[0]
                  + (q.GetPosition().y - c0.y) / MM * ileri[1])
                 for q in fps[ic].Pads() if q.GetNetname() == ag]
            return sum(v) / len(v) if v else 0.0
        # giris pedleri geriye (-ileri), anahtar pedi ileriye baksin
        puan = izdusum(sw) - izdusum(vin)
        if en_iyi_puan is None or puan > en_iyi_puan:
            en_iyi, en_iyi_puan = (aci + deneme) % 360, puan
    fps[ic].SetOrientationDegrees(en_iyi)
    # KONDANSATORLER EKSENE DIK. 0805'in kisa kenari zincir boyunca
    # duruyor; iki pedi de IC'nin AYNI kenarina bakiyor (VIN ve PGND
    # yan yana), yani cevrim kondansatorun boyu kadar bile uzamiyor.
    # Eksene paralel de denendi: ayni merkez mesafesinde ped-ped
    # 4.8 mm yerine 5.9 mm cikti, yani daha kotu.
    for r in cin + cout:
        if r in fps:
            fps[r].SetOrientationDegrees((aci + 90) % 360)

    def boy_yon(ref):
        """Parcanin blok EKSENI boyunca olcusu (+ bosluk)."""
        w, h = olcu(fps[ref], BLOK_ARA)
        return w if ileri[0] else h

    def enine(ref):
        w, h = olcu(fps[ref], BLOK_ARA)
        return h if ileri[0] else w

    n = 0
    yerlestir = [(ic, 0.0, 0.0)]      # (ref, eksen konumu, yan konum)
    cin = [r for r in cin if r in fps]
    cout = [r for r in cout if r in fps]
    # giris kondansatorleri IC'nin GERISINDE
    if cin:
        merkez = -boy_yon(ic) / 2 - boy_yon(cin[0]) / 2
        yerlestir.append((cin[0], merkez, 0.0))
        # Ikincisi birincinin YANINDA: cevrim uzamiyor, iki
        # kondansator gercekten paralel bagli oluyor. Eksen konumu
        # HER PARCA ICIN AYRI hesaplaniyor — ortak merkez kullanmak,
        # eksende daha genis olan ikinci kondansatoru IC'nin
        # courtyard'ina sokuyordu (D'de C663 ile U50, 0.15 mm).
        for r in cin[1:]:
            yerlestir.append((r, -boy_yon(ic) / 2 - boy_yon(r) / 2,
                              (enine(cin[0]) + enine(r)) / 2))
    # bobin ve cikis kondansatorleri IC'nin ONUNDE
    yer = boy_yon(ic) / 2
    if bobin in fps:
        yer += boy_yon(bobin) / 2
        yerlestir.append((bobin, yer, 0.0))
        yer += boy_yon(bobin) / 2
    if cout:
        yerlestir.append((cout[0], yer + boy_yon(cout[0]) / 2, 0.0))
        for r in cout[1:]:
            yerlestir.append((r, yer + boy_yon(r) / 2,
                              (enine(cout[0]) + enine(r)) / 2))
    for ref, ileriye, yana in yerlestir:
        px = x + ileri[0] * ileriye + yan[0] * yana
        py = y + ileri[1] * ileriye + yan[1] * yana
        n += koy(fps, ref, px, py, None, kondu)
        BLOK_SABIT.add(ref)
    return n


def ayikla(fps, kondu, en, boy, tur=500):
    """Cakismalari coz — KRITIK PARCALAR OYNAMAZ.

    Kritik olanlar kat planindaki yerinde kalmali; ayirma butunuyle
    ikincil parcalara yikiliyor. Yoksa saat tamponu ADC'lerin
    ortasindan kayar ve LVDS esitligi bozulur.
    """
    ref = list(fps)
    kayma, px, py, olc = [], [], [], []
    for r in ref:
        fp = fps[r]
        p0 = fp.GetPosition()
        try:
            c = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            m = c.GetCenter() if c.GetWidth() > 0 else p0
        except Exception:
            m = p0
        kayma.append(((m.x - p0.x) / MM, (m.y - p0.y) / MM))
        px.append(p0.x / MM + kayma[-1][0])
        py.append(p0.y / MM + kayma[-1][1])
        olc.append(olcu(fp))
    # KATMAN. Cakisma sinamasi katmani gormuyordu: BGA altina alinan
    # kondansatorler ust yuzeydeki parcalarla "cakisiyor" sayildi ve
    # sayac 185 gosterdi, gercekte 16'ydi. Farkli yuzeydeki iki parca
    # ust uste GELEBILIR — kartin iki tarafi.
    kat = [fps[r].GetLayer() for r in ref]
    n = len(ref)
    for _ in range(tur):
        cak = 0
        kova = {}
        for i in range(n):
            kova.setdefault((int(px[i] / 12), int(py[i] / 12)), []).append(i)
        for (cx, cy), liste in kova.items():
            komsu = []
            for a in (-1, 0, 1):
                for b2 in (-1, 0, 1):
                    komsu += kova.get((cx + a, cy + b2), [])
            for i in liste:
                wi, hi = olc[i]
                for j in komsu:
                    if j <= i or kat[i] != kat[j]:
                        continue
                    wj, hj = olc[j]
                    dx, dy = px[j] - px[i], py[j] - py[i]
                    ox, oy = (wi + wj) / 2, (hi + hj) / 2
                    ax, ay = abs(dx), abs(dy)
                    if ax < ox and ay < oy:
                        ki = ref[i] in kondu
                        kj = ref[j] in kondu
                        if ki and kj:
                            # IKISI DE ELLE KONMUS: zaten oynatmiyoruz.
                            # Sayaci da ancak GERCEK courtyard'lar
                            # kesisiyorsa artir. olcu() 1.4 mm guvenlik
                            # payi ekliyor; yapiskan gruplar bilerek
                            # 0.5 mm arayla sikistiriliyor ve pay'li
                            # olcu onlari cakisma sayip her kosuda
                            # yanlis alarm veriyordu.
                            if ax < ox - 1.4 and ay < oy - 1.4:
                                cak += 1
                            continue
                        cak += 1
                        pi = 0.0 if ki else (1.0 if kj else 0.5)
                        pj = 0.0 if kj else (1.0 if ki else 0.5)
                        if ox - ax < oy - ay:
                            k = ox - ax + 0.2
                            s = 1 if dx >= 0 else -1
                            px[i] -= k * pi * s
                            px[j] += k * pj * s
                        else:
                            k = oy - ay + 0.2
                            s = 1 if dy >= 0 else -1
                            py[i] -= k * pi * s
                            py[j] += k * pj * s
        for i in range(n):
            if ref[i] in kondu:
                continue
            px[i] = min(max(px[i], 8), en - 8)
            py[i] = min(max(py[i], 8), boy - 8)
        if not cak:
            break
    for i, r in enumerate(ref):
        if r in kondu:
            continue
        fps[r].SetPosition(pcbnew.VECTOR2I(
            int(round((px[i] - kayma[i][0]) * 20) / 20 * MM),
            int(round((py[i] - kayma[i][1]) * 20) / 20 * MM)))
    return cak


# ------------------------------------------------------------------ C karti
# Dort kanal, kanal basina yedi bant. Kat plani tek cumleyle: HER
# KANAL BIREBIR AYNI, sinyal soldan saga akiyor, geri donus yok.
#
#      0      40      80     120     160     200     240     280   340
#   25 J1 -- B1 --- B2 --- B3 --- B4 --- B5 --- B6 --- B7 --> J80
#   80 J2 -- B1 --- B2 --- B3 --- B4 --- B5 --- B6 --- B7 --> J81
#  135 J3 -- ...
#  190 J4 -- ...
#
# Dort seridin geometrisi ayni olmak ZORUNDA: bu kartin butun degeri
# dort kanalin faz uyumu. Serit 1 elle konumlaniyor, 2/3/4 ayni
# geometrinin otelenmisi.
C_EN, C_BOY = 350, 235
C_KANAL_Y = [25, 80, 135, 190]
# BANT BANKASI 42'DEN 60'A KAYDI. Giris zinciri (GDT, TVS, T/R
# rolesi, ikinci TVS cifti, seri direnc) artik antenin dibinde
# duruyor ve 42 mm'ye sigmiyordu. Bant 7 boylece 300'e, en sagdaki
# bobini 333'e dusuyor; cikis konnektorleri 348.6'da, arada 15 mm
# kaliyor.
C_BANT_X0 = 60
C_BANT_ADIM = 40
# Giris zincirinin x konumlari, SINYAL SIRASINDA. Aralar parcalarin
# courtyard genisligine gore: GDT 4.5, SMB 7.4, role 9.4 mm.
C_GIRIS_X = (9.0, 17.0, 27.0, 36.0, 40.0, 44.0)


def yerlesim_C(fps, pn, kondu):
    """C karti: dort kanal x yedi bant filtre bankasi.

    Uc kural:

    1 SERITLER BIREBIR AYNI. Her parca kendi bandinin ayni goreli
      noktasina konuyor, kanal indeksinden bagimsiz. Yol uzunlugu
      boylece dort kanalda esit cikiyor.

    2 KOMSU BANT BOBINLERI DIK. Yan yana iki toroid ayni yonde
      duruyorsa aralarinda karsilikli endüktans var; bir bandin
      durdurma bolgesinde otekinin sinyali sizar. Tek numarali
      bantlar 0, cift numaralilar 90 derece — alanlar dik, kuplaj
      birinci mertebeden sifir.

    3 ROLE KONTROL HATLARI RF'IN ALTINDAN GECMEZ. Bobin uclari
      seridin altinda, RF yolu seridin ekseninde.
    """
    n = 0
    for k, ky in enumerate(C_KANAL_Y, start=1):
        n += koy(fps, f"J{k}", 0.5, ky, KENAR_ACI["sol"], kondu, kenar=True)
        # GIRIS ZINCIRI AG ADINDAN TURETILIYOR, REFERANS ARITMETIGINDEN
        # DEGIL.
        #
        # Eski hali "E{99+k}" ve "D{100+(k-1)*5}" diye referans sayisi
        # uyduruyordu. Gercek adimlama kanal basina 9: koruma diyotlari
        # D101/D105/D106, D110/D114/D115, D119/..., D128/... Formul
        # D100 (yok), D105, D110, D115 uretiyordu — yani 1. kanalin
        # diyotu 2. kanalin seridine, 2. kanalinki 3. ve 4. seride
        # kondu. Olculdu: D105 (kanal 1) y=80'de, D110 (kanal 2)
        # y=135'te, D115 (kanal 2) y=190'da. Yerlestirilemeyenler
        # genel dolguya dustu ve GDT'sinden 100 mm oteye gitti;
        # 100 mm'lik bir baglantinin ucundaki TVS asiri gerilimi
        # bastirmaz, kendi endüktansi darbeyi gecirir.
        #
        # Ag adi uydurulamaz: parcayi hangi aga bagliysa ondan
        # buluyoruz.
        ant, rxa = f"ANT{k}", f"RX{k}_ANT"

        def bagli(ag, onek, _pn=pn):
            return sorted(r for r, p in _pn.items()
                          if ag in p.values() and r.startswith(onek))

        # T/R ROLESI ANTENIN DIBINDE, BANT BANKASININ SONUNDA DEGIL.
        # Once C_EN-42'ye (x=308) konuyordu, "alis/veris ayrimi
        # filtreden sonra yapiliyor" gerekcesiyle. Netlist tersini
        # soyluyor: KT{k} ANT{k} ile RX{k}_ANT arasinda, yani
        # filtrelerden ONCE. Olculen bedeli: ANT{k} agi 303 mm,
        # RX{k}_ANT 287 mm — alinan sinyal ilk filtreye varmadan
        # once kartin boyunu iki kez kat ediyordu. O 590 mm hem
        # dogrudan kayip (kazanctan ONCE, yani tamami gurultu
        # rakamina biniyor) hem de dort kanalin yan yana kosan
        # uzun hatlari arasinda karsilikli kuplaj — bu kartin butun
        # degeri olan kanal esitligini bozan sey.
        # TX yolu uzuyor; dogru takas bu, cunku TX yuksek seviyeli
        # ve gurultuye duyarsiz.
        zincir = (bagli(ant, "E") + bagli(ant, "D") + [f"KT{k}"]
                  + bagli(rxa, "D") + bagli(rxa, "R"))
        for j, r in enumerate(zincir):
            if r in fps and j < len(C_GIRIS_X):
                n += koy(fps, r, C_GIRIS_X[j], ky, 90, kondu)
        # Role surucusu kendi rolesinin USTUNDE, altinda degil.
        # Altta (ky+13) 4. kanalinki y=203'e dusuyor ve alt kenardaki
        # role surucu bandindaki U70'in uzerine biniyordu; ikisi de
        # sabit sinifta oldugu icin ayirici ayiramiyordu. Ust taraf
        # dort kanalda da bos: bant bobinleri ky-9'da ama x>=69'da,
        # bu ise x=27.
        n += koy(fps, f"QT{k}", C_GIRIS_X[2], ky - 13, 0, kondu)
        for bant in range(1, 8):
            bx = C_BANT_X0 + (bant - 1) * C_BANT_ADIM
            n += koy(fps, f"K{k}{bant}", bx, ky, 0, kondu)
            desen = (f"F{k}{bant}_", f"N{k}{bant}_")
            ic = [r for r, padlar in pn.items()
                  if r[:1] in ("L", "C")
                  and any(a.startswith(desen) for a in padlar.values())]
            bobin = sorted(r for r in ic if r.startswith("L"))
            kond = sorted(r for r in ic if r.startswith("C"))
            baci = 0 if bant % 2 else 90
            # BOBIN ADIMI CEKIRDEGE GORE, SABIT 8 mm DEGIL.
            # Bant 1 ve 6 elde sarilmis T50 toroid kullaniyor
            # (courtyard 13.8 mm), 2-5 ise 0805/NR-30 SMD bobin
            # (1.8-3.6 mm). Hepsine 8 mm adim verilince toroidler ic
            # ice giriyordu: dort kanalda 24 courtyard cakismasi.
            # GORUNMUYORDU cunku eski T50 ayak izinde F.CrtYd yoktu
            # ve cakisma sinamasi genisligi 0 olan parcalari atliyor.
            # Ayak izine courtyard eklenince ortaya cikti.
            # Uc toroid 3 x 13.8 + 2 x 0.5 = 42.4 mm; bant adimi
            # 40 mm ama komsu bantlarin bobinleri kucuk ve ortalanmis
            # oldugu icin tasma yan banda girmiyor (olculdu).
            def cap_l(r):
                try:
                    kk = fps[r].GetCourtyard(pcbnew.F_CrtYd).BBox()
                    if kk.GetWidth() > 0:
                        return kk.GetWidth() / MM
                except Exception:
                    pass
                return 4.0
            gen = [cap_l(r) for r in bobin if r in fps]
            imle = bx + 9 - (sum(gen) + 0.5 * max(0, len(gen) - 1)) / 2
            for r in bobin:
                if r not in fps:
                    continue
                w = cap_l(r)
                # ky-9 DEGIL ky-14. Role govdesi 10.6 mm yuksek,
                # yani ky+-5.3'u kapliyor; 13.8 mm'lik toroid
                # ky-9'da 3.2 mm ile rolenin icine giriyordu
                # (dort kanalda 16 cakisma). 14 mm'de toroidin
                # alt kenari 17.9, rolenin ust kenari 19.7.
                n += koy(fps, r, imle + w / 2, ky - 14, baci, kondu)
                imle += w + 0.5
            for i, r in enumerate(kond):
                n += koy(fps, r, bx + 6 + (i % 4) * 7,
                         ky + 8 + (i // 4) * 5, 0, kondu)
    # (KT{k}/QT{k} artik yukarida, giris zincirinin icinde. Burada
    # C_EN-42'ye konuyorlardi; gerekcesi netliste uymuyordu.)

    # SAG KENAR: her kanalin RX cikisi kendi seridinin hizasinda,
    # TX girisi hemen altinda. J82..J85 = RX1..RX4 -> A karti,
    # J86..J89 = TX1..TX4 <- A karti.
    for i in range(4):
        n += koy(fps, f"J{82 + i}", C_EN - 0.5, C_KANAL_Y[i],
                 KENAR_ACI["sag"], kondu, kenar=True)
        n += koy(fps, f"J{86 + i}", C_EN - 0.5, C_KANAL_Y[i] + 20,
                 KENAR_ACI["sag"], kondu, kenar=True)
    # kontrol ve besleme alt kenarda, RF seritlerinden uzak
    for i, r in enumerate(("J80", "J81", "J90")):
        n += koy(fps, r, 70 + i * 70, C_BOY - 0.5, KENAR_ACI["alt"], kondu, kenar=True)

    # ROLE SURUCULERI AYRI BANTTA. Latching role bobinine giden darbe
    # birkac amperlik bir kenar; o akimi RF seridinin yanindan
    # gecirmek yerine karti alt kenarda bir kontrol bandina topluyoruz.
    # Bobin hatlari bantlar arasindaki 40 mm'lik bosluklardan dikey
    # cikiyor ve ic katmanda, toprak duzlemi altinda ilerliyor.
    # ROLE SURUCULERI KENDI KANALLARININ SERIDINDE.
    #
    # Once on dordu de alt kenarda TEK SIRADA duruyordu (y=205,
    # x=24..323) ve roleler dort kanal seridinde. Olculdu: 28
    # surucu-role ciftinin 27'si 60 mm'nin uzerinde, ortalama
    # 144 mm, en uzugu 274 mm. Kilitlenen role bobinine verilen
    # darbe o iz uzerinde zayifliyor; atmayan bir bant rolesi
    # yanlis filtreyle verme demek. Ustelik o 56 uzun bobin hatti
    # kartin dortte ucunu kat eden bir demet olusturup
    # yonlendiriciyi tikiyordu.
    #
    # Simdi kanal basina dort surucu (gen_05_driver 16 x DRV8833),
    # her biri surdugu iki rolenin TAM ARASINDA, seridin 20 mm
    # altinda. Bobin hatti 20-25 mm'ye iniyor ve dort kanal
    # birebir ayni geometriyi aliyor.
    for k, ky in enumerate(C_KANAL_Y, start=1):
        for j in range(4):
            ref = f"U{70 + (k - 1) * 4 + j}"
            # j=0,1,2 iki roleyi suruyor: ikisinin ortasi.
            # j=3 tek role suruyor (7 tek sayi): onun hizasi.
            bx = (C_BANT_X0 + (2 * j) * C_BANT_ADIM
                  + (C_BANT_ADIM / 2 if j < 3 else 0))
            n += koy(fps, ref, bx, ky + 20, 0, kondu)
    # Kaydirmali yazmaclar alt kenarda kaliyor: seri veri yolu
    # yavas (birkac MHz) ve uzunluga duyarsiz. Sira 16'dan 11'e
    # indi cunku 4. kanalin suruculeri artik y=210'da.
    for i in range(7):
        n += koy(fps, f"U{60 + i}", 30 + i * 46, C_BOY - 11, 0, kondu)
    # +5V BUCK YAPISKAN GRUP. Once hicbir yere capalanmamisti ve
    # genel dolguya kaliyordu: giris cevrimi 54 mm, cikis 48 mm.
    # Yer secimi: SOL ALT KOSE, x=10 ekseninde DIKEY (aci=270,
    # yukari dogru). Dort RF seridi y = 25/80/135/190'da; blok
    # y=222'den y=206'ya uzaniyor, yani hepsinin altinda. Role
    # suruculeri x=24'ten basliyor, blok x=6..14 arasinda kaliyor.
    # Anahtarlamali dugum RF'in gectigi hicbir seride komsu degil.
    n += regulator_blok(fps, pn, kondu, "U90", "L80", 10, 214, 270,
                        cin=("C84", "C83"), cout=("C82", "C80"))
    return n


# ------------------------------------------------------------------ D karti
# Tek bir guc zinciri, soldan saga, geri donus yok:
#
#   J10 -> U10 zayiflatici -> U11 on kuvvetlendirici -> T10 giris
#       -> Q20/Q21 surucu -> Q10..Q13 final -> T11 cikis
#       -> KL1..KL7 LPF bankasi -> T20/T21 kuplor -> anten
#
# Karti belirleyen kisit TERMAL. A sinifi 100 W cikis icin DC giris
# ~333 W; 233 W'i dort IRFP250N'de isiya donuyor, cihaz basina 58 W.
# Dort TO-247'nin de KULAKLARI AYNI KENARA bakmali ki tek bir bakir
# barin uzerine cakilsinlar. Ustelik dort cihaz ayni bara ayni sirayla
# bagli olmali: aralarindaki sicaklik farki bias farkina, o da IMD'ye
# donusuyor.
# KART 240 -> 260 mm GENIS.
# LPF bobinlerine dogru ayak izleri verilince (T94 25.0, T68 18.6,
# T50 13.8 mm) tek siranin ihtiyaci olculdu:
#     4xT94 + 4xT68 + 4xT50 = 229.6 mm
#   + bypass bandinin rolesi           14.0
#   + bantlar arasi 6 x 1 mm            6.0
#   ------------------------------------------
#                                     249.6 mm
# 240 mm'lik kartta kullanilabilir genislik ~236 mm; 14 mm eksik
# kaliyordu ve bobinler kuplor blogunun uzerine tasiyordu.
# Iki secenek vardi: bantlari iki sira yapmak ya da karti genisletmek.
# Iki sira, her bandin filtresini kendi rolesinin ustunde tutma
# kuralini bozuyor (sinyal roleden cikip filtreye, oradan ayni
# roleye donuyor; sira degisince o yol yan bandin altindan geciyor).
# 240 -> 260 yetmedi: sira 250'ye kadar geliyor ve kuplor/dedektor
# blogu 220-242'de duruyordu. 275'te sira 4..250, kuplor 233..268,
# arada 5 mm kaliyor.
# Iki siraya bolmeyi de olctum: genislik rahatlar (132 ve 117 mm) ama
# ikinci sira 25 mm'lik T94'lerle birlikte 25 mm daha DUSEY yer
# istiyor ve role/surucu/olcum siralari 185 mm'ye sigmiyor. Yani
# problem genislik degil ALAN; en az bozan yon genislik.
# 35 mm bakir, bozulan bir kat planindan ucuz.
D_EN, D_BOY = 275, 185
# Final cihazlar kartin UST KENARINDA, kulaklar disari. 26 mm iceride
# durduruyordum: sogutucu bari kartin uzerinden gecmek zorunda kaliyor,
# ustelik 26 mm bakir bosa gidiyor. Cihaz basina 58 W'i tasiyacak bar
# kartin kenarina dayanmali, TO-247 kulagi da ona.
D_FINAL_Y = 8
D_EKSEN = 70            # RF hattinin ana ekseni


def yerlesim_D(fps, pn, kondu):
    """D karti: 5..100 W ayarlanabilir A sinifi PA.

    Dort kural:

    1 DORT FINAL UST KENARDA, TEK SIRA. Kulaklar disari bakiyor, hepsi
      ayni sogutucu barina biniyor. Sirali dizilim sicakligi de sirali
      yapiyor; rastgele yerlestirirsen kenardaki cihaz ortadakinden
      soguk kalir, bias'i kayar, IMD3 bozulur.

    2 ITME-CEKME SIMETRIK. Q10/Q11 bir kol, Q12/Q13 oteki. Ikisi
      cikis trafosunun ekseninde AYNALI. Kollar arasi uzunluk farki
      dogrudan cift harmonik bastirmasini bozar — itme-cekmenin tek
      isi o.

    3 KAPI YOLLARI DORDUNE DE ESIT. Surucu ciftinden dort kapiya giden
      mesafe ayni; farkli olsa cihazlar farkli anda aciliyor ve
      birbirlerinin akimini yukleniyorlar.

    4 ALGILAMA CIKISTA, GUC KOSEDE. Kuplor ve AD8318'ler cikis
      trafosundan sonra; 50 V girisi ve regulatorler RF hattinin en
      uzak kosesinde.
    """
    n = 0
    # ---------- giris zinciri: sol kenardan iceri, duz hat
    n += koy(fps, "J10", 0.5, D_EKSEN, KENAR_ACI["sol"], kondu, kenar=True)
    for r, x in (("U10", 26), ("U11", 52)):
        n += koy(fps, r, x, D_EKSEN, 0, kondu)
    # T10 ASAGIDA, SURUCU EKSENINDE KONUMLANIYOR (bkz. yerlesim_D
    # icinde "SURUCU GIRIS TRAFOSU"). Burada giris zincirinin
    # sirasindan cikarildi: x=78'de dururken iki kapi kolu 43.6 ve
    # 95.5 mm oluyordu — itme-cekme bir kati besleyen trafo iki
    # kolun TAM ORTASINDA olmak zorunda.
    # ---------- final: UST KENAR, tek sira, kulaklar yukari
    # Q10/Q11 sol kol, Q12/Q13 sag kol; cikis trafosu tam ortada.
    # TO-247 govdesi 16.5 mm. 16 mm adimla dizmistim, kulaklar
    # birbirine giriyordu. 20 mm adim: govdeler arasi 3.5 mm bosluk,
    # sogutucu barinin vidalari da araya siger.
    fx = (112, 132, 162, 182)
    for r, x in zip(("Q10", "Q11", "Q12", "Q13"), fx):
        n += koy(fps, r, x, D_FINAL_Y, 180, kondu)
    # HIZALAMA GERCEK KONUMDAN. koy() parcayi govde merkezine
    # oturtuyor, yani istenen koordinat artik gercek konum degil:
    # TO-247 ile TO-220'nin orijin-merkez farki ayni olmadigi icin
    # finaller +5.5 mm, suruculer +2.5 mm kaydi ve simetri bozuldu
    # (Q20 -> Q10 16.9 mm ama -> Q11 24.6 mm). Finalleri koyduktan
    # sonra NEREYE dustuklerini oku, gerisini ona gore hizala.
    def mrk(r):
        q = fps[r].GetPosition()
        return q.x / MM, q.y / MM

    gx = [mrk(r)[0] for r in ("Q10", "Q11", "Q12", "Q13")]
    n += koy(fps, "T31", (gx[1] + gx[2]) / 2, D_FINAL_Y + 26, 0, kondu)
    # ---------- surucu cifti HER BIRI KENDI KOLUNUN MERKEZINDE
    # Once ikisini de giris trafosunun yanina koymustum: Q20'den dort
    # kapiya mesafe 39..82 mm cikti. Itme-cekmede Q20 sol kolu, Q21
    # sag kolu suruyor; herkes kendi ciftinin tam ortasinda durmali,
    # yoksa cihazlar farkli anda aciliyor ve birbirinin akimini
    # yukleniyor. Simetri de korunuyor: iki surucu de kendi kolundan
    # ayni uzaklikta.
    # Suruculer finallerin 16 mm altindaydi; T12 ve R213 ile
    # cakisiyorlardi. 44 mm asagi: final -> kapi direnci -> surucu ->
    # surucu trafosu sirasi acilir.
    # SURUCU SIRASI 44 -> 54. Final girisi trafosu (T30) referans
    # catismasindan geri gelince arada yer kalmadi: T30 ile T31
    # ve T30 ile Q20/Q21 cakisti. Olculen kutulara gore final
    # girisi ile surucu arasinda 15 mm bos band gerekiyor.
    n += koy(fps, "Q20", (gx[0] + gx[1]) / 2, D_FINAL_Y + 54, 0, kondu)
    n += koy(fps, "Q21", (gx[2] + gx[3]) / 2, D_FINAL_Y + 54, 0, kondu)
    # Konuldular; simdi ONLARIN gercek konumuna gore ince ayar.
    for s, (a, c) in (("Q20", ("Q10", "Q11")), ("Q21", ("Q12", "Q13"))):
        hedef = (mrk(a)[0] + mrk(c)[0]) / 2
        q = fps[s].GetPosition()
        fps[s].SetPosition(pcbnew.VECTOR2I(
            int(q.x + (hedef - q.x / MM) * MM), q.y))
    q = fps["T31"].GetPosition()
    hedef = (mrk("Q11")[0] + mrk("Q12")[0]) / 2
    fps["T31"].SetPosition(pcbnew.VECTOR2I(
        int(q.x + (hedef - q.x / MM) * MM), q.y))
    # ---------- LPF bankasi: cikis trafosunun altinda, tek sira
    # G2RL-2 govdesi 13.1 x 29.4 mm — YUKSEK. Suruculeri 16 mm asagi
    # koymustum, rolenin govdesinin icinde kaliyorlardi. 24 mm asagi
    # ve adim 27 mm: yedi role 20..182 arasina siginca sag taraf
    # kuplor ve detektorlere kaliyor.
    # BANT GENISLIGI CEKIRDEGE GORE, SABIT 27 mm DEGIL.
    # Butun bantlara 27 mm verip bobinleri 13 mm arayla diziyordum.
    # Cekirdekler ayni degil: T50 13.8, T68 18.6, T94 25.0 mm. Alt
    # bantlarin T94'leri 13 mm arayla ic ice giriyordu — kart basilir,
    # parcalar takilmaz. On courtyard cakismasi hep bu sirada cikti.
    # (Ustelik eski T50 ayak izinde F.CrtYd yoktu, yani cakisma
    # denetimi bu parcalari hic gormuyordu; ayak izleri duzeltilince
    # sorun gorunur oldu.)
    # Toplam ihtiyac olculdu: 4xT94 + 4xT68 + 4xT50 = 229.6 mm,
    # kartin kullanilabilir genisligi ~236 mm. Tek sira YETIYOR,
    # yeter ki her bant kendi cekirdeginin genisligini alsin.
    def bant_bobinleri(i):
        return sorted(r for r, padlar in pn.items()
                      if r.startswith("L")
                      and any(a.startswith((f"LF{i}_", f"N{i}_"))
                              for a in padlar.values()))

    def cap(r):
        """Parcanin courtyard genisligi (mm); yoksa kaba tahmin."""
        try:
            k = fps[r].GetCourtyard(pcbnew.F_CrtYd).BBox()
            if k.GetWidth() > 0:
                return k.GetWidth() / MM
        except Exception:
            pass
        return 14.0

    bant_x = {}
    imlec = 4.0
    for i in range(1, 8):
        w = sum(cap(r) for r in bant_bobinleri(i) if r in fps)
        # Bypass bandinin (bobinsiz) genisligi rolenin kendisi
        # kadar: G2RL-2 govdesi 13.1 mm.
        w = max(w, 14.0)
        bant_x[i] = imlec + w / 2
        imlec += w + 1.0          # bantlar arasi 1 mm
    for i in range(1, 8):
        bx = bant_x[i]
        n += koy(fps, f"KL{i}", bx, 130, 0, kondu)
        n += koy(fps, f"QL{i}", bx, 155, 0, kondu)
        # BANDIN FILTRESI KENDI SUTUNUNDA. Onceden LPF bobinlerini
        # genel dolguya birakmistim; T68/T94 toroidler role
        # govdelerinin icine dustu (10 adet pth_inside_courtyard).
        # Her bandin C-L-C-L-C zinciri kendi rolesinin tam ustunde,
        # 27 mm'lik sutununda duruyor: sinyal roleden cikip yukari,
        # filtreden gecip role geri donuyor, yan banda hic girmiyor.
        # Blok y=90'dan basliyor: 78'e koyunca band 2'nin toroidi
        # y=70'teki giris zincirinin on kuvvetlendiricisine giriyordu.
        ic = [r for r, padlar in pn.items()
              if r[:1] in ("L", "C")
              and any(a.startswith((f"LF{i}_", f"N{i}_"))
                      for a in padlar.values())]
        bobin = sorted(r for r in ic if r.startswith("L"))
        kond = sorted(r for r in ic if r.startswith("C"))
        # Komsu bant bobinleri dik: tek bantlar 0, ciftler 90 derece.
        baci = 0 if i % 2 else 90
        # Bobinler bandin icinde KENDI capina gore diziliyor: imlec
        # her bobinin yarim capi kadar ilerliyor. Sabit 13 mm adim
        # T94'te ic ice geciyordu.
        bimlec = bx - (sum(cap(r) for r in bobin)
                       + 0.5 * max(0, len(bobin) - 1)) / 2
        for r in bobin:
            w = cap(r)
            # Bobinler arasi 0.5 mm: tam capa esit adimda
            # courtyard'lar DEGIYOR ve cakisma sayiliyor.
            # 96 -> 99. Surucu giris trafosu (T10) itme-cekmenin
            # iki kolunun tam ortasina, yani bu eksene alindi ve
            # T12 ile toroid sirasi arasinda 15.1 mm'lik trafoya
            # 14.1 mm kaliyordu. Uc mm asagi: T10 alt kenari 89.05,
            # toroid ust kenari 89.69. Filtre kondansatorleri de
            # birlikte iniyor (asagida 111 -> 114).
            n += koy(fps, r, bimlec + w / 2, 99, baci, kondu)
            bimlec += w + 0.5
        for j, r in enumerate(kond):
            n += koy(fps, r, bx - 8 + j * 8, 114, 90, kondu)
    # ---------- kuplor ve detektorler: LPF cikisi
    # Kart 20 mm genisleyince kuplor/dedektor blogu da 20 mm saga:
    # LPF sirasi artik x=250'ye kadar geliyor.
    # KUPLOR BLOGU DIKEY SUTUN, LPF SIRASININ SAGINDA.
    # Yatay diziliyken (T20/T21 x=255, dedektorler x=233) LPF role
    # sirasinin sag ucuyla cakisiyordu: KL7 x=240..253, KL6 218..231.
    # Olculdu, tahmin degil. Sinyal zaten LPF'ten cikip saga
    # gidiyor; blogu dikey sutuna almak akisi bozmuyor.
    for r, (x, y) in (("K20", (266, 78)),
                      ("T20", (266, 98)), ("T21", (266, 118)),
                      ("U60", (266, 136)), ("U61", (266, 158)),
                      ("C407", (254, 98)), ("C612", (254, 118)),
                      ("C411", (254, 168))):
        n += koy(fps, r, x, y, 0, kondu)
    # ---------- KOL SONUMLEME DIRENCLERI KOLUN MERKEZINDE.
    # R213 ve R215 genel dolguya dusmustu: biri kolunun merkezinden
    # +5 mm, oteki -10 mm kaymisti ve itme-cekme kollari 62.2 / 57.2
    # mm cikiyordu. Kollarin esitligi cift harmonik bastirmasinin
    # kendisi; bu iki direnc de o esitligin parcasi.
    # SIMETRIK CIFTLER: KOORDINAT DOGRUDAN, koy() KULLANMADAN.
    # koy() parcayi gövde merkezine oturtuyor ve iki kolu AYNI yone
    # kaydiriyor; ayna simetrisi boyle kurulmuyor. Bu ciftlerde
    # konumu dogrudan yaziyoruz: eksen cikis trafosu, iki taraf onun
    # aynasi. Kollarin esitligi cift harmonik bastirmasinin kendisi.
    def ayna(sol_ref, sag_ref, x_sol, y, aci=90):
        if sol_ref not in fps or sag_ref not in fps or eks is None:
            return 0
        for r, x in ((sol_ref, x_sol), (sag_ref, 2 * eks - x_sol)):
            fps[r].SetOrientationDegrees(aci)
            fps[r].SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
            kondu.add(r)
        return 2

    eks = None   # asagida, trafo hizalandiktan SONRA hesaplanacak
    # SURUCU TRAFOSU DA IKI SURUCUNUN TAM ORTASINDA.
    # T12 x=126.7'deydi, Q20 (127.4) ile Q21 (177.4) arasinin ortasi
    # 152.4. Kollar 21.5 / 53.2 mm cikiyordu — surucu katinin kendi
    # itme-cekmesi de simetrik olmali, final kadar.
    def birincil_ortala(tr, a, c):
        """Trafoyu BIRINCIL PINLERINE gore ortala, govdesine gore degil.

        Ayak izinde birincil (1 ve 2) orijinden 5 mm SOLDA. Govdeyi
        iki kolun ortasina koyunca pinler 5 mm sola kaliyor ve bir kol
        otekinden 10 mm uzak oluyor: T11'de 20.4'e karsi 29.6 mm.
        Hizalanacak olan pin, govde degil.
        """
        if tr not in fps or a not in fps or c not in fps:
            return 0
        # TRAFOYU 90 DERECE CEVIR. Ayak izinde birincilin iki pini
        # DIKEY diziliyor: biri otekinden 5 mm yukarida. Cihazlarin
        # hepsi ayni y'de oldugu icin bu fark dogrudan kollara
        # geciyordu (70.2'ye karsi 74.5 mm). Cevirince iki pin yatay
        # olup eksenin iki yaninda esit uzakliga dusuyor.
        fps[tr].SetOrientationDegrees(90)
        pinler = [q for q in fps[tr].Pads() if q.GetNumber() in ("1", "2")]
        if not pinler:
            return 0
        px = sum(q.GetPosition().x for q in pinler) / len(pinler)
        # HEDEF, CIHAZIN ORIJINI DEGIL AYNI AGA BAGLI PEDI.
        # TO-247'nin orijini drain pedinden 5 mm otede; orijinlerin
        # ortasi 152, pedlerin ortasi 147. Trafoyu 152'ye hizalayinca
        # butun grup 5.45 mm saga kaydi ve kollar esitlenmedi.
        def ped_x(ref):
            aglar = {q.GetNetname() for q in fps[tr].Pads()}
            uy = [q.GetPosition().x for q in fps[ref].Pads()
                  if q.GetNetname() in aglar]
            return uy[0] if uy else fps[ref].GetPosition().x
        hedef = (ped_x(a) + ped_x(c)) / 2
        q = fps[tr].GetPosition()
        fps[tr].SetPosition(pcbnew.VECTOR2I(int(q.x + (hedef - px)), q.y))
        kondu.add(tr)
        return 1

    # T12 SURUCULERIN ALTINDA. D_FINAL_Y+18'de kalmisti ve Q12'nin
    # govdesine giriyordu; surucu kati asagi indikten sonra trafo da
    # onunla birlikte inmeli.
    if "T12" in fps:
        # T12 66'DAN 57'YE. Bastirma dirençleri (R200/R201) T30'un
        # ikincilinin dibine tasininca burasi acildi ve surucu cikis
        # trafosu drainlerin 2.5 mm altina geldi. Asil kazanc:
        # asagida T10 icin eksen uzerinde yer aciliyor.
        q = fps["T12"].GetPosition()
        fps["T12"].SetPosition(pcbnew.VECTOR2I(q.x, int((D_FINAL_Y + 57) * MM)))
    n += birincil_ortala("T12", "Q20", "Q21")
    n += birincil_ortala("T31", "Q10", "Q13")
    # AYNA EKSENI TRAFO HIZALANDIKTAN SONRA. Once T11'in eski
    # konumundan aliyordum, sonra trafo kayinca eksen bayatliyor ve
    # aynalanan dirençler yanlis yere dusuyordu.
    if "T31" in fps:
        # DEGISKEN ADI `pn` DEGIL: o, fonksiyonun ped-ag SOZLUGU
        # parametresi. Burada listeyle ustune yazilinca sonraki her
        # kullanim (regulator_blok) 'list' object has no attribute
        # 'get' ile patliyordu.
        t31_ped = [q for q in fps["T31"].Pads() if q.GetNumber() in ("1", "2")]
        if t31_ped:
            eks = sum(q.GetPosition().x for q in t31_ped) / len(t31_ped) / MM
    kolA = ((fps["Q10"].GetPosition().x + fps["Q11"].GetPosition().x)
            / 2 / MM) if "Q10" in fps else None
    if kolA is not None:
        # R213/R215 -> R205/R207 (geri besleme 820R cifti; kuplaj
        # kondansatorleri eklenince cnt() numaralari kaydi).
        n += ayna("R205", "R207", kolA, D_FINAL_Y + 31)
        # SURUCU KAPI DIRENCLERI SURUCULERIN EKSENINDE.
        # T11'in ekseninde aynaliyordum; surucu kati kendi ekseni
        # etrafinda simetrik olmali (Q20/Q21 ortasi), final katinin
        # degil. 20.9'a karsi 22.0 mm farki buradan geliyordu.
        sur_eks = eks
        if "Q20" in fps and "Q21" in fps:
            sur_eks = (fps["Q20"].GetPosition().x
                       + fps["Q21"].GetPosition().x) / 2 / MM
        eks_yedek, eks = eks, sur_eks
        n += ayna("R106", "R108", sur_eks - 26, D_FINAL_Y + 62)
        n += ayna("R107", "R109", sur_eks - 20, D_FINAL_Y + 62)
        # FINALIN GIRIS TRAFOSU SURUCU ILE KAPILAR ARASINDA.
        # T30 (BN43-202 3:1) referans catismasi yuzunden kartta hic
        # yoktu; catisma cozulunce geri geldi ve genel dolguya dusup
        # RS3'un ustune oturdu. Yeri belli: surucunun cikisi (DRV_OUT)
        # buraya girer, GIN_A/GIN_B buradan dort kapiya dagilir, yani
        # iki kolun tam ortasinda ve surucu ile finaller arasinda
        # olmali. Cikis trafosu T31 D_FINAL_Y+26'da; bu ondan 10 mm
        # asagida, surucu sirasinin (D_FINAL_Y+44) hemen ustunde.
        n += koy(fps, "T30", sur_eks, D_FINAL_Y + 41.5, 90, kondu)
        # BASTIRMA DIRENCLERI (1R) T30'UN IKINCILINDE, SIMETRIK.
        # GIN_A/GIN_B'yi topraga baglayan bu iki direnc genel
        # dolguda surucunun kapi bolgesine dusuyordu (y=66.5) ve
        # R201'in toprak pedi Q21'in kapi izini kesiyordu: iki
        # surucu kolundan biri elle cizilemiyor, oteki ciziliyordu
        # — yani tam da onlemeye calistigimiz asimetri. Yerleri
        # besledikleri sarginin dibi.
        n += koy(fps, "R200", sur_eks - 10, D_FINAL_Y + 36, 0, kondu)
        n += koy(fps, "R201", sur_eks + 10, D_FINAL_Y + 36, 0, kondu)
        # SURUCU GIRIS TRAFOSU DA IKI KOLUN ORTASINDA.
        # x=78'de (giris zincirinin sirasinda) duruyordu ve
        # olculdu: T10 -> R106 43.6 mm, T10 -> R108 95.5 mm.
        # 52 mm fark, itme-cekmenin iki kolunu farkli suruyor;
        # cift harmonik bastirmasi dogrudan bu farkla sinirlaniyor.
        # 90 derece cevriliyor ki ikincilin iki pedi eksenin iki
        # yanina esit uzaklikta dussun. y = D_FINAL_Y+71: ustunde
        # T12 (biter 64.5), altinda LPF toroid sirasi (baslar 86.7).
        # y+71 denendi: T12 (biter 72.55) ile 1.1 mm cakisti.
        # y+73.5 ile arada 1.4 mm var; alttaki LPF toroid sirasi
        # 86.7'de basliyor, trafonun alt kenari 89.05 — orasi da
        # 2.3 mm. Iki komsu arasindaki tek serit bu.
        # T12'nin 0.3 mm altina yapisik: arada 1.4 mm birakinca
        # genel dolgu oraya bir 0603 sikistirmaya calisti (R317)
        # ve iki sabit parca arasinda kalip ayirici tarafindan
        # cozulemedi. Bosluk parca sigmayacak kadar dar olmali.
        n += koy(fps, "T10", sur_eks, D_FINAL_Y + 72.2, 90, kondu)
        # SURUCU BOGUCUSU (L11) TRAFONUN ORTA UCUNUN DIBINDE.
        # 12 V bu bobinden gecip T12'nin orta ucuna giriyor (o
        # baglanti semada YOKTU, bkz. gen_01_driver). Genel dolgu
        # onu T12 ile T10 arasindaki 1 mm'lik seride sikistiriyordu.
        # Yeri: trafonun saginda, ayni sirada.
        n += koy(fps, "L11", sur_eks + 16, D_FINAL_Y + 57, 0, kondu)
        # FINAL BOGUCUSU (L20, +50V -> DRN_CT) DE ELLE.
        # Genel dolguda cikis trafosunun (T31) courtyard'inin icine
        # dusuyordu: uc PTH pedi trafonun govdesinin altinda kaldi.
        # Bos bolge olculdu: sol kolun altinda, R213 (biter 42.9) ile
        # Q20 (baslar 59.5) arasi. Trafonun orta ucundan 21 mm.
        n += koy(fps, "L20", kolA, D_FINAL_Y + 43, 0, kondu)
        eks = eks_yedek

    # ---------- KAPI DIRENCLERI HER CIHAZIN KENDI KAPISINDA.
    # Genel dolguya birakmistim; R202..R209 kartin dortbir yanina
    # dagildi ve kapi aglari 57.8 / 66.0 / 81.1 / 94.4 mm cikti.
    # Yerlesim surucuyu dort kapiya esit uzaklikta koymustu ama
    # arada duran direnc rastgele yerde olunca o esitlik bir sey
    # ifade etmiyor. Her cihazin iki direnci kendi kapisinin
    # hemen altinda: seri direnc ve kapi-toprak direnci.
    for i, r in enumerate(("Q10", "Q11", "Q12", "Q13")):
        q = fps[r].GetPosition() if r in fps else None
        if q is None:
            continue
        gx = q.x / MM
        # REFERANSLAR: R240..R243 = 10R bastirma, R244..R247 = 1k
        # servo direnci, C230..C233 = kuplaj kondansatoru. Ucu de
        # gen_02_final'de SABIT adli (cnt() ile uretilmiyor) —
        # sayfaya parca eklendiginde bu yerlesim bozulmasin diye.
        # Kuplaj kondansatoru da buraya ait: trafodan gelen RF
        # once ondan, sonra 10R'den gecip kapiya giriyor.
        # KOLUN ORTASI BOS KALMALI — DRAIN KORIDORU.
        # Kol basina iki cihaz paralel ve drain izi (6.67 A, 2.2 mm)
        # trafodan gelip TAM ORTALARINDA ikiye ayriliyor (elle_cek
        # dengeli tee). Bu uc kucuk parca simetrik olarak "gx+3"e
        # konunca sol cihazinki tam o eksene dusuyordu ve tee
        # cizilemiyordu (olculdu: R244 x=120.5, eksen x=122).
        # Cozum: her cihazin parcalari KENDI DIS TARAFINA. Kol
        # icindeki iki cihaz birbirinin AYNASI oluyor, dort kapi
        # hatti yine 14.5 mm ve orta koridor aciliyor.
        dis = -1 if i % 2 == 0 else 1
        n += koy(fps, f"C{230 + i}", gx + dis * 9, D_FINAL_Y + 9, 90, kondu)
        n += koy(fps, f"R{240 + i}", gx + dis * 3, D_FINAL_Y + 9, 90, kondu)
        # 1k servo direnci ikinci sirada: ayni sirada uc parca
        # (kondansator + 10R + 1k) 3 mm adimla sigmiyor, ve INA240
        # ayni x'te bir alt sirada duruyor. y+11.5'te iki sira
        # arasinda 1.5 mm bosluk kaliyor.
        # 1k servo direnci ikinci sirada. y+11 denendi: sag
        # cihazlarin dirençleri INA240 sirasinin (y+15, yukseklik
        # 5.5) ust kenarina 0.3 mm kaldi. y+9'da uc parca da ayni
        # sirada ve INA240 ile arada 3 mm var.
        n += koy(fps, f"R{244 + i}", gx + dis * 6, D_FINAL_Y + 9, 90, kondu)

    # ---------- AKIM OLCUM YUKSELTECLERI SHUNT'LARININ DIBINDE
    # Uc INA240 kartin alt-sol kosesinde, olcum seridinde duruyordu:
    # kendi shunt'larindan 150 mm otede. INA240 shunt uzerindeki
    # gerilimi olcuyor ve 0.01R'de 6.67 A sadece 66.7 mV yapiyor.
    # O 66.7 mV'luk cift, 150 mm boyunca 6.67 A'in manyetik alaninin
    # icinden gecerse okunan sey akim degil, akimin turevi olur.
    # Ustelik sonuc "bozuk" degil MAKUL AMA YANLIS bir sayidir ve
    # bias servosu ona bakiyor.
    # Dogrusu KELVIN baglanti: yukseltec shunt'in yaninda, iki olcum
    # izi shunt pedlerinden baslayip yapisik gidiyor. Shunt sirasi
    # D_FINAL_Y+16'da, cihaz basina bir tane; yukseltec de ayni
    # sirada, shunt'in 9 mm sagina.
    # Dorduncusu (U31) referans catismasi yuzunden kartta yoktu;
    # simdi dordu de var ve dordu de ayni geometride.
    # Konum CIHAZDAN turetiliyor, shunt'tan degil: RS'ler bu
    # fonksiyonun daha asagisinda yerlesiyor, buradan okunsa bayat
    # koordinat gelirdi. Ikisi de ayni x'ten cikiyor, sonuc ayni.
    for i in range(4):
        if f"U{31 + i}" in fps and f"Q1{i}" in fps:
            gx0 = fps[f"Q1{i}"].GetPosition().x / MM
            # SAGA, HEPSI AYNI. Disari aynalamak denendi: ic
            # cihazlarinki (U32, U33) kartin ortasina, yani cikis
            # trafosunun (T31) govdesine dusuyor. Drain koridorunu
            # acan sey zaten kapi parcalarinin aynalanmasi; INA240
            # sirasi y=23'te ve tee dallari y<20'de kaliyor.
            n += koy(fps, f"U{31 + i}", gx0 + 9, D_FINAL_Y + 15, 0, kondu)
    # kaydirmali yazmac ve yardimci FET'ler kendi siralarinda
    n += koy(fps, "U56", 150, 164, 0, kondu)
    # LM358 bias integratorleri: genel dolguda T12/T30 uzerine
    # dusuyorlardi. Olcum seridinde, besledikleri servo
    # zincirinin oteki ucunda.
    for i, r in enumerate(("U41", "U42")):
        # y=145'te G2RL-2'nin govdesine giriyorlardi: role 13x29 mm,
        # y=128'e konunca 113..143'u kapliyor. Olcum siras y=164.
        n += koy(fps, r, 40 + i * 22, 164, 0, kondu)
    for i, r in enumerate(("Q31", "Q32")):
        n += koy(fps, r, 178 + i * 12, 164, 0, kondu)
    # U41/U42 BU LISTEDEN CIKARILDI. Eskiden D kartinda U41 diye bir
    # parca yoktu ve koy() sessizce False donuyordu. Dedektorler
    # U30/U31'den U40/U41'e tasininca U41 birden var oldu ve buradaki
    # satir onu kuplorun yanindan (200,150) alip kartin ortasina
    # (100,80) tasidi — REV dedektoru olctugu kuplorden 70 mm oteye.
    for r, (x, y) in (("U20", (100, 56)), ("U21", (100, 68)),
                      # olcum katindaki iki entegre birbirinin ustune
                      # dusuyordu; sicaklik sensoru sogutucu tarafina
                      ("U57", (100, 164)), ("U55", (125, 164))):
        n += koy(fps, r, x, y, 0, kondu)
    # ---------- guc: SAG UST KOSE, RF hattindan en uzak
    # J30 (50 V girisi) KOSE DELIGINDEN UZAK.
    # y=12'de sag ust kose deligine (D_EN-5, 5) 2.17 mm
    # kaliyordu; M3 civata basi 6.5 mm cap, yani pul klemense
    # degiyordu. y=26 ile civata cevresinde 9 mm bos yaricap
    # kaliyor. 50 V tasiyan bir klemenste bu asgari.
    n += koy(fps, "J30", D_EN - 0.5, 26, KENAR_ACI["sag"], kondu,
             kenar=True)
    # GUC KOSESI, GIRISTEN CIKISA SIRALI:
    #   J30 (kenar) -> Q30/U52 ideal diyot -> C601/C602 toplu enerji
    #   -> U50 blogu (50->12 V) -> U51 blogu (12->5 V)
    # Ideal diyot J30'un DIBINDE: 6.67 A tasiyan yolun korumasiz
    # kismi ne kadar kisaysa o kadar iyi, ve MOSFET'in savagi
    # dogrudan toplu kondansatorlere bakiyor.
    for r, (x, y) in (("Q30", (252, 22)), ("U52", (252, 30)),
                      ("C601", (232, 20)), ("C602", (232, 42))):
        n += koy(fps, r, x, y, 0, kondu)
    # IKI REGULATOR YAPISKAN GRUP, SOLA UZANIYOR (aci=180).
    # Olculen eski hali: U50 giris 12.2 / bobin 9.8 / cikis 10.3,
    # U51 giris 185.0 / bobin 9.3 / cikis 15.5. 185 mm'lik bir giris
    # cevrimi kartin bir ucundan otekine gidiyordu.
    # Blok saga degil sola aciliyor: sagda J30 ve kart kenari var.
    n += regulator_blok(fps, pn, kondu, "U50", "L50", 250, 58, 180,
                        cin=("C662", "C663"), cout=("C665", "C664"))
    n += regulator_blok(fps, pn, kondu, "U51", "L51", 250, 76, 180,
                        cin=("C651", "C650"), cout=("C667", "C666"))
    # anten cikisi kuplorden hemen sonra, sag kenar
    # J40 KENAR MONTAJ DEGIL: klemens, govdesi de vidasi da kartin
    # uzerinde durur. kenar=True verince pedini kenara dayadi ve
    # normal parcalar icin tuttugumuz 2 mm kusagi deldi.
    n += koy(fps, "J40", D_EN - 12, 168, 0, kondu)
    # KAYNAK ORNEKLEME DIRENCLERI CIHAZLARIN ALTINDA.
    # RS1..RS4 genel dolguda kaliyordu ve LPF toroidlerinin pedine
    # oturdu. Her cihazin kaynak akimini olcen direnc kendi cihazinin
    # altinda olmali; olcum de yol da kisa kalir.
    for i in range(4):
        if f"RS{i + 1}" in fps and f"Q1{i}" in fps:
            gx0 = fps[f"Q1{i}"].GetPosition().x / MM
            n += koy(fps, f"RS{i + 1}", gx0, D_FINAL_Y + 16, 90, kondu)

    # ---------- kontrol konnektorleri alt kenar
    # J33 zincir gecisi: J31/J32'nin yaninda, ayni kenarda.
    # Kablo A -> C -> D1 -> D2 diye giderken hepsi ayni yuzden ciksin.
    # J20 (DPD ornegi) SAG KENARA, kuplorlerin yanina.
    # Alt kenarda kontrol konnektorleriyle ayni seride duruyordu ve
    # yonlendirici uzun role kontrol izlerini (RLY_RCLK 66 mm)
    # pedlerinin uzerinden geciriyordu — dort kisa devre, alti maske
    # koprusu, her turda ayni yerde. Ustelik DPD ornegi zaten
    # kuplorden geliyor; sag kenar hem dogru hem tenha.
    n += koy(fps, "J20", D_EN - 0.5, 168, KENAR_ACI["sag"], kondu,
             kenar=True)
    for i, r in enumerate(("J31", "J32", "J33")):
        n += koy(fps, r, 40 + i * 48, D_BOY - 0.5, KENAR_ACI["alt"], kondu, kenar=True)
    return n


# Konumu KESINLIKLE degismeyecek parcalar: ayna ciftleri, esit
# uzunluk gruplari, sogutucuya bakan cihazlar.
SIMETRIK = {
    "D": ("Q10", "Q11", "Q12", "Q13", "Q20", "Q21", "T10", "T31", "T12",
          # Kapi zinciri: kuplaj kondansatoru + 10R + 1k, cihaz basina.
          # (Eskiden R202..R209 idi; kuplaj kondansatorleri eklenince
          # cnt() numaralari kaydi ve dort kapi hatti 14.5 mm'den
          # 22.5/34.2/24.9 mm'ye dagildi. Artik sabit adli.)
          "C230", "C231", "C232", "C233",
          "R240", "R241", "R242", "R243",
          "R244", "R245", "R246", "R247",
          "R205", "R207", "R106", "R107", "R108", "R109",
          # Kaynak olcum dirençleri her cihazin ALTINDA olmali —
          # koridorun icinde ama oraya ait. Sabit degillerse koridor
          # bosaltici onlari kartin disina itiyor (uc pedin ust
          # kenari -3.41 mm cikti).
          "RS1", "RS2", "RS3", "RS4"),
    # R220/R221 = ADC saat sonlandirmalari. Sabit degillerken
    # koridor bosaltici onlari A'nin RX koridorundan (x 0-60,
    # y 112-212) disari itiyordu: istenen 3.6 mm yerine 14.4 mm.
    # Sonlandirma alicinin dibinde olmazsa gorevini yapmiyor.
    "A": tuple(f"T{i}" for i in range(1, 5)) + ("U15", "Y10", "U20", "U21",
                                                "R220", "R221"),
    "C": tuple(f"K{k}{b}" for k in range(1, 5) for b in range(1, 8))
         + tuple(f"KT{k}" for k in range(1, 5)),
}

KART = {"A": ("A_main", "dogrudan_sdr_A", A_EN, A_BOY, yerlesim_A),
        "C": ("C_rf", "dogrudan_sdr_C", C_EN, C_BOY, yerlesim_C),
        "D": ("D_pa", "dogrudan_sdr_D", D_EN, D_BOY, yerlesim_D)}


def kenar_sil_dosyadan(pcb):
    """Edge.Cuts cizgilerini DOSYADAN cikar.

    pcbnew'un Remove()'u bu nesnede de surece cokuyor. Kart dosyasi
    s-ifade; (gr_line ... (layer "Edge.Cuts") ...) bloklarini
    parantez sayarak cikarmak guvenli.
    """
    metin = open(pcb, encoding="utf-8").read()
    out, i, n = [], 0, 0
    while True:
        k = metin.find('(layer "Edge.Cuts")', i)
        if k < 0:
            out.append(metin[i:])
            break
        b0 = max(metin.rfind("(gr_line", 0, k), metin.rfind("(gr_rect", 0, k),
                 metin.rfind("(gr_arc", 0, k))
        if b0 < 0:
            out.append(metin[i:k + 1])
            i = k + 1
            continue
        derinlik, j = 0, b0
        while j < len(metin):
            if metin[j] == "(":
                derinlik += 1
            elif metin[j] == ")":
                derinlik -= 1
                if derinlik == 0:
                    j += 1
                    break
            j += 1
        out.append(metin[i:b0])
        i = j
        n += 1
    if n:
        open(pcb, "w", encoding="utf-8").write("".join(out))
    return n


def uygula(kart):
    dizin, proj, en, boy, fn = KART[kart]
    pcb = os.path.join(HERE, dizin, proj + ".kicad_pcb")
    kenar_sil_dosyadan(pcb)
    b = pcbnew.LoadBoard(pcb)
    # Delikleri AYRICA listele: dordu de "REF**" oldugu icin fps
    # sozluginde tek anahtara cokuyorlar, uc tanesi kayboluyordu.
    delikler = [fp for fp in b.Footprints() if fp.GetReference() == "REF**"]
    # KAPLAMALI DELIK ONCE. C kartinda deliklerden biri pedli ve
    # GND'ye bagli (sase referansi, pcb_kur.dis_hat). O delik anten
    # konnektorlerinin dibinde olmali: J1..J4 sol kenarda, ilki
    # y=25'te, yani (5,5) kosesi. Sirayi dosya duzenine birakmak
    # yerine PEDINDEN taniyoruz — dosya duzeni LoadBoard'un isi.
    #
    # PED VARLIGINA BAKMAK YETMIYOR: kaplamasiz delik de bir "ped"
    # tasiyor (NPTH, numarasiz, agsiz). len(Pads()) ikisinde de 1,
    # yani siralama etkisizdi ve delik kimligi dosya duzenine, yani
    # UUID'lere kaliyordu. Olculdu: ayni girdiyle uc kosuda kaplamali
    # delik bir kez H2, bir kez H3 oldu; kart konumlari ayni kalsa da
    # iceri_al pedli deligi 0.15 mm iceri cektigi icin PARMAK IZI
    # degisiyordu — yani C kartinin zinciri tekrarlanamiyordu ve
    # uretilen SES bir sonraki kuruluma UYMUYORDU.
    # Ayirt edici olan pedin NUMARASI: kaplamalinin "1", otekinin "".
    delikler.sort(key=lambda fp: 0 if any(q.GetNumber()
                                          for q in fp.Pads()) else 1)
    KART_OLCU[0], KART_OLCU[1] = en, boy
    # MONTAJ DELIKLERI EN BASTA ADLANDIRILIR VE KONUR.
    #
    # Once bu is fonksiyonun SONUNDA yapiliyordu ve arada delikler
    # hala "REF**" adiyla duruyordu. Asagidaki fps sozlugu referansa
    # gore anahtarlaniyor: DORT delik TEK anahtara cokuyor ve sozlukte
    # hangisinin kaldigi dosya duzenine, yani UUID'lere bagli oluyordu.
    # ayikla() o tek deligi engel olarak gorup cevresini ona gore
    # bosalttigi icin sonuc kosudan kosuya degisiyordu: A kartinda
    # ust uste iki kosuda 7 kondansator (C623, C723, ...) farkli yere
    # dustu. Yani zincir tekrarlanabilirligini burada kaybediyordu ve
    # DSN parmak izi sinamasi bunu yakaliyordu.
    #
    # Delikler basta adlandirilinca fps'te H1..H4 olarak DORDU BIRDEN
    # bulunuyor; ayikla hepsini engel sayiyor ve `kondu` icinde
    # olduklari icin kimse onlari oynatamiyor.
    kose = ((5, 5), (en - 5, 5), (5, boy - 5), (en - 5, boy - 5))
    for i, fp in enumerate(delikler[:4]):
        x, y = kose[i]
        fp.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
        fp.SetReference(f"H{i + 1}")
    # SIRALI: kart ici sira UUID'lere bagli ve her kurulumda
    # farkli; sirasiz dolasmak yerlesimi tekrarlanmaz yapiyor.
    fps = {fp.GetReference(): fp
           for fp in sorted(b.Footprints(),
                            key=lambda x: x.GetReference())}
    pn = padnetler(dizin, proj)
    kondu = {f"H{i + 1}" for i in range(len(delikler[:4]))}
    # Kart basina temiz baslangic: uygula() ayni surecte birden cok
    # kart icin cagrilabiliyor (./yap.sh A C D).
    BLOK_SABIT.clear()
    BLOK_KULLANILDI.clear()
    kritik = fn(fps, pn, kondu)
    kritik += adc_referans(fps, pn, kondu)
    # SIRA: ONCE HERKES YERLESSIN, SONRA KONDANSATORLER BACAGA.
    #
    # ayristirma_topa havuzunu YERLESMIS entegrelerden kuruyor.
    # Once kalanlar'dan ONCE cagriliyordu, yani acik kurali olmayan
    # entegreler (A'da ADP150'ler U4..U9, C'de dort PE4312) havuza
    # hic girmiyordu. Olculdu: o entegrelerin hicbirinin 15 mm
    # cevresinde ayirma kondansatoru yoktu; C'de entegre-ray
    # ciftlerinin %100'u 5 mm'den uzakti, en kotusu 69 mm.
    #
    # Once "entegreleri onceden yerlestir" diye ayri bir asama
    # denedim; ise yaramadi ve nedeni olcunce cikti: kalanlar
    # icindeki koy() cagrisi kondu'yu ALMIYOR, yani oraya yerlesen
    # hicbir parca kumeye girmiyor. Ustelik bir LDO'nun guc disi
    # komsusu yok, yani tutunacak bir komsu da bulamiyor.
    #
    # Dogru sira bu: kalanlar herkesi koysun, sonra ayristirma_topa
    # kondansatorleri besledikleri bacaga ceksin. O noktada her
    # entegrenin bir konumu var.
    bos = kalanlar(fps, pn, kondu, en, boy)
    kritik += ayristirma_topa(fps, pn, kondu)
    kritik += ac_kalanlara_kondansator(fps, pn, kondu, kart=kart)
    cak = ayikla(fps, kondu, en, boy)
    # KENAR CIZGILERI DOSYADAN SILINDI (yukarida, LoadBoard'dan once).
    # b.Remove() burada da surece cokuyordu — ve yap.sh'in hata
    # toleransi bunu gizliyordu: yerlesim hic uygulanmiyor, kart
    # pcb_kur'un kuvvet-guduml u yerlesimiyle kaliyordu. Sessizce
    # yanlis kart uretmenin iyi bir ornegi.
    # MONTAJ DELIKLERI KART BOYUYLA BIRLIKTE TASINMALI. pcb_kur onlari
    # kendi varsaydigi olcuye (190x200) gore koyuyor; burada kenari
    # 235x225'e cizip delikleri birakinca biri PHY'nin uzerinde kaldi.
    # Ayrica referanssizdilar (REF**), DRC "Footprint REF**" diyordu.
    for a, bb, c, dd in ((0, 0, en, 0), (en, 0, en, boy),
                         (en, boy, 0, boy), (0, boy, 0, 0)):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(int(a * MM), int(bb * MM)))
        s.SetEnd(pcbnew.VECTOR2I(int(c * MM), int(dd * MM)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(int(0.1 * MM))
        b.Add(s)
    # ELLE KONUMLANDIRILANLARIN LISTESINI YAZ.
    # ayir.py sadece parca TIPINE bakiyordu (UJTYLQK sabit) ve
    # dirençleri oynatabiliyordu. Simetrik yerlestirdigim her direnci
    # sonradan kaydiriyordu: kapi ve kol dirençleri yerinden oynayinca
    # itme-cekme kollari yine esitsiz cikiyordu. Tip degil, KARAR
    # onemli — elle koyduysam sabittir.
    # IKI SINIF: SIMETRIK ve SADECE YERLESTIRILMIS.
    # Basta elle konulan her parcayi sabitlemistim. Fazla kati:
    # ayirici bir yigin kondansatoru artik itemedigi icin cakisma
    # 9'dan 11'e cikti ve her turda elle koordinat kovaladim.
    # Korunmasi gereken sey konum degil, SIMETRI. Ayna ciftleri ve
    # esit-uzunluk gruplari dokunulmaz; gerisi ayirici tarafindan
    # oynatilabilir.
    # SIMETRIK AGA DOKUNAN HER PARCA SABIT.
    # A'nin koridoru (x 0-60, y 112-212) tam alis zincirlerinin
    # bolgesi. Zincirin kendi seri dirençleri ve kondansatorleri
    # sabit degildi, koridor bosaltici onlari KENDI koridorlarindan
    # disari atti ve dort zincir 26.2 / 25.3 / 25.3 / 42.0 mm oldu.
    # Ref listesi tutmak yerine agdan turetiyoruz: elle_cek'in
    # korudugu bir aga dokunan parca, o simetrinin parcasidir.
    # YAPISKAN GRUPLAR DA SABIT. Bir regulator blogunun icindeki
    # kondansator ayirici tarafindan 3 mm oteye itilirse blok
    # varlik sebebini kaybediyor.
    sabitler = set(SIMETRIK.get(kart, ())) | set(BLOK_SABIT)
    try:
        import elle_cek
        kritik_ag = set(elle_cek.TABLOLAR.get(kart, {}))
    except Exception:
        kritik_ag = set()
    for ref, padlar in pn.items():
        if kritik_ag & set(padlar.values()):
            sabitler.add(ref)
    with open(os.path.join(HERE, dizin, "sabit.txt"), "w") as fh:
        fh.write("\n".join(sorted(sabitler)))
    # DOKUMU KART OLCUSUNE OTURT.
    # pcb_kur dokumu kendi varsaydigi olcuye gore ciziyor; burada
    # kenari degistirince doküm oldugu yerde kaliyor. Olculdu:
    # C'de kart 350x235, doküm 339'da bitiyor; D'de kart 240x185,
    # doküm 214x172. Sag ve alt kenardaki parcalarin altinda toprak
    # YOK — C'de 226, D'de 104 toprak pedi bagsiz kaldi.
    for z in b.Zones():
        poly = z.Outline()
        poly.RemoveAllContours()
        poly.NewOutline()
        for px, py in ((PED_ICERI, PED_ICERI), (en - PED_ICERI, PED_ICERI),
                       (en - PED_ICERI, boy - PED_ICERI),
                       (PED_ICERI, boy - PED_ICERI)):
            poly.Append(int(px * MM), int(py * MM))

    b.Save(pcb)
    print(f"{kart}: {kritik} kritik parca elle, {len(bos)} bagsiz, "
          f"{cak} cakisma, {en}x{boy} mm")


if __name__ == "__main__":
    for k in (sys.argv[1:] or ["A"]):
        uygula(k)
