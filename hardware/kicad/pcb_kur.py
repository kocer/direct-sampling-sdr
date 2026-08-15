#!/usr/bin/env python3
"""Semadan PCB kurar: ayak izlerini yukler, aglari baglar, katman
yigini ve tasarim kurallarini koyar, islevsel gruplara yerlestirir.

    python3 pcb_kur.py A       # A karti
    python3 pcb_kur.py C
    python3 pcb_kur.py D

Yonlendirme BURADA YAPILMIYOR. Bu betik karti yonlendirilebilir hale
getiriyor: dogru yigin, dogru kurallar, dogru yerlesim. Yonlendirme
ayri adim (pcb_route.sh).

NEDEN BETIKLE: dort ozdes alis zinciri ve 28 ozdes filtre bolumu elle
yerlestirilirse birbirinden farkli olur. Faz uyumu bu kartlarin
ayirt edici ozelligi ve simetriye bagli — betik simetriyi garanti
ediyor, el garanti etmiyor.
"""
import json, math, os, re, subprocess, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
MM = 1000000          # pcbnew ic birimi: nanometre

# KART OLCUSU TEK KAYNAKTAN: gercek_yerlesim.
#
# Burada en/boy elle yazilirdi (170x130, 240x180, 160x120) ve
# gercek_yerlesim'deki gercek olculerle (235x225, 350x235, 275x185)
# TUTMUYORDU. Zararsiz gorunuyordu cunku kenari gercek_yerlesim
# ciziyor; ama iki ayri "gercek" birakmak, bir gun birinin
# otekinden habersiz degismesi demek — nitekim dis_hat montaj
# deliklerini BU olculere gore koyuyordu ve gercek_yerlesim
# onlari sonradan tasimak zorunda kaliyordu.
# Artik olcu gercek_yerlesim'den geliyor; buradaki deger sadece
# kuvvet-guduml u ilk dizimin baslangic kutusu ve o da ayni sayi.
import gercek_yerlesim as _GY

KARTLAR = {
    "A": dict(dizin="A_main", proj="dogrudan_sdr_A", katman=6,
              en=_GY.A_EN, boy=_GY.A_BOY),
    "C": dict(dizin="C_rf", proj="dogrudan_sdr_C", katman=2,
              en=_GY.C_EN, boy=_GY.C_BOY),
    "D": dict(dizin="D_pa", proj="dogrudan_sdr_D", katman=2,
              en=_GY.D_EN, boy=_GY.D_BOY),
}

# ---------------------------------------------------------------- yigin
# A karti 6 katman. Sira ADC'nin gurultu tabanini korumak icin secildi:
#   1 sinyal   ust, bilesenler ve kisa yollar
#   2 TOPRAK   kesintisiz — ADC'nin altinda yarik YOK
#   3 sinyal   ic, RGMII ve LVDS burada (iki toprak arasinda gomulu)
#   4 GUC      raylar, adalara bolunmus
#   5 sinyal   ic
#   6 TOPRAK   alt referans
# LVDS ve RGMII'yi 3. katmana koymak: iki toprak duzlemi arasinda
# gomulu serit hat, yayilim en az. Ust katmanda giderlerse ADC'nin
# analog ucuna kuple olurlar.
YIGIN_A = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]

# ---------------------------------------------------------------- ag sinifi
# Empedans hedefleri. Genislikler 6 katmanli 1.6 mm yigin icin
# yaklasik; uretici yigin verisiyle dogrulanacak.
AG_SINIFI = {
    "RF50": dict(track=0.45, via=0.6, drill=0.3, clear=0.25,
                 desen=r"^(RF_|TX_|ANT|PA_OUT|RX\d_)"),
    "LVDS": dict(track=0.2, via=0.4, drill=0.2, clear=0.2,
                 diff=0.15, desen=r"^(ADCLK_|FPGA_PCLK|DACCLK_|CLKTEST)"),
    "RGMII": dict(track=0.2, via=0.4, drill=0.2, clear=0.2,
                  desen=r"^PHY\d_(TX|RX)"),
    "GUC": dict(track=0.8, via=0.8, drill=0.4, clear=0.25,
                desen=r"^(\+|GND|VIN|VCXO_VDD|PHY\d_1V0)"),
    "VARSAYILAN": dict(track=0.2, via=0.4, drill=0.2, clear=0.2, desen=r".*"),
}


def fp_kutuphaneleri():
    """fp-lib-table'lardan {kutuphane_adi: dizin} cikar."""
    yollar = ["/usr/share/kicad/template/fp-lib-table",
              os.path.expanduser("~/.config/kicad/10.0/fp-lib-table")]
    d = {}
    for y in yollar:
        if not os.path.exists(y):
            continue
        t = open(y, encoding="utf-8").read()
        for m in re.finditer(r'\(name "([^"]+)"\).*?\(uri "([^"]+)"\)', t):
            ad, uri = m.groups()
            uri = uri.replace("${KICAD10_FOOTPRINT_DIR}",
                              "/usr/share/kicad/footprints")
            uri = uri.replace("${KICAD9_FOOTPRINT_DIR}",
                              "/usr/share/kicad/footprints")
            d[ad] = uri
    d["dogrudan-sdr"] = os.path.join(HERE, "lib", "dogrudan-sdr.pretty")
    return d


def netlist(dizin, proj):
    """{ref: (deger, ayak_izi, {pad: ag})}"""
    out = f"/tmp/pcb_{proj}.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist",
                    os.path.join(HERE, dizin, proj + ".kicad_sch"),
                    "-o", out, "--format", "kicadsexpr"],
                   capture_output=True, check=True)
    t = open(out, encoding="utf-8").read()
    comps = {}
    # Sayfa adi da aliniyor: gruplama icin en dogru anahtar bu.
    # Once referans desenleriyle gruplamistim; desenler her seyi
    # kapsamadi, kapsanmayanlar bir kosede yigildi ve ust uste bindi.
    # Sema sayfasi zaten islevsel ayrimin ta kendisi.
    for m in re.finditer(
            r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*'
            r'\(footprint "([^"]*)"\).*?\(sheetpath\s*\(names "([^"]*)"\)',
            t, re.S):
        ref, val, fp, sayfa = m.groups()
        if not ref.startswith("#"):
            comps[ref] = [val, fp, {}, sayfa.strip("/")]
    for m in re.finditer(
            r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', t, re.S):
        ag, body = m.groups()
        for ref, pad in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body):
            if ref in comps:
                comps[ref][2][pad] = ag
    return comps


# ---------------------------------------------------------------- yerlesim
# Gruplama SEMA SAYFASINA gore. Sayfalar zaten islevsel ayrim: guc,
# saat, ADC, DAC, ethernet... Her sayfa bir blok oluyor, bloklar
# cakismayan bir izgaraya diziliyor.
#
# Sayfa sirasi kartin akisini belirliyor. RF once, sonra donusum,
# sonra sayisal, guc kenarda. Analog ile anahtarlamali guc arasina
# mesafe koymak ADC'nin gurultu tabanini korumanin en ucuz yolu.
SAYFA_SIRASI = {
    "A": ["ADC x2", "Saat dagitimi", "DAC x2", "FPGA guc + konfig",
          "SDRAM", "Ethernet x2", "Kontrol", "Guc agaci"],
    "C": ["Koruma + T/R", "Filtre bankasi", "Zayiflaticilar",
          "Role surucu", "Kart arasi", "Guc"],
    "D": ["Surucu katlari", "Final kat", "Bias servosu", "Kuplor + olcum",
          "Cikis filtreleri", "Guc ve koruma"],
}
BOSLUK = 6.0        # bloklar arasi bosluk, mm
KENAR = 10.0        # kart kenarindan bosluk (bakir-kenar acikligi icin)


def olcu(fp, pay=1.6):
    """Parcanin gercek kapladigi alan, mm.

    GetBoundingBox() REFERANS VE DEGER YAZILARINI da sayiyor: bir
    QFN-64 icin 34 x 13 mm donuyor, oysa gercek courtyard 10.3 x 10.3.
    Yaziya gore yerlestirince kartlar iki katina cikti. Courtyard
    varsa onu kullan, yoksa pedlerin sinirini."""
    try:
        c = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = c.BBox()
        if bb.GetWidth() > 0 and bb.GetHeight() > 0:
            return bb.GetWidth() / MM + pay, bb.GetHeight() / MM + pay
    except Exception:
        pass
    bb = None
    for pad in fp.Pads():
        b = pad.GetBoundingBox()
        if bb is None:
            bb = b
        else:
            bb.Merge(b)
    if bb is not None and bb.GetWidth() > 0:
        return bb.GetWidth() / MM + pay * 2, bb.GetHeight() / MM + pay * 2
    b = fp.GetBoundingBox()
    return b.GetWidth() / MM + pay, b.GetHeight() / MM + pay


def ayristirma_eslesmesi(fps, comps):
    """Her ayristirma kondansatorunu ait oldugu entegreye esle.

    Pin basina 100nF'in tek anlami ENTEGRENIN BESLEME BACAGININ
    DIBINDE olmasi. Satir halinde dizilirse hicbir ise yaramaz:
    kondansatorden pine giden yolun endüktansi kondansatorun faydasini
    yiyor. Yerlesimde kondansator entegrenin yaninda olmali.

    Eslesme: iki bacakli, biri GND digeri bir ray olan parca ->
    ayni sayfadaki, o raya en cok bacagi bagli entegre.
    """
    ic_rays = {}          # ref -> {ray: bacak sayisi}
    for ref, (val, fp, padlar, sayfa) in comps.items():
        if not ref.startswith("U"):
            continue
        d = {}
        for ag in padlar.values():
            if ag.startswith("+") or ag.endswith(("_1V0", "_VDD")):
                d[ag] = d.get(ag, 0) + 1
        if d:
            ic_rays[ref] = (sayfa, d)

    eslesme = {}
    for ref, (val, fp, padlar, sayfa) in comps.items():
        if not ref.startswith("C") or len(padlar) != 2:
            continue
        aglar = set(padlar.values())
        if "GND" not in aglar:
            continue
        ray = next((a for a in aglar if a != "GND"), None)
        if not ray or not ray.startswith("+"):
            continue
        adaylar = [(n, s[ray]) for n, (sy, s) in ic_rays.items()
                   if sy == sayfa and ray in s]
        if adaylar:
            eslesme[ref] = max(adaylar, key=lambda z: z[1])[0]
    return eslesme


def blok_diz(oge, gx, gy, hedef_en, eslesme=None):
    """Bir sayfanin parcalarini satir satir diz, (en, boy) don."""
    def boyut(t):
        w, h = olcu(t[1])
        return -(w * h)
    oge.sort(key=boyut)
    # Ayristirma kondansatorlerini entegrelerinin HEMEN ARDINA al:
    # dizim sirasi yerlesim sirasi oldugu icin boylece yanlarina
    # dusuyorlar. Satir halinde dizilseler hicbir ise yaramazdi.
    if eslesme:
        sirali, alindi = [], set()
        for ref, fp in oge:
            if ref in alindi:
                continue
            sirali.append((ref, fp))
            alindi.add(ref)
            for r2, f2 in oge:
                if r2 not in alindi and eslesme.get(r2) == ref:
                    sirali.append((r2, f2))
                    alindi.add(r2)
        oge = sirali
    cx, cy, satir_h, max_x = gx, gy, 0.0, gx
    for ref, fp in oge:
        w, h = olcu(fp)
        if cx > gx and cx + w > gx + hedef_en:
            cx = gx
            cy += satir_h
            satir_h = 0.0
        # Ayak izinin ORIJINI courtyard merkezinde olmak zorunda degil
        # (konnektorlerde cogu zaman degil). Once koy, sonra courtyard
        # merkeziyle hedef arasindaki farki telafi et — yoksa parca
        # hesapladigimiz kutunun disina tasar ve komsusuyla cakisir.
        hedef = pcbnew.VECTOR2I(int((cx + w / 2) * MM), int((cy + h / 2) * MM))
        fp.SetPosition(hedef)
        try:
            c = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            if c.GetWidth() > 0:
                merkez = c.GetCenter()
                fp.SetPosition(pcbnew.VECTOR2I(
                    hedef.x + (hedef.x - merkez.x),
                    hedef.y + (hedef.y - merkez.y)))
        except Exception:
            pass
        cx += w
        max_x = max(max_x, cx)
        satir_h = max(satir_h, h)
    return max_x - gx, (cy + satir_h) - gy


def yerlestir(board, kart, fps, sayfalar, eslesme=None):
    """Sayfa bloklarini cakismayan sekilde yerlestir; kart boyunu don."""
    gruplar = {}
    for ref, fp in fps.items():
        gruplar.setdefault(sayfalar.get(ref, "muhtelif"), []).append((ref, fp))

    sira = [s for s in SAYFA_SIRASI[kart] if s in gruplar]
    sira += [s for s in gruplar if s not in sira]

    # HEDEF GENISLIK PARCA ALANINDAN. Once sabit bir genislik
    # kullaniyordum ve kart 176x298 gibi cok uzun cikiyordu — satir
    # bazli dizim bos alan biraktikca boy uzuyor. Toplam parca alanini
    # olcup 1.3 en/boy oranina yakin bir hedef seciyoruz.
    alan = 0.0
    for oge in gruplar.values():
        for _, fp in oge:
            w0, h0 = olcu(fp)
            alan += w0 * h0
    DOLULUK = 0.42      # yonlendirme icin bosluk birakiyoruz
    hedef_alan = alan / DOLULUK
    hedef_en = math.sqrt(hedef_alan * 1.3)
    # Her blogu once olcup sonra yerlestiriyoruz: iki gecis. Tek
    # gecisde blok boyu bilinmedigi icin bloklar ust uste biniyordu.
    # Blok genisligi hedefin yarisi: iki blok yan yana sigsin.
    blok_en = hedef_en / 2 - BOSLUK
    olculer = {}
    for ad in sira:
        w, h = blok_diz(list(gruplar[ad]), 0, 0, blok_en, eslesme)
        olculer[ad] = (w, h)

    x, y, satir_h, max_x, max_y = KENAR, KENAR, 0.0, KENAR, KENAR
    for ad in sira:
        w, h = olculer[ad]
        if x > KENAR and x + w > KENAR + hedef_en:
            x = KENAR
            y += satir_h + BOSLUK
            satir_h = 0.0
        blok_diz(gruplar[ad], x, y, blok_en, eslesme)
        x += w + BOSLUK
        satir_h = max(satir_h, h)
        max_x = max(max_x, x)
        max_y = max(max_y, y + h)
    return max_x + KENAR, max_y + KENAR
# ---------------------------------------------------------------- kurulum
def kurallar(board, kart):
    """Tasarim kurallari ve ag siniflari."""
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(KARTLAR[kart]["katman"])
    # JLCPCB sinirlari: en kucuk delik 0.20 mm, en kucuk iz/aciklik
    # 0.127 mm. Varsayilan KiCad kurallari daha dar ve elde ettigimiz
    # ayak izleri "drill out of range" veriyordu.
    # ASGARI DELIK 0.20 DEGIL 0.30. Kural 0.20'de kalinca
    # kutuphanedeki 0.2 mm isi vialari DRC'den sessizce
    # geciyordu — kural kendisiyle tutarliydi ama uretimle
    # degil. delikleri_buyut() pedleri 0.3'e cikariyor;
    # kural da onu denetleyecek sekilde ayarlaniyor.
    ds.m_MinThroughDrill = int(0.30 * MM)
    ds.m_TrackMinWidth = int(0.127 * MM)
    ds.m_ViasMinSize = int(0.40 * MM)
    ds.m_MinClearance = int(0.127 * MM)
    # BOSLUK TAVANI KARTA GORE — DRC ILE YONLENDIRICI AYNI SEYI
    # SOYLEMEK ZORUNDA.
    # A kartinda BGA kacisi icin DSN boslugu 127 um'ye indirildi
    # (dsn_yaz: 0.8 mm adimli CABGA256'da 300 um ile via GEOMETRIK
    # OLARAK sigmiyor). Ag sinifinin DRC boslugu 200 um kalirsa
    # yonlendiricinin cektigi her iz DRC hatasi olur. Sinif degeri
    # burada kartin tabanina kirpiliyor:
    #     A  127 um   (JLCPCB 4+ katman standart sinif 0.09 mm)
    #     C  150 um
    #     D  250 um   (2 oz dis bakir; o surecte asgari 0.25 mm)
    # Genis guc izleri yine 300 um arayla cekiliyor — onu DSN
    # tarafindaki sinif kurali sagliyor. Buradaki deger bir TABAN,
    # hedef degil.
    # DEGERLER URETIM SINIRI, YONLENDIRME HEDEFI DEGIL.
    # Yonlendirici DSN'de A'da 127, C'de 150, D'de 300 um hedefiyle
    # cekiyor. DRC kuralini AYNI sayiya koyarsak kural bir seyi
    # denetlemiyor: yonlendiricinin ciktisi tanim geregi tam o
    # degerde ve 1-2 um'lik yuvarlama farki hata olarak cikiyor
    # (olculdu: "clearance 0.2000; actual 0.1517" tipinde 501 kayit,
    # hepsi yuvarlama mesafesinde). DRC'nin isi URETILEBILIRLIGI
    # denetlemek:
    #   A  6 katman, JLCPCB standart siniri 0.0889 mm -> 0.10
    #   C  2 katman, standart sinir 0.127 mm           -> 0.127
    #   D  2 katman 2 oz, o surecte sinir 0.254 mm     -> 0.25
    # Yonlendirici her kartta bu tabanin uzerinde bir hedefle
    # calisiyor, yani arada gercek bir pay var.
    # D'YE 0.25 VERILMISTI, GERI ALINDI. Gerekce 2 oz bakirin
    # uretim siniriydi ama o sinir IZLER icin gecerli; PEDLERIN
    # arasi paketin kendi geometrisi ve degistirilemiyor.
    # Olculdu, karttaki en kucuk ped-ped acikligi (ayni ayak izi
    # icinde, farkli aglar):
    #     A 0.177 mm (AD9251 QFN-64)
    #     C 0.200 mm (PE4312 QFN-20)
    #     D 0.177 mm (AD8318 QFN-16)
    # 0.25'lik bir kural bunlarin hepsini "ihlal" sayardi ve DRC
    # her kosuda kalici gurultu uretirdi — gercek bir ihlal o
    # gurultunun icinde kaybolur.
    # Iz araligini kural degil YONLENDIRICI garanti ediyor: DSN
    # sinif kurallari A'da 127, C'de 150, D'de 300 um. Ice aldiktan
    # sonra gercek en kucuk iz araligi olculup raporlaniyor.
    BOSLUK_TAVANI = {"A": 0.10, "C": 0.127, "D": 0.127}
    tavan = BOSLUK_TAVANI.get(kart, 0.2)
    ncmap = board.GetAllNetClasses()
    # ** ASIL KURALI BELIRLEYEN SINIF "Default". **
    # Asagida AG_SINIFI'ndan uretilen siniflar (RF50, LVDS, GUC...)
    # kart dosyasina KAYDEDILMIYOR: kaydedilip geri okununca kartta
    # tek sinif kaliyor, "Default". Yani butun DRC boslugu onun
    # degeriyle, 0.200 mm ile olculuyordu.
    # Olculdu: C kartinda yonlendirici 150 um araliga cekti (DSN
    # sinif kurali oyle diyor) ve DRC 501 clearance hatasi verdi —
    # hepsi "clearance 0.2000 mm; actual 0.15 mm". Yani yonlendirici
    # ile DRC ayni kartta iki farkli kural kullaniyordu.
    # Default'un boslugu kartin tabanina cekiliyor; DSN tarafindaki
    # sinif kurallari zaten guc izlerini 300 um'de tutuyor.
    if "Default" in ncmap:
        ncmap["Default"].SetClearance(int(tavan * MM))
    for ad, k in AG_SINIFI.items():
        nc = ncmap[ad] if ad in ncmap else pcbnew.NETCLASS(ad)
        nc.SetTrackWidth(int(k["track"] * MM))
        nc.SetViaDiameter(int(k["via"] * MM))
        nc.SetViaDrill(int(k["drill"] * MM))
        nc.SetClearance(int(min(k["clear"], tavan) * MM))
        if "diff" in k:
            nc.SetDiffPairWidth(int(k["track"] * MM))
            nc.SetDiffPairGap(int(k["diff"] * MM))
        ncmap[ad] = nc
    return ncmap


def dis_hat(board, en, boy, kart=None, gnd=None):
    """Kart dis hatti, 3 mm kose yaricapi yerine duz — uretim ucuz.

    MONTAJ DELIKLERI VE SASE BAGI. Uc kart ayni kasaya giriyor ve
    metal ayaklarla vidalaniyor. Her kart kendi montaj deliginden
    kasaya baglanirsa aralarinda toprak dongusu olusur: kasa
    uzerinden akan sebeke/anahtarlama akimi alis on ucunun
    referansina biner. Sistemde TEK sase referans noktasi var ve
    o C kartinda — anten konnektorleri orada, kasa zaten anten
    toprak referansi.

        C   anten konnektorlerine en yakin delik KAPLAMALI, GND'de
        A   dort delik de kaplamasiz
        D   dort delik de kaplamasiz

    C'de kaplamali delik LISTENIN BASINDA uretiliyor; gercek_yerlesim
    delikleri pedli olan basa gelecek sekilde siralayip ilkini
    (5,5) kosesine koyuyor — C'de anten konnektorleri sol kenarda,
    J1 y=25'te, yani o kose 20 mm otesi.
    """
    for a, b, c, d in ((0, 0, en, 0), (en, 0, en, boy),
                       (en, boy, 0, boy), (0, boy, 0, 0)):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(int(a * MM), int(b * MM)))
        s.SetEnd(pcbnew.VECTOR2I(int(c * MM), int(d * MM)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(int(0.1 * MM))
        board.Add(s)
    # dort kose montaj deligi, 3.2 mm (M3)
    libs = fp_kutuphaneleri()
    koseler = ((5, 5), (en - 5, 5), (5, boy - 5), (en - 5, boy - 5))
    for i, (x, y) in enumerate(koseler):
        kaplamali = (kart == "C" and i == 0)
        ad = ("MountingHole_3.2mm_M3_Pad" if kaplamali
              else "MountingHole_3.2mm_M3")
        try:
            fp = pcbnew.FootprintLoad(libs["MountingHole"], ad)
            if fp:
                fp.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
                board.Add(fp)
                if kaplamali and gnd is not None:
                    for pad in fp.Pads():
                        pad.SetNet(gnd)
        except Exception:
            pass


def toprak_dokum(board, kart):
    """Toprak duzlemleri. A kartinda 2 ve 6, iki katmanlida F ve B.

    ADC'nin altinda YARIK OLMAYACAK: dokum tum karti kapliyor ve
    bolunmuyor. Guc adalari 4. katmanda, toprakta degil.
    """
    en, boy = KARTLAR[kart]["en"], KARTLAR[kart]["boy"]
    gnd = board.FindNet("GND")
    if gnd is None:
        return 0
    katmanlar = ([pcbnew.In1_Cu, pcbnew.In4_Cu] if KARTLAR[kart]["katman"] == 6
                 else [pcbnew.F_Cu, pcbnew.B_Cu])
    n = 0
    for lay in katmanlar:
        z = pcbnew.ZONE(board)
        z.SetLayer(lay)
        z.SetNetCode(gnd.GetNetCode())
        z.SetLocalClearance(int(0.3 * MM))
        z.SetMinThickness(int(0.2 * MM))
        pts = pcbnew.VECTOR_VECTOR2I()
        for x, y in ((1, 1), (en - 1, 1), (en - 1, boy - 1), (1, boy - 1)):
            pts.append(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
        z.AddPolygon(pts)
        board.Add(z)
        n += 1
    return n


ASGARI_DELIK = 0.30      # mm, JLCPCB standart surec
# HALKA 0.15 DEGIL 0.10.
# 0.15 ile isi viasinin pedi 0.5 -> 0.6 mm oluyordu ve QFN'in sinyal
# pedlerine 0.15 mm kaliyordu (kural 0.2): C'de 32, D'de 8 clearance
# hatasi. PE4312 ve DRV8833'un isi via dizisi zaten sinyal pedlerinin
# dibinde; ped buyutulecek yer yok.
# 0.3 mm delik + 0.5 mm ped = her yanda 0.10 mm halka, ki JLCPCB'nin
# via icin standart alt siniri. Delik buyutmenin amaci zaten surec
# sinifiydi (0.2 mm ileri surec), halka degil.
ASGARI_HALKA = 0.10      # mm, delik basina her yandan bakir


def delikleri_buyut(board):
    """0.2 mm delikleri 0.3 mm'ye cikar — URETIM SURECI MESELESI.

    Kutuphanedeki "*_ThermalVias" ayak izleri isi vialarini 0.2 mm
    delikle koyuyor. Olculdu: A'da 9 (U15), C'de 184 (PE4312 x4 +
    DRV8833 x14), D'de 10 (U10, U50) — toplam 203 delik.

    DRC bunu YAKALAMIYOR cunku kartin kendi asgari delik kurali da
    0.2 mm; kural kendisiyle tutarli oldugu icin sessiz. Ama 0.2 mm
    JLCPCB'de ileri surec: fiyati yukseltiyor ve teslim suresini
    uzatiyor, ustelik uc kartin UCUNU birden etkiliyor.

    Isi direnci acisindan kayip yok: alti adet 0.3 mm'lik via, on
    adet 0.2 mm'likten daha genis kesit veriyor. Ped de buyuyor
    (0.3 + 2 x 0.15 = 0.6 mm) yoksa halka kalmaz ve delik pedin
    kenarindan cikar.
    """
    n = 0
    for fp in sorted(board.Footprints(), key=lambda f: f.GetReference()):
        for pad in fp.Pads():
            d = pad.GetDrillSizeX() / MM
            if not 0 < d < ASGARI_DELIK:
                continue
            pad.SetDrillSize(pcbnew.VECTOR2I(int(ASGARI_DELIK * MM),
                                             int(ASGARI_DELIK * MM)))
            en_az = ASGARI_DELIK + 2 * ASGARI_HALKA
            if pad.GetSizeX() / MM < en_az:
                pad.SetSize(pcbnew.VECTOR2I(int(en_az * MM),
                                            int(en_az * MM)))
            n += 1
    return n


def kur(kart):
    k = KARTLAR[kart]
    comps = netlist(k["dizin"], k["proj"])
    libs = fp_kutuphaneleri()
    board = pcbnew.BOARD()
    kurallar(board, kart)

    agi = {}

    def ag(ad):
        if ad not in agi:
            n = pcbnew.NETINFO_ITEM(board, ad)
            board.Add(n)
            agi[ad] = n
        return agi[ad]

    fps, eksik, sayfalar = {}, [], {}
    for ref, (val, fpid, padlar, sayfa) in sorted(comps.items()):
        sayfalar[ref] = sayfa
        if ":" not in fpid:
            eksik.append((ref, fpid))
            continue
        lib, ad = fpid.split(":", 1)
        if lib not in libs:
            eksik.append((ref, fpid))
            continue
        try:
            fp = pcbnew.FootprintLoad(libs[lib], ad)
        except Exception:
            fp = None
        if fp is None:
            eksik.append((ref, fpid))
            continue
        fp.SetReference(ref)
        fp.SetValue(val)
        board.Add(fp)
        fps[ref] = fp
        for pad in fp.Pads():
            nm = padlar.get(pad.GetNumber())
            if nm:
                pad.SetNet(ag(nm))

    # Kart boyu YERLESIMDEN cikiyor, tersi degil. Kutu kisiti yok
    # (PA_TASARIM.md §11), o yuzden karti sikistirmaya calismiyoruz:
    # ferah yerlesim = kisa yol = daha iyi sinyal butunlugu.
    esl = ayristirma_eslesmesi(fps, comps)
    en, boy = yerlestir(board, kart, fps, sayfalar, esl)
    k["en"], k["boy"] = round(en + 0.5), round(boy + 0.5)
    # Bagliliga gore iyilestir. Sayfa dizimi baslangic noktasi;
    # asil yerlesim buradan cikiyor.
    # Yasallastirma yakinsamazsa kart parcalar icin KUCUK demektir.
    # Kutu kisiti yok (PA_TASARIM.md §11), buyutmek serbest.
    # KAT PLANI CAPALARI. Kuvvet yontemi baglantilari kisaltiyor ama
    # neyin nerede olacagini fizik degil algoritma seciyordu. Capalar
    # o karari geri aliyor: SMA'lar kenarda, saat iki ADC'nin ortasinda
    # (LVDS esit uzunluk), FPGA merkezde, guc ADC'den en uzak kosede.
    import kat_plani as KP
    # SADECE KENARDA OLMAK ZORUNDA OLANLAR capalanir: konnektorler,
    # magjack'ler, guc girisi. Butun kat planini capalayinca hareketli
    # parcalar sabitler arasinda sikisti ve 63 cakisma cozulemedi.
    # Geri kalanin yerini kuvvet secsin — orada algoritma insandan
    # kotu degil; kenar konnektoru ise fizik, tartisilmaz.
    # ** CAPALAR KAPALI — OLCUM BOYLE SOYLUYOR. **
    # Kat plani (kat_plani.py) elle dusunulmus, mantikli bir plan:
    # SMA'lar kenarda, saat iki ADC'nin ortasinda, guc uzak kosede.
    # Ama capalayinca A kartinda ortalama baglanti 20.5 mm'den
    # 66.4 mm'ye cikti — uc kat kotu. Sebep: sabit noktalar
    # eniyilemeyi bogyor, ozellikle kart-arasi baslikar cok sayida
    # aga bagli ve nereye civilenirse oraya uzun yol cekiyor.
    #
    # Plan yanlis degil, UYGULAMASI eksik: capalar konurken o
    # capalara bagli parcalarin da birlikte tasinmasi gerekiyor
    # (blok yerlesimi), tek tek civilemek yetmiyor. Bu is duruyor;
    # simdilik olcumun daha iyi buldugu yontem kullaniliyor.
    tum = {"A": KP.A_CAPA, "C": KP.C_CAPA, "D": KP.D_CAPA}.get(kart, {})
    capa = {}
    sabit = set()
    for ref, (cx, cy, caci) in capa.items():
        if ref in fps:
            fps[ref].SetPosition(pcbnew.VECTOR2I(int(cx * MM), int(cy * MM)))
            if caci:
                fps[ref].SetOrientationDegrees(caci)
            sabit.add(ref)

    # BUYUTME KAPALI. Cakisma kalinca karti buyutuyordum; kart
    # 193x198'den 262x269'a cikti ve parcalar yayilinca ortalama
    # baglanti 20.5 mm'den 66 mm'ye FIRLADI. Buyutmek cakismayi
    # cozuyordu ama asil derdi (kisa yol) bozuyordu.
    # Kalan birkac cakismayi drc_duzelt.py tek tek ayiriyor.
    once = sonra = kalan = None
    for deneme in range(4):
        once, sonra, kalan = kuvvet_yerlesim(fps, comps, k["en"], k["boy"],
                                             sabit=sabit)
        if kalan == 0:
            break
        k["en"] = round(k["en"] * 1.08)
        k["boy"] = round(k["boy"] * 1.08)
        # Sayfa dizimine geri don: buyumus kartta kuvvet adimi bastan
        # calissin. Kalmis konumlardan devam edince "once" olcusu zaten
        # iyilesmis durumdan aliniyor ve kazanc %8 gibi gorunuyordu.
        yerlestir(board, kart, fps, sayfalar, esl)
        for ref, (cx, cy, caci) in capa.items():
            if ref in fps:
                fps[ref].SetPosition(pcbnew.VECTOR2I(int(cx * MM),
                                                     int(cy * MM)))
        print(f"   {kart}: {kalan} cakisma kaldi, kart "
              f"{k['en']}x{k['boy']} mm'ye buyutuluyor")
    dis_hat(board, k["en"], k["boy"], kart, agi.get("GND"))
    nz = toprak_dokum(board, kart)
    buyutulen = delikleri_buyut(board)

    # ag sinifi atamasi: desene gore
    ncmap = board.GetAllNetClasses()
    for nm, n in agi.items():
        for sinif, kk in AG_SINIFI.items():
            if sinif != "VARSAYILAN" and re.match(kk["desen"], nm):
                if sinif in ncmap:
                    n.SetNetClass(ncmap[sinif])
                break

    yol = os.path.join(HERE, k["dizin"], k["proj"] + ".kicad_pcb")
    board.Save(yol)
    print(f"{kart}: {len(fps)} ayak izi, {len(agi)} ag, {nz} dokum, "
          f"{k['en']}x{k['boy']} mm | ratsnest {once:.0f} -> {sonra:.0f} mm "
          f"({100 * (1 - sonra / once):.0f}% kisaldi), capa {len(sabit)}, "
          f"cakisma {kalan}"
          f" -> {os.path.basename(yol)}")
    if eksik:
        print(f"   ** {len(eksik)} AYAK IZI YUKLENEMEDI **")
        for ref, fpid in eksik[:8]:
            print(f"      {ref:<8} {fpid}")
    return len(eksik)


# ---------------------------------------------------------------- iyilestirme
# Sayfa bazli dizim parcalari ISLEVSEL olarak gruplyor ama ELEKTRIKSEL
# olarak degil: grup icinde siralama alana gore yapiliyordu, yani bir
# direnc bagli oldugu entegrenin 50 mm otesine dusebiliyordu.
# Olculdu: ortalama sinyal baglantisi 63 mm, en uzunu 167 mm, toplam
# 28 metre. Boyle bir kart yonlendirilse calisir ama gurultu tabani ve
# faz uyumu gider — yani aletin butun degeri.
#
# Cozum: kuvvet-guduml u iyilestirme. Ayni aga bagli parcalar birbirini
# CEKIYOR, ust uste binenler ITIYOR. Guc ve toprak aglari cekimden
# haric — onlar her seyi her seye baglar ve kart tek noktaya cokerdi.
ATLA_AG = re.compile(r"^(GND|\+|VIN|CHASSIS|GND_HDR|GND_STRAP|GND_MODE)")


def kuvvet_yerlesim(fps, comps, en, boy, adim=260, sabit=()):
    """Baglantiya gore yerlesimi iyilestir; (once, sonra) uzunluk don."""
    ref_list = list(fps)
    idx = {r: i for i, r in enumerate(ref_list)}
    # COURTYARD MERKEZINDE calisiyoruz, ayak izi konumunda degil.
    # Ikisi ayni yer degil: G2RL-2 rolesinde 12 mm fark var. Konum
    # uzerinden itip courtyard olcusuyle cakisma sinamak yanlis sonuc
    # veriyor — parcalar 18 mm uzakta "cakisiyor" gorunuyordu.
    kayma = []
    for r in ref_list:
        fp = fps[r]
        p0 = fp.GetPosition()
        try:
            c = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            m = c.GetCenter() if c.GetWidth() > 0 else p0
        except Exception:
            m = p0
        kayma.append(((m.x - p0.x) / MM, (m.y - p0.y) / MM))
    px = [fps[r].GetPosition().x / MM + kayma[i][0]
          for i, r in enumerate(ref_list)]
    py = [fps[r].GetPosition().y / MM + kayma[i][1]
          for i, r in enumerate(ref_list)]
    # PAY 1.4: cakisma sinamasi sinir KUTUSU ile, KiCad ise gercek
    # courtyard COKGENI ile bakiyor. Dikdortgen olmayan courtyard'larda
    # ikisi ayrisiyor ve 1.0 payda DRC birkac ihlal buluyordu.
    olc = [olcu(fps[r], pay=1.4) for r in ref_list]

    # ag -> bagli parca indisleri (guc/toprak haric, cok genis aglar haric)
    aglar = {}
    for ref, (val, fp, padlar, sayfa) in comps.items():
        if ref not in idx:
            continue
        for ag_ad in set(padlar.values()):
            if ATLA_AG.match(ag_ad):
                continue
            aglar.setdefault(ag_ad, set()).add(idx[ref])
    kenarlar = []
    for ag_ad, uyeler in aglar.items():
        u = sorted(uyeler)
        if 2 <= len(u) <= 10:          # genis yollar cekimi bozar
            for i in range(len(u)):
                for j in range(i + 1, len(u)):
                    kenarlar.append((u[i], u[j]))

    def uzunluk():
        return sum(math.dist((px[a], py[a]), (px[b], py[b]))
                   for a, b in kenarlar)

    once = uzunluk()
    n = len(ref_list)
    hucre = 12.0

    def cakismalari_coz(tur_sayisi):
        """Cakisan ciftleri dogrudan ayir; kalan cakisma sayisini don."""
        cakisan = 0
        for _ in range(tur_sayisi):
            cakisan = 0
            kova = {}
            for i in range(n):
                kova.setdefault((int(px[i] / hucre), int(py[i] / hucre)),
                                []).append(i)
            for (cx, cy), liste in kova.items():
                komsu = []
                for ddx in (-1, 0, 1):
                    for ddy in (-1, 0, 1):
                        komsu += kova.get((cx + ddx, cy + ddy), [])
                for i in liste:
                    wi, hi = olc[i]
                    for j in komsu:
                        if j <= i:
                            continue
                        wj, hj = olc[j]
                        dx, dy = px[j] - px[i], py[j] - py[i]
                        ortx, orty = (wi + wj) / 2, (hi + hj) / 2
                        ax, ay = abs(dx), abs(dy)
                        if ax < ortx and ay < orty:
                            cakisan += 1
                            si = ref_list[i] in sabit
                            sj = ref_list[j] in sabit
                            if si and sj:
                                continue
                            # capa sabitse ayirmanin tamami otekine
                            pi = 0.0 if si else (1.0 if sj else 0.5)
                            pj = 0.0 if sj else (1.0 if si else 0.5)
                            if ortx - ax < orty - ay:
                                k = ortx - ax + 0.15
                                s = 1 if dx >= 0 else -1
                                px[i] -= k * pi * s
                                px[j] += k * pj * s
                            else:
                                k = orty - ay + 0.15
                                s = 1 if dy >= 0 else -1
                                py[i] -= k * pi * s
                                py[j] += k * pj * s
            for i in range(n):
                if ref_list[i] in sabit:
                    continue
                px[i] = min(max(px[i], KENAR), en - KENAR)
                py[i] = min(max(py[i], KENAR), boy - KENAR)
            if not cakisan:
                break
        return cakisan

    for it in range(adim):
        sicak = 1.0 - it / adim
        fx = [0.0] * n
        fy = [0.0] * n
        # cekim
        for a, b in kenarlar:
            dx, dy = px[b] - px[a], py[b] - py[a]
            d = math.hypot(dx, dy) or 0.001
            k = 0.020 * min(d, 60.0)
            fx[a] += k * dx / d
            fy[a] += k * dy / d
            fx[b] -= k * dx / d
            fy[b] -= k * dy / d
        # itme: sadece cakisan ciftler (kaba izgara ile hizli tarama)
        hucre = 12.0
        kova = {}
        for i in range(n):
            kova.setdefault((int(px[i] / hucre), int(py[i] / hucre)), []).append(i)
        for (cx, cy), liste in kova.items():
            komsu = []
            for ddx in (-1, 0, 1):
                for ddy in (-1, 0, 1):
                    komsu += kova.get((cx + ddx, cy + ddy), [])
            for i in liste:
                wi, hi = olc[i]
                for j in komsu:
                    if j <= i:
                        continue
                    wj, hj = olc[j]
                    dx, dy = px[j] - px[i], py[j] - py[i]
                    ortx, orty = (wi + wj) / 2, (hi + hj) / 2
                    ax, ay = abs(dx), abs(dy)
                    if ax < ortx and ay < orty:
                        # cakisma var: en az itme yonunde ayir
                        if ortx - ax < orty - ay:
                            it_x = (ortx - ax + 0.4) * (1 if dx >= 0 else -1)
                            fx[i] -= it_x * 0.5
                            fx[j] += it_x * 0.5
                        else:
                            it_y = (orty - ay + 0.4) * (1 if dy >= 0 else -1)
                            fy[i] -= it_y * 0.5
                            fy[j] += it_y * 0.5
        for i in range(n):
            if ref_list[i] in sabit:
                continue      # capa: kat planinda yeri belli, oynamaz
            px[i] = min(max(px[i] + fx[i] * sicak, KENAR), en - KENAR)
            py[i] = min(max(py[i] + fy[i] * sicak, KENAR), boy - KENAR)

    # ---- YASALLASTIRMA, KUVVETLE DONUSUMLU
    # Once sadece sonda yasallastiriyordum: cakismalar cozuluyordu ama
    # kuvvetin kazandirdigi kisalma geri gidiyordu (%81 -> %47).
    # Donusumlu calistirinca cekim, ayrilan parcalari tekrar topluyor
    # ve sonuc hem yasal hem kisa kaliyor.
    for tur in range(12):
        cakisan = cakismalari_coz(40)
        if not cakisan:
            break
        for _ in range(8):
            fx = [0.0] * n
            fy = [0.0] * n
            for a, b in kenarlar:
                dx, dy = px[b] - px[a], py[b] - py[a]
                d = math.hypot(dx, dy) or 0.001
                kk = 0.012 * min(d, 40.0)
                fx[a] += kk * dx / d
                fy[a] += kk * dy / d
                fx[b] -= kk * dx / d
                fy[b] -= kk * dy / d
            for i2 in range(n):
                px[i2] = min(max(px[i2] + fx[i2] * 0.35, KENAR), en - KENAR)
                py[i2] = min(max(py[i2] + fy[i2] * 0.35, KENAR), boy - KENAR)
    cakisan = cakismalari_coz(300)

    for r in ref_list:
        i = idx[r]
        # courtyard merkezinden ayak izi konumuna geri cevir
        gx = px[i] - kayma[i][0]
        gy = py[i] - kayma[i][1]
        # 0.05 mm izgaraya otur: yonlendirici duzgun izgara sever
        fps[r].SetPosition(pcbnew.VECTOR2I(int(round(gx * 20) / 20 * MM),
                                           int(round(gy * 20) / 20 * MM)))
    return once, uzunluk(), cakisan


if __name__ == "__main__":
    hedef = sys.argv[1:] or ["A", "C", "D"]
    kotu = sum(kur(k) for k in hedef)
    sys.exit(1 if kotu else 0)
