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


def padnetler(dizin, proj):
    out = f"/tmp/gy_{proj}.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist",
                    os.path.join(HERE, dizin, proj + ".kicad_sch"),
                    "-o", out, "--format", "kicadsexpr"],
                   capture_output=True, check=True)
    t = open(out, encoding="utf-8").read()
    pn = {}
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
# Pedin dis yuzu kenardan bu kadar iceride. 0.3 mm'ydi; 0.6'ya
# cikarildi ki DSN sinirini 0.5 mm iceri cekince ped tamamen
# yonlendirilebilir alanin icinde kalsin. Kenar montaj SMA'sinda
# 0.3 mm'lik ek sap HF'te olcusuz kalir — 54 MHz'te dalga boyu 5.5 m.
PED_ICERI = 0.6
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
            xs = [q.GetPosition().x / MM for q in pedler]
            ys = [q.GetPosition().y / MM for q in pedler]
            wx = max(q.GetSizeX() / MM for q in pedler) / 2
            wy = max(q.GetSizeY() / MM for q in pedler) / 2
            sol, sag = min(xs) - wx, max(xs) + wx
            ust, alt = min(ys) - wy, max(ys) + wy
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
            n += koy(fps, r, A_ZINCIR_X["dif"], y, 90, kondu)
    # ---------- ADC'ler
    for adc, y in A_ADC_Y.items():
        n += koy(fps, adc, A_ADC_X, y, 0, kondu)
    # ---------- saat adasi: tampon iki ADC'nin TAM ORTASINDA
    n += koy(fps, "Y10", *A_VCXO, 0, kondu)
    n += koy(fps, "U15", *A_BUF, 0, kondu)
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
    for r, (x, y) in (("J1", (14, 6)), ("U1", (14, 42)),
                      ("U2", (14, 62)), ("L1", (34, 42)), ("L2", (34, 62))):
        n += koy(fps, r, x, y, 0, kondu)
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
            koy(fps, ref, q.x / MM + dx * 1.9, q.y / MM + dy * 1.9, 0, kondu)
        n += 1
    return n


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


def kalanlar(fps, pn, kondu, en, boy):
    """Konmamislari: ayristirma besledigi bacaga, otekiler komsusuna.

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
            padlar = pn.get(ref, {})
            aglar = set(padlar.values())
            hedef = None
            # ayristirma kondansatoru: besledigi entegrenin GUC BACAGINA
            if ref.startswith("C") and len(padlar) == 2 and "GND" in aglar:
                ray = next((a for a in aglar if a != "GND"), None)
                if ray:
                    ic = [r for r in yerli if r.startswith("U")
                          and ray in pn.get(r, {}).values()]
                    if ic:
                        en_iyi = max(ic, key=lambda r: sum(
                            1 for v in pn[r].values() if v == ray))
                        for pad in fps[en_iyi].Pads():
                            if pad.GetNetname() == ray:
                                p = pad.GetPosition()
                                hedef = (p.x / MM + 2.4, p.y / MM + 2.4)
                                break
            if hedef is None:
                aday = [r for r in kom.get(ref, ()) if r in yerli]
                if not aday:
                    continue
                xs = [fps[r].GetPosition().x / MM for r in aday]
                ys = [fps[r].GetPosition().y / MM for r in aday]
                hedef = (sum(xs) / len(xs) + 3.5, sum(ys) / len(ys) + 3.5)
            koy(fps, ref, min(max(hedef[0], 8), en - 8),
                min(max(hedef[1], 8), boy - 8))
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
                        cak += 1
                        ki = ref[i] in kondu
                        kj = ref[j] in kondu
                        if ki and kj:
                            continue
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
C_BANT_X0 = 42
C_BANT_ADIM = 40


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
        # KORUMA VE SERI DIRENCLER KENDI SERIDINDE.
        # Genel dolguya birakmistim: RX{k}_B1_IN agi 212 mm cikti,
        # yani antenle ilk bandin arasindaki 0 ohm direnc kartin ote
        # ucundaydi. Dort kanalda ayni oldugu icin simetri bozulmadi
        # ama 212 mm'lik bir RF hatti tek basina kayip ve anten.
        # Zincir sirasi: SMA -> koruma -> seri direnc -> bant 1.
        # Referans adimi kanal basina 9: ch1 R106/R107, ch2 R115/R116,
        # ch3 R124/R125, ch4 R133/R134. Once 2 yazmistim ve yalnizca
        # birinci kanal duzeldi.
        for j, r in enumerate((f"E{99 + k}", f"D{100 + (k - 1) * 5}",
                               f"R{106 + (k - 1) * 9}",
                               f"R{107 + (k - 1) * 9}")):
            if r in fps:
                n += koy(fps, r, 10 + j * 7, ky, 90, kondu)
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
            for i, r in enumerate(bobin):
                n += koy(fps, r, bx + 9 + i * 8, ky - 9, baci, kondu)
            for i, r in enumerate(kond):
                n += koy(fps, r, bx + 6 + (i % 4) * 7,
                         ky + 8 + (i // 4) * 5, 0, kondu)
    # T/R ROLESI VE SURUCUSU HER KANALIN KENDI SERIDINDE.
    # Genel dolguya birakinca KT'ler seritler arasina, QT4 de bir
    # role surucusunun (U73) uzerine dustu — ikisi de sabit sinifta
    # oldugu icin ayirici kurtaramadi. Role bant bankasindan SONRA,
    # cikisa giderken: alis/veris ayrimi filtreden sonra yapiliyor.
    for k, ky in enumerate(C_KANAL_Y, start=1):
        n += koy(fps, f"KT{k}", C_EN - 42, ky, 0, kondu)
        n += koy(fps, f"QT{k}", C_EN - 42, ky + 13, 0, kondu)

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
    for i in range(14):
        n += koy(fps, f"U{70 + i}", 24 + i * 23, C_BOY - 30, 0, kondu)
    for i in range(7):
        n += koy(fps, f"U{60 + i}", 30 + i * 46, C_BOY - 16, 0, kondu)
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
D_EN, D_BOY = 240, 185
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
    for r, x in (("U10", 26), ("U11", 52), ("T10", 78)):
        n += koy(fps, r, x, D_EKSEN, 0, kondu)
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
    n += koy(fps, "T11", (gx[1] + gx[2]) / 2, D_FINAL_Y + 26, 0, kondu)
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
    n += koy(fps, "Q20", (gx[0] + gx[1]) / 2, D_FINAL_Y + 44, 0, kondu)
    n += koy(fps, "Q21", (gx[2] + gx[3]) / 2, D_FINAL_Y + 44, 0, kondu)
    # Konuldular; simdi ONLARIN gercek konumuna gore ince ayar.
    for s, (a, c) in (("Q20", ("Q10", "Q11")), ("Q21", ("Q12", "Q13"))):
        hedef = (mrk(a)[0] + mrk(c)[0]) / 2
        q = fps[s].GetPosition()
        fps[s].SetPosition(pcbnew.VECTOR2I(
            int(q.x + (hedef - q.x / MM) * MM), q.y))
    q = fps["T11"].GetPosition()
    hedef = (mrk("Q11")[0] + mrk("Q12")[0]) / 2
    fps["T11"].SetPosition(pcbnew.VECTOR2I(
        int(q.x + (hedef - q.x / MM) * MM), q.y))
    # ---------- LPF bankasi: cikis trafosunun altinda, tek sira
    # G2RL-2 govdesi 13.1 x 29.4 mm — YUKSEK. Suruculeri 16 mm asagi
    # koymustum, rolenin govdesinin icinde kaliyorlardi. 24 mm asagi
    # ve adim 27 mm: yedi role 20..182 arasina siginca sag taraf
    # kuplor ve detektorlere kaliyor.
    for i in range(1, 8):
        bx = 20 + (i - 1) * 27
        n += koy(fps, f"KL{i}", bx, 128, 0, kondu)
        n += koy(fps, f"QL{i}", bx, 152, 0, kondu)
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
        for j, r in enumerate(bobin):
            n += koy(fps, r, bx - 6 + j * 13, 90, baci, kondu)
        for j, r in enumerate(kond):
            n += koy(fps, r, bx - 8 + j * 8, 106, 90, kondu)
    # ---------- kuplor ve detektorler: LPF cikisi
    for r, (x, y) in (("T20", (222, 128)), ("T21", (222, 150)),
                      ("U30", (200, 128)), ("U31", (200, 150)),
                      ("C407", (210, 122)), ("C612", (210, 134)),
                      ("C411", (210, 156)),
                      ("K20", (222, 106))):
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
        q = fps["T12"].GetPosition()
        fps["T12"].SetPosition(pcbnew.VECTOR2I(q.x, int((D_FINAL_Y + 58) * MM)))
    n += birincil_ortala("T12", "Q20", "Q21")
    n += birincil_ortala("T11", "Q10", "Q13")
    # AYNA EKSENI TRAFO HIZALANDIKTAN SONRA. Once T11'in eski
    # konumundan aliyordum, sonra trafo kayinca eksen bayatliyor ve
    # aynalanan dirençler yanlis yere dusuyordu.
    if "T11" in fps:
        pn = [q for q in fps["T11"].Pads() if q.GetNumber() in ("1", "2")]
        if pn:
            eks = sum(q.GetPosition().x for q in pn) / len(pn) / MM
    kolA = ((fps["Q10"].GetPosition().x + fps["Q11"].GetPosition().x)
            / 2 / MM) if "Q10" in fps else None
    if kolA is not None:
        n += ayna("R213", "R215", kolA, D_FINAL_Y + 32)
        # SURUCU KAPI DIRENCLERI SURUCULERIN EKSENINDE.
        # T11'in ekseninde aynaliyordum; surucu kati kendi ekseni
        # etrafinda simetrik olmali (Q20/Q21 ortasi), final katinin
        # degil. 20.9'a karsi 22.0 mm farki buradan geliyordu.
        sur_eks = eks
        if "Q20" in fps and "Q21" in fps:
            sur_eks = (fps["Q20"].GetPosition().x
                       + fps["Q21"].GetPosition().x) / 2 / MM
        eks_yedek, eks = eks, sur_eks
        n += ayna("R106", "R108", sur_eks - 26, D_FINAL_Y + 52)
        n += ayna("R107", "R109", sur_eks - 20, D_FINAL_Y + 52)
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
        n += koy(fps, f"R{202 + i * 2}", gx - 3, D_FINAL_Y + 9, 90, kondu)
        n += koy(fps, f"R{203 + i * 2}", gx + 3, D_FINAL_Y + 9, 90, kondu)

    # ---------- bias servolari kapilarin yaninda
    # INA240'lar kapi direnclerinin uzerine dusuyordu; olcum kati
    # RF hattinin altinda kendi seridinde.
    # Olcum kati ALT-SOL koseye. x=60'ta girisin RF bogucusunun
    # (L10) pedine oturuyorlardi; o serit zaten giris zincirinin.
    # Buradaki bosluk LPF surucu sirasinin altinda.
    for i in range(3):
        n += koy(fps, f"U{32 + i}", 30 + i * 22, 164, 0, kondu)
    # kaydirmali yazmac ve yardimci FET'ler kendi siralarinda
    n += koy(fps, "U56", 150, 164, 0, kondu)
    for i, r in enumerate(("Q31", "Q32")):
        n += koy(fps, r, 178 + i * 12, 164, 0, kondu)
    for r, (x, y) in (("U20", (100, 56)), ("U21", (100, 68)),
                      ("U41", (100, 80)), ("U42", (100, 92)),
                      # olcum katindaki iki entegre birbirinin ustune
                      # dusuyordu; sicaklik sensoru sogutucu tarafina
                      ("U57", (100, 164)), ("U55", (125, 164))):
        n += koy(fps, r, x, y, 0, kondu)
    # ---------- guc: SAG UST KOSE, RF hattindan en uzak
    n += koy(fps, "J30", D_EN - 0.5, 12, KENAR_ACI["sag"], kondu, kenar=True)
    for r, (x, y) in (("U50", (200, 26)), ("U51", (200, 46)),
                      ("Q30", (200, 62)), ("C601", (222, 26)),
                      ("C602", (222, 44))):
        n += koy(fps, r, x, y, 0, kondu)
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
    "D": ("Q10", "Q11", "Q12", "Q13", "Q20", "Q21", "T10", "T11", "T12",
          "R202", "R203", "R204", "R205", "R206", "R207", "R208", "R209",
          "R213", "R215", "R106", "R107", "R108", "R109",
          # Kaynak olcum dirençleri her cihazin ALTINDA olmali —
          # koridorun icinde ama oraya ait. Sabit degillerse koridor
          # bosaltici onlari kartin disina itiyor (uc pedin ust
          # kenari -3.41 mm cikti).
          "RS1", "RS2", "RS3", "RS4"),
    "A": tuple(f"T{i}" for i in range(1, 5)) + ("U15", "Y10", "U20", "U21"),
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
    KART_OLCU[0], KART_OLCU[1] = en, boy
    # SIRALI: kart ici sira UUID'lere bagli ve her kurulumda
    # farkli; sirasiz dolasmak yerlesimi tekrarlanmaz yapiyor.
    fps = {fp.GetReference(): fp
           for fp in sorted(b.Footprints(),
                            key=lambda x: x.GetReference())}
    pn = padnetler(dizin, proj)
    kondu = set()
    kritik = fn(fps, pn, kondu)
    kritik += adc_referans(fps, pn, kondu)
    kritik += ayristirma_topa(fps, pn, kondu)
    bos = kalanlar(fps, pn, kondu, en, boy)
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
    kose = ((5, 5), (en - 5, 5), (5, boy - 5), (en - 5, boy - 5))
    # ZATEN KURULU fps SOZLUGUNU KULLAN. b.Footprints() ayni surecte
    # ikinci kez cagrilinca bozuk proxy donduruyor (GetFPID() yok).
    # REFERANSTAN TANI. GetFPID() de bozuk proxy donduruyor; montaj
    # delikleri zaten kartta referanssiz (REF**) olan tek parcalar.
    for i, fp in enumerate(delikler[:4]):
        x, y = kose[i]
        fp.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
        fp.SetReference(f"H{i + 1}")
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
    sabitler = set(SIMETRIK.get(kart, ()))
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
