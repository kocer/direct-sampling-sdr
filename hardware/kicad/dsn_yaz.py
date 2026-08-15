#!/usr/bin/env python3
"""KiCad PCB -> Specctra DSN.

    python3 dsn_yaz.py A_main/dogrudan_sdr_A.kicad_pcb /tmp/A.dsn

NEDEN KENDIMIZ YAZIYORUZ: pcbnew'un ExportSpecctraDSN'i kendi kart
baglamini GUI'den aliyor; bagimsiz python'da GetBoard() None donuyor
ve fonksiyon sessizce False veriyor. Yonlendirici (freerouting) DSN
istiyor, biz de DSN uretiyoruz.

DSN'in iki tuzagi:
  1 Y EKSENI TERS. KiCad'de y asagi artiyor, DSN'de yukari. Cevirmeyi
    unutursan kart aynalanir ve yonlendirme geri alindiginda her sey
    ters yerde olur.
  2 Padstack'ler GLOBAL. Ayni olculu pedler tek padstack paylasmali,
    yoksa dosya sisiyor ve bazi yonlendiriciler bogluyor.
"""
import os, re, sys
import pcbnew

UM = 1000.0        # pcbnew nm -> um


def q(s):
    """DSN tanimlayicisi: bosluk ve ozel karakter varsa tirnakla."""
    s = str(s)
    return f'"{s}"' if re.search(r'[\s()"]', s) or s == "" else s


def ped_adlari(fp):
    """Ayak izinin pedlerine BENZERSIZ ad ver, ped sirasina gore.

    NEDEN: kenar montaj SMA'sinin dort toprak pedi de "2" numarali.
    DSN'e dordunu de "2" diye yazinca yonlendirici bir tanesini
    kaydediyor, otekilerin orada oldugunu HIC bilmiyor ve uzerlerinden
    yol cekiyor. D kartinda J20'nin cevresindeki bes kisa devre, uc
    clearance ve uc hole_clearance ihlalinin tamami buydu.

    Cakisan numaralara sirayla "2@1", "2@2" ekleniyor. Kutuphane ve
    ag bolumleri AYNI fonksiyondan geciyor ki isimler tutsun. SES'i
    geri okurken ped adi kullanilmiyor (eslesme ag adindan), o yuzden
    bu takma adlar disari sizmiyor.
    """
    sayac = {}
    out = []
    for pad in fp.Pads():
        num = pad.GetNumber() or "NC"
        k = sayac.get(num, 0)
        sayac[num] = k + 1
        out.append(num if k == 0 else f"{num}@{k}")
    return out


class Yazici:
    def __init__(self, board):
        self.b = board
        self.padstack = {}      # anahtar -> ad
        self.ps_tanim = []

    # ---------------------------------------------------------- yardimci
    def xy(self, v):
        """KiCad VECTOR2I -> DSN (um). Y ISARETI TERS."""
        return v.x / UM, -v.y / UM

    def katmanlar(self):
        """Bakir katmanlarin adlari, USTTEN ALTA.

        KATMAN NUMARALARI KICAD 9'DA DEGISTI. Eskiden F_Cu=0,
        In1_Cu=1, In2_Cu=2 ... ardisiktı; artik bakir katmanlar CIFT
        sayilar: F.Cu=0, B.Cu=2, In1.Cu=4, In2.Cu=6, In3.Cu=8.

        Ben "In1_Cu + i - 1" diye sayiyordum. Alti katmanli kartta bu
        4 gercek bakir katman + F.Silkscreen + B.Silkscreen veriyordu:
        yonlendirici ipek baski katmanina iz cekiyor, kart iki katman
        eksik yonlendiriliyordu. SES geri okunurken o izler ipek
        katmanina dusuyor, yani hic bakir olmuyorlardi.

        CuStack() dogru sirayi kendi veriyor; elle saymak yok.
        """
        return [pcbnew.LayerName(i)
                for i in self.b.GetEnabledLayers().CuStack()]

    def ps_ad(self, pad, katmanlar):
        """Bir pedin padstack adini don, gerekirse tanimla."""
        sekil = pad.GetShape()
        w = pad.GetSizeX() / UM
        h = pad.GetSizeY() / UM
        delik = pad.GetDrillSizeX() / UM if pad.GetAttribute() in (
            pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else 0
        tht = delik > 0
        # PEDIN GERCEK KATMANI. Once butun SMD pedleri ust katmana
        # yazmistim; alt yuzeydeki pedler (kenar montaj SMA gibi)
        # yonlendiriciye "alt katman bos" gorundu ve uzerlerinden
        # baska aglarin izleri gecti — DRC'de kisa devre olarak cikti.
        if tht:
            hedef = katmanlar
        elif pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu):
            hedef = [katmanlar[-1]]
        else:
            hedef = [katmanlar[0]]
        anahtar = (sekil, round(w, 1), round(h, 1), round(delik, 1),
                   tht, tuple(hedef))
        if anahtar in self.padstack:
            return self.padstack[anahtar]
        ad = f"ps{len(self.padstack)}"
        self.padstack[anahtar] = ad
        satir = [f"    (padstack {q(ad)}"]
        for lay in hedef:
            if sekil == pcbnew.PAD_SHAPE_CIRCLE:
                satir.append(f"      (shape (circle {q(lay)} {w:.1f}))")
            elif sekil == pcbnew.PAD_SHAPE_OVAL:
                satir.append(f"      (shape (path {q(lay)} {min(w, h):.1f} "
                             f"{-(w - h) / 2 if w > h else 0:.1f} "
                             f"{0 if w > h else -(h - w) / 2:.1f} "
                             f"{(w - h) / 2 if w > h else 0:.1f} "
                             f"{0 if w > h else (h - w) / 2:.1f}))")
            else:
                satir.append(f"      (shape (rect {q(lay)} {-w / 2:.1f} "
                             f"{-h / 2:.1f} {w / 2:.1f} {h / 2:.1f}))")
        satir.append("      (attach off))")
        self.ps_tanim.append("\n".join(satir))
        return ad

    # ---------------------------------------------------------- bolumler
    def yapi(self, katmanlar):
        # DUZLEM KATMANLARI "power" TIPINDE. Alti katmanin hepsini
        # signal diye verince yonlendirici toprak duzlemlerinin
        # uzerine sinyal cekti: A kartinda 37 kisa devre, 40 maske
        # koprusu ve 430 bagsiz ag cikti. Uzerinde dokum olan katman
        # yonlendiriciye kapali olmali; oradan gecis sadece via ile.
        duzlem = {pcbnew.LayerName(z.GetLayer()) for z in self.b.Zones()}
        # IKI KATMANLI KARTTA DUZLEM ISARETLENMEZ. C ve D'nin dokumu
        # F.Cu ve B.Cu'da, yani TEK katmanlari. Ikisini de power
        # ilan edince yonlendiriciye sinyal katmani kalmiyor ve
        # 1 saniyede pes ediyor. Iki katmanli kartta dokumun uzerine
        # yonlendirmek tasarimin kendisi; KiCad doldururken her izin
        # etrafini aciyor.
        if len(katmanlar) - len(duzlem) < 2:
            duzlem = set()
        o = ["  (structure"]
        for i, lay in enumerate(katmanlar):
            tip = "power" if lay in duzlem else "signal"
            o.append(f"    (layer {q(lay)} (type {tip}) "
                     f"(property (index {i})))")
        # sinir: Edge.Cuts kenarlarindan
        pts = []
        for d in self.b.GetDrawings():
            if d.GetLayer() == pcbnew.Edge_Cuts and \
               d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                pts.append((self.xy(d.GetStart()), self.xy(d.GetEnd())))
        if pts:
            xs = [p[0] for s in pts for p in s]
            ys = [p[1] for s in pts for p in s]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            # SINIRI ICERI CEK. Yonlendirici sinira kadar bakir
            # koyuyor; kart kenarina 0.1 mm kalan izler cikti. Kenari
            # kesen frezenin toleransi +-0.15 mm — o iz kesilir ya da
            # bakiri kartin yan yuzunde aciga cikar. Sinir 0.5 mm
            # iceri alininca yonlendirilen hicbir bakir o kusaga
            # giremiyor. Pedler PED_ICERI=0.6 ile zaten daha iceride,
            # yani erisilebilir kaliyorlar.
            ic = 500.0      # um -> 0.5 mm
            x0, y0 = x0 + ic, y0 + ic
            x1, y1 = x1 - ic, y1 - ic
            o.append(f"    (boundary (path pcb 0 {x0:.0f} {y0:.0f} "
                     f"{x1:.0f} {y0:.0f} {x1:.0f} {y1:.0f} "
                     f"{x0:.0f} {y1:.0f} {x0:.0f} {y0:.0f}))")
        ds = self.b.GetDesignSettings()
        o.append('    (via "via_default")')
        o.append(f"    (rule (width 200) (clearance 200)"
                 f" (clearance 100 (type smd_smd)))")
        o.append("  )")
        return "\n".join(o)

    def yerlesim(self):
        gruplar = {}
        for fp in self.b.Footprints():
            gruplar.setdefault(str(fp.GetFPID().GetLibItemName()), []).append(fp)
        o = ["  (placement"]
        for ad, fps in sorted(gruplar.items()):
            o.append(f"    (component {q(ad)}")
            for fp in fps:
                x, y = self.xy(fp.GetPosition())
                yuz = "front" if fp.GetLayer() == pcbnew.F_Cu else "back"
                aci = fp.GetOrientationDegrees() % 360
                o.append(f"      (place {q(fp.GetReference())} {x:.0f} {y:.0f}"
                         f" {yuz} {aci:.0f} (PN {q(fp.GetValue())}))")
            o.append("    )")
        o.append("  )")
        return "\n".join(o)

    def kutuphane(self, katmanlar):
        gorulen = {}
        for fp in self.b.Footprints():
            ad = str(fp.GetFPID().GetLibItemName())
            if ad in gorulen:
                continue
            gorulen[ad] = fp
        o = ["  (library"]
        for ad, fp in sorted(gorulen.items()):
            o.append(f"    (image {q(ad)}")
            fpx, fpy = fp.GetPosition().x, fp.GetPosition().y
            aci = fp.GetOrientation().AsRadians()
            import math
            adlar = ped_adlari(fp)
            for pad, pad_ad in zip(fp.Pads(), adlar):
                ps = self.ps_ad(pad, katmanlar)
                # ped konumu ayak izi ORIJININE gore, donme geri alinmis
                dx = (pad.GetPosition().x - fpx) / UM
                dy = -(pad.GetPosition().y - fpy) / UM
                ca, sa = math.cos(-aci), math.sin(-aci)
                rx = dx * ca - dy * sa
                ry = dx * sa + dy * ca
                o.append(f"      (pin {q(ps)} {q(pad_ad)}"
                         f" {rx:.0f} {ry:.0f})")
            o.append("    )")
        o.extend(self.ps_tanim)
        # gecis padstack'i
        o.append('    (padstack "via_default"')
        for lay in katmanlar:
            o.append(f"      (shape (circle {q(lay)} 600))")
        o.append("      (attach off))")
        o.append("  )")
        return "\n".join(o)

    # AG SINIFLARI: her ag ayni genislikte olamaz.
    # Tek bir varsayilan (200 um) yaziyordum ve yonlendirici 50 V
    # rayini da 0.2 mm cekti. A sinifi 100 W'ta o raydan 6.67 A
    # geciyor; IPC-2221'e gore 1 oz dis katmanda 20 C artis icin
    # ~4 mm gerekiyor. 0.2 mm o akimda sigorta gibi davranir.
    #
    # RF genisligi katman yiginina bagli. Iki katmanli kartta 1.6 mm
    # FR4 uzerinde 50 ohm mikroserit ~2.9 mm; alti katmanli kartta
    # ic dielektrik 0.2 mm oldugu icin ~0.35 mm.
    GUC = ("+50V", "+12V", "DRN_CT", "DRN_A", "DRN_B", "D2_CT",
           "PA_OUT", "PA_LPF_OUT", "ANT_OUT", "+5V", "+3V3")
    RF_ONEK = ("LPF_", "RX", "TX", "ANT", "PA_", "F1", "N1")

    def ag_sinifi(self, ad, iki_katman):
        """Agin genisligi (um) — yuke ve RF'e gore."""
        if ad in ("+50V", "DRN_CT", "DRN_A", "DRN_B"):
            # 2 oz BAKIR, 4 mm DEGIL 2.2 mm.
            # 1 oz'da 6.67 A icin 4 mm gerekiyor ve iki katmanli
            # kalabalik kartta o genislikte iz yol bulamiyor —
            # yonlendirici yarim saat calisip bitiremedi. Cozum izi
            # inceltmek degil, bakiri kalinlastirmak: D karti 2 oz
            # dis katman siparis edilecek (JLCPCB standart secenek,
            # 100 W'lik bir amfide zaten dogru tercih). 2 oz'da ayni
            # akim ayni sicaklik artisiyla 2.2 mm istiyor.
            return 2200          # 6.67 A @ 2 oz
        if ad in ("+12V", "D2_CT"):
            return 1500          # surucu, ~1 A
        if ad in ("+5V", "+3V3") and iki_katman:
            # IKI KATMANLI KARTTA DAHA INCE. D kartinda bu raylar
            # detektorleri ve regulatorleri besliyor, dal basina
            # 100-200 mA. 0.8 mm iki katmanli kalabalik kartta yol
            # bulamadi (16 + 6 bagsiz ag). 0.5 mm 1 oz'da 1.3 A
            # tasiyor, fazlasiyla yeterli.
            return 500
        if ad in ("+5V", "+3V3"):
            # 0.8 mm YAZMISTIM, GEREKSIZ GENIS.
            # Bu raylar entegre besliyor, guc kati degil. Ray toplamda
            # ~2 A tasiyor ama DAGITILMIS: her dal kendi entegresinin
            # akimini goruyor, tipik 100-300 mA. 0.4 mm bunun kat kat
            # ustunde (1 oz'da ~1.1 A).
            # Bedeli agirdi: A kartinda sadece 4 sinyal katmani var
            # (6 bakirin ikisi toprak duzlemi) ve 0.8 mm'lik besleme
            # agi yolu tikadi — yonlendirici 96 dakikada bitiremedi,
            # onceki turda 8 dakikada bitiriyordu.
            return 400
        if ad.startswith(self.RF_ONEK) or ad in ("PA_OUT", "PA_LPF_OUT",
                                                 "ANT_OUT"):
            # IKI KATMANLI KARTTA EMPEDANS DEGIL AKIM BELIRLIYOR.
            # Once 2.9 mm yazmistim: 1.6 mm FR4 uzerinde 50 ohm
            # mikroseridin genisligi bu. Dogru ama gereksiz — HF'te
            # 100 mm'lik bir iz dalga boyunun 0.02'si, empedans
            # kontrolu anlam tasimiyor. Ustelik kalabalik iki
            # katmanli kartta sigmiyor: yonlendirici 1.2 saniyede
            # pes etti ve sifir iz uretti.
            # Belirleyen akim: 100 W / 50 ohm = 1.4 A. 1.5 mm bol.
            # Alti katmanli kartta durum farkli — orada ADC girisi
            # ve saat var, ince dielektrik uzerinde 0.35 mm ile
            # gercekten 50 ohm tutuyor.
            return 1500 if iki_katman else 350
        return 250

    def ag(self):
        aglar = {}
        for fp in self.b.Footprints():
            adlar = ped_adlari(fp)
            for pad, pad_ad in zip(fp.Pads(), adlar):
                n = pad.GetNetname()
                if n and pad.GetNumber():
                    aglar.setdefault(n, []).append(
                        f"{fp.GetReference()}-{pad_ad}")
        # TOPRAK YINE YONLENDIRILIYOR — ONCEKI GEREKCE YANLISTI.
        #
        # GND'yi ag listesinden cikarmistim: "429 ince iz dokumu
        # yariyor" diye. Yanlis. AYNI AGIN izi dokumu KESMEZ; KiCad
        # dokumu ayni ag bakiriyla birlestiriyor. Dokumu parcalayan
        # sey BASKA aglarin izleri.
        #
        # Ustelik cikarmanin bedeli agirdi: ag listesinde olmayan
        # pedler yonlendiriciye gorunmuyor. J20'nin dort toprak pedi
        # DSN'e hic girmedi ve router uzerlerinden RLY_RCLK,
        # RLY_SER_OUT gecirdi — dort kisa devre, dokuz maske koprusu.
        #
        # Dikis via'lari yine gerekli: onlar ust ve alt dokumu
        # birbirine bagliyor, ki bu ayri bir is.
        DOKUM_AG = set()
        # (eski kod, kayit icin)
        # TOPRAK YONLENDIRILMEZ, DOKUM TASIR.
        # Yonlendirici GND'yi normal ag sanip D kartinda 429 tane
        # 0.25 mm iz cekti. PA'nin donus akimi 6.67 A; o izden gecse
        # buharlasir. Gercekte akim dokumde akiyor, ama her iz
        # dokumu YARIYOR — parcalanan dokumde donus yolu uzuyor ve
        # inceliyor, yani izler yardim etmek yerine zarar veriyor.
        # Pedler kutuphanede duruyor, yani yonlendirici onlarin
        # yerini biliyor ve uzerlerinden gecmiyor; sadece "bu agi
        # bagla" gorevi verilmiyor. Baglantiyi KiCad dokumu
        # doldururken kuruyor.
        # DOKUM AGLARI KARTTAN TURETILIYOR, ELLE YAZILMIYOR.
        # Once {"GND","GND_HDR","GNDA","AGND"} diye sabit liste
        # yazmistim. GND_HDR'in dokumu YOK — konnektor topragi, GND'ye
        # tek bir 0R uzerinden bagli. Yonlendirmeden cikarinca pedleri
        # bosta kaldi (22 bagsiz). Bir agi yonlendirmemek ancak onu
        # tasiyacak bir dokum varsa dogru.
        # DOKUM_AG = {z.GetNetname() for z in self.b.Zones()}
        o = ["  (network"]
        for n, pins in sorted(aglar.items()):
            if len(pins) < 2 or n in DOKUM_AG:
                continue
            o.append(f"    (net {q(n)}")
            o.append("      (pins " + " ".join(q(p) for p in pins) + "))")
        # AGLARI GENISLIGE GORE GRUPLA, HER GRUP AYRI SINIF.
        # Tek bir varsayilan sinif yaziyordum ve yonlendirici her seyi
        # 0.2 mm cekti — 50 V rayi ve drain beslemesi dahil. A sinifi
        # 100 W'ta o raydan 6.67 A geciyor.
        iki = self.b.GetCopperLayerCount() <= 2
        grup = {}
        for n in sorted(aglar):
            if len(aglar[n]) < 2:
                continue
            if n in DOKUM_AG:
                continue
            grup.setdefault(self.ag_sinifi(n, iki), []).append(n)
        for w, netler in sorted(grup.items()):
            o.append(f"    (class sinif{w} " + " ".join(q(x) for x in netler))
            o.append("      (circuit (use_via via_default))")
            # BOSLUK GENISLIKLE OLCEKLENMEZ. max(200, w*0.35) yazmistim:
            # 4 mm'lik guc izi 1.4 mm boslugu zorunlu kildi ve
            # yonlendirici 1 saniyede pes etti. Boslugun sebebi
            # uretim ve delinme dayanimi, izin kendi genisligi degil.
            # 50 V'ta 0.3 mm zaten fazlasiyla yeterli (IPC-2221 ic
            # katman B2 sinifi: 50 V icin 0.13 mm).
            o.append(f"      (rule (width {w}) (clearance 300))")
            o.append("    )")
        o.append("  )")
        return "\n".join(o)

    def tel(self, katmanlar):
        """Kartta ZATEN VAR OLAN izleri korumali tel olarak yaz.

        elle_cek.py simetrik aglari elle cekiyor: dort kapi 14.5 mm,
        iki kol 72.5 mm. Yonlendiriciye bunlari soylemezsek hepsini
        sokup kendi bildigini cekiyor ve simetri gidiyor — daha once
        kapilar 66.7 / 80.1 / 95.4 / 123.4 mm cikmisti.

        `(type protect)` = "buna dokunma". Yonlendirici kalan aglari
        bu izlerin etrafindan dolastiriyor.
        """
        o = ["  (wiring"]
        n = 0
        for tr in self.b.GetTracks():
            ag = tr.GetNetname()
            if not ag or isinstance(tr, pcbnew.PCB_VIA):
                continue
            lay = pcbnew.LayerName(tr.GetLayer())
            if lay not in katmanlar:
                continue
            a, c = tr.GetStart(), tr.GetEnd()
            x1, y1 = self.xy(a)
            x2, y2 = self.xy(c)
            o.append(f"    (wire (path {q(lay)} {tr.GetWidth() / UM:.0f} "
                     f"{x1:.0f} {y1:.0f} {x2:.0f} {y2:.0f})")
            o.append(f"      (net {q(ag)})(type fix))")
            n += 1
        o.append("  )")
        self.korunan = n
        return "\n".join(o)

    def yaz(self, yol):
        katmanlar = self.katmanlar()
        govde = [
            f"(pcb {q(os.path.basename(yol).replace('.dsn', ''))}",
            "  (parser (string_quote \")(space_in_quoted_tokens on)"
            "(host_cad \"KiCad\")(host_version \"10.0\"))",
            "  (resolution um 10)",
            "  (unit um)",
        ]
        govde.append(self.yapi(katmanlar))
        govde.append(self.yerlesim())
        govde.append(self.kutuphane(katmanlar))
        govde.append(self.ag())
        # ELLE CEKILEN IZLER YONLENDIRICIYE VERILIYOR.
        # Ice alirken korumak yetmedi: router o aglari bilmedigi icin
        # uzerlerinden gecti ve 44 kisa devre cikti. Simetriyi
        # korumanin tek dogru yolu izi ONA soylemek.
        # `protect` kabul edilmedi (1.3 saniyede pes etti);
        # Specctra'nin `fix` tipi deneniyor.
        govde.append(self.tel(katmanlar))
        govde.append(")")
        open(yol, "w", encoding="utf-8").write("\n".join(govde) + "\n")
        return len(katmanlar)


if __name__ == "__main__":
    pcb, dsn = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(pcb)
    y = Yazici(b)
    n = y.yaz(dsn)
    print(f"{os.path.basename(dsn)}: {getattr(y, 'korunan', 0)} korumali iz, "
          f"{n} katman, "
          f"{len(list(b.Footprints()))} parca, "
          f"{len(y.padstack)} padstack, {os.path.getsize(dsn) // 1024} KB")
