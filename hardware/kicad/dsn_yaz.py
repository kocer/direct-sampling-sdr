#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
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
# Yonlendiricinin kullandigi gecis capi (um). ses_oku ayni
# degeri kullaniyor; ikisi ayrisirsa ice alinan via DSN'de
# planlanandan buyuk olur ve boslu ihlali cikar.
VIA_CAP = 500
VIA_DELIK = 300


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


def parmak(board):
    """Yerlesimin parmak izi — SES ile kartin ayni karta ait oldugunu sinar.

    BIR SES DOSYASI TEK BIR YERLESIME AITTIR. yap.sh ice alirken karti
    netlistten yeniden kuruyor (dikis via'lari birikmesin diye). O
    yeniden kurulum, DSN'in uretildigi yerlesimle birebir ayni degilse
    yonlendiricinin izleri artik baska pedlere denk geliyor: bilinen
    sonucu 45 kisa devre, ve hicbir yerde uyari cikmiyor.

    Zinciri tekrarlanabilir yaptik (sirali dolasim + sabit karma
    tohumu), ama "yaptik" yetmez — tekrarlanabilirligin BOZULDUGUNU
    haber verecek bir sey lazim. Kod degistikce bu garanti sessizce
    kaybolabilir; parmak izi kaybolduğu anda bagirir.

    Parmak izi PARCALARIN KONUMU: referans, konum, aci, yuz. Iz ya da
    via girmiyor — onlar zaten yonlendirmeyle degisiyor.
    """
    import hashlib
    h = hashlib.sha256()
    for fp in sorted(board.Footprints(), key=lambda f: f.GetReference()):
        p = fp.GetPosition()
        h.update(f"{fp.GetReference()}|{p.x}|{p.y}|"
                 f"{fp.GetOrientationDegrees():.1f}|{fp.GetLayer()}\n"
                 .encode())
    return h.hexdigest()


def akim_gereksinimi(board):
    """{ag: amper} — besleme yolunu SERI PARCALARDAN gecerek yay.

    NEDEN TABLO YETMIYOR: ag_sinifi() genisligi agin ADINDAN
    seciyor. Ama bir besleme yolu tek bir ag degil; konnektorden
    regulatore giderken sigortadan, ters polarite MOSFET'inden,
    bobinden geciyor ve HER GECISTE AD DEGISIYOR. Ara adlarin cogu
    KiCad'in otomatik urettikleri — "Net-(Q1-S)" gibi. Tablo onlari
    tanimaz, varsayilan 250 um'e duserler.

    AYNI HATAYA IKI KEZ DUSULDU:
      D karti  VIN50, +50V ile ayni 6.67 A'i tasiyor, tabloda yoktu.
      A karti  J1 -> Net-(J1-Pin_1) -> Q1 -> Net-(Q1-S) -> F1 ->
               VIN_PROT. VIN_PROT'a 800 um verildi ama ONDAN ONCEKI
               iki ag ayni akimi tasiyip 250 um'de kaldi.

    Ucuncusunu beklemek yerine gereksinimi TURETIYORUZ: guc_yolu.py
    zaten seri parcalari (sigorta, bobin, ferrit, dusuk degerli
    direnc, MOSFET'in drain-source'u) buluyor. Kaynak aglardan
    baslayip o kenarlardan yayiyoruz. Boylece kartta yeni bir
    sigorta ya da bobin belirdiginde kimsenin bu dosyayi
    guncellemesi gerekmiyor.
    """
    import collections
    try:
        import guc_yolu
    except Exception:
        return {}
    ad = os.path.basename(board.GetFileName() or "")
    kart = next((k for k in ("A", "C", "D") if f"_{k}." in ad), None)
    if kart is None:
        return {}
    kaynak = guc_yolu.KAYNAK.get(kart, {})
    kenar = guc_yolu.seri_baglantilar(board)
    gerek = dict(kaynak)
    kuyruk = collections.deque((n, n) for n in kaynak)
    while kuyruk:
        ag, kok = kuyruk.popleft()
        for komsu, _ref in kenar.get(ag, []):
            yeni = gerek[kok]
            if gerek.get(komsu, 0) >= yeni:
                continue
            gerek[komsu] = yeni
            kuyruk.append((komsu, kok))
    return gerek


# D KARTINDA FINALDEN SONRAKI AGLAR — 100 W tasiyanlar.
# Liste acik yazili cunku "hangi ag guc tasiyor" bilgisi ag adinda
# yok. Finalin cikis trafosundan (T31) antene kadar olan yol:
#   PA_OUT -> R500 -> LPF bankasi -> R501 -> PA_LPF_OUT -> T20 -> ANT_OUT
# LPF bankasinin ic dugumleri (LPF_B*, LF*, N*) asagida desenle
# yakalaniyor. DPD_OUT bu yolun -30 dB'lik ornegi, milivat: burada
# YOK, bilerek.
D_YUKSEK_GUC = {"PA_OUT", "PA_LPF_OUT", "ANT_OUT",
                "DRN_A", "DRN_B", "DRN_CT"}

# Finalden ONCEKI RF zinciri — milivattan 8 W'a. Adlari desene
# uymuyor ama TX_IN ile ayni hattin devami; ayni genislikte
# olmalilar. (TX_IN 1500, ATT_OUT 250 idi: ayni sinyalde alti kat
# sicrama, ve 1500'luk ucu PE4312'nin 0.25 mm'lik pedine giremedi.)
D_ORTA_GUC = {"ATT_OUT", "D1_IN", "D1_OUT", "D2_IN", "DRV_OUT",
              "DPD_OUT", "PGA_BIAS"}


class Yazici:
    def __init__(self, board):
        self.b = board
        self.padstack = {}      # anahtar -> ad
        self.ps_tanim = []
        # KART KIMLIGI. Genislik ve boslu kurallari karta gore
        # degisiyor: D'nin bir kismi 100 W tasiyor, C'nin hicbir
        # yeri tasimiyor, A'da 0.8 mm adimli BGA var. "Iki katmanli
        # mi" bayragi bu ayrimlari yapamiyor.
        _ad = os.path.basename(board.GetFileName() or "")
        self.kart = next((k for k in ("A", "C", "D") if f"_{k}." in _ad), None)
        # 2 oz sadece D'de: 100 W'lik amfide dis katman kalinlastirildi.
        self.oz = 2 if self.kart == "D" else 1
        self.akim = akim_gereksinimi(board)

    # ---------------------------------------------------------- yardimci
    def sirali(self):
        """Ayak izleri referansa gore sirali — kart ici sira UUID'lere bagli."""
        return sorted(self.b.Footprints(), key=lambda f: f.GetReference())

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

    def ps_ad(self, pad, katmanlar, fp=None):
        """Bir pedin padstack adini don, gerekirse tanimla.

        PEDIN KENDI DONMESI SAYILIR. GetSizeX/GetSizeY pedin KENDI
        cercevesindeki olcu; ayak izi icinde 90 derece dondurulmus bir
        ped bu sayilarla yazilinca DSN'de ENINE BOYUNA TAKAS EDILMIS
        bir engel oluyor. Specctra padstack'i donme tasimiyor, o
        yuzden olcuyu burada cevirmek zorundayiz.

        Olculdu (D karti): SMA_Amphenol_132289_EdgeMount'un launch
        pedi gercekte 5.08 x 1.5 mm YATAY; DSN'e 1.5 x 5.08 DIKEY
        yaziliyordu. Yonlendirici pedin gercek govdesini bos sandi ve
        J10'un TX_IN pedinin ustunden GND izi gecirdi — kisa devre,
        ve DRC'de "shorting_items" olarak cikti. Ayni ayak izi
        A'da 45, C'de 60, D'de 10 pedle kullaniliyor; hepsi RF
        konnektoru, yani kartin en kritik pedleri.
        """
        sekil = pad.GetShape()
        w = pad.GetSizeX() / UM
        h = pad.GetSizeY() / UM
        # pedin AYAK IZINE gore acisi (mutlak aci degil)
        yerel = 0.0
        if fp is not None:
            yerel = (pad.GetOrientationDegrees()
                     - fp.GetOrientationDegrees()) % 180.0
        if 45.0 <= yerel < 135.0:
            w, h = h, w
        elif yerel > 1.0:
            # 90'in kati olmayan aci: eksene hizali SINIR KUTUSU.
            # Biraz genis, ama fazla engel kisa devreden iyidir.
            import math as _m
            r = _m.radians(yerel)
            w, h = (abs(w * _m.cos(r)) + abs(h * _m.sin(r)),
                    abs(w * _m.sin(r)) + abs(h * _m.cos(r)))
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

    def donus_yolu_keepout(self, x0, x1):
        """C kartinda RF seritlerinin ALTINI yonlendirmeye kapat.

        ** IKI KATMANLI BIR RF KARTINDA ALT KATMANIN ISI REFERANS
        DUZLEMI OLMAK, GENEL YONLENDIRME KATMANI OLMAK DEGIL. **

        Olculdu (ilk yonlendirmeden sonra): ust katmandaki bir RF
        izinin altindan, alt katmanda GND OLMAYAN baska bir agin
        gecmesi — yani donus yolunun kesilmesi:
            kanal 1  177 kesisme / 1567 mm RF izi  -> 11.3 /cm
            kanal 2  329          / 1665           -> 19.8
            kanal 3  393          / 1552           -> 25.3
            kanal 4  472          / 1655           -> 28.5
        Alt katmandaki GND-disi bakirin %68'i DIKEY, yani kanal
        bantlarina DIK: her dikey iz ustunden gectigi her RF izinin
        donusunu kesiyor.

        Iki ayri zarar var:
          1 Her kesinti donus akimini dolastiriyor: endüktans ve o
            noktada kuplaj.
          2 Fark KANAL NUMARASIYLA DUZENLI ARTIYOR (2.7 kat). Bu
            kartin tek ayirt edici ozelligi dort kanalin AYNI
            olmasi; uzunluklar esit ama ORTAM esit degil. Ustelik
            kesen hatlar RLY_FAULT, +5V, Q0..Q18, ATT_CLK — role
            anahtarlarken AKTIF olan hatlar, yani kuplaj calisma
            sirasinda degisiyor ve kalibrasyonla telafi edilemiyor.

        Cozum: dort seridin altina keepout. Kontrol hatlari ya ust
        katmandan ya da seritler ARASINDAKI 19 mm'lik bantlardan,
        yani kanallara PARALEL gidiyor — paralel gecis hicbir
        donus yolunu kesmiyor.

        Serit araligi role sirasindan turetiliyor (gercek_yerlesim
        C_KANAL_Y): ky-20 ile ky+16 arasi filtre bolgesi (toroidler
        ky-14, role ky, filtre kondansatorleri ky+8..+13). ky+16'nin
        altinda role surucusu ve bobin hatlari var; orasi acik
        kaliyor cunku bobin hatti RF yolunu zaten kesmiyor (role
        govdesinin bobin ucu asagi, kontak ucu yukari bakiyor).
        """
        if self.kart != "C":
            return []
        try:
            import gercek_yerlesim as GY
            kanallar = GY.C_KANAL_Y
        except Exception:
            return []
        alt = self.katmanlar()[-1]
        out = []
        for ky in kanallar:
            # DSN'de y isareti ters: kart y -> -y
            ust_y = -(ky - 20) * 1000.0
            alt_y = -(ky + 16) * 1000.0
            out.append(f"    (keepout \"\" (rect {q(alt)} {x0:.0f} "
                       f"{alt_y:.0f} {x1:.0f} {ust_y:.0f}))")
        return out

    def dokum_alanlari(self, duzlem, x0, x1, y0, y1):
        """Bakir dokumleri Specctra "plane" kapsami olarak yaz.

        Freerouting bunlari ConductionArea'ya ceviriyor: o alandaki
        ayni agin butun pedleri BIRBIRINE BAGLI sayiliyor, yani
        yonlendiricinin cekmesi gereken bir sey kalmiyor — sadece
        pedden duzleme bir via.

        Koseler kart sinirina KIRPILIYOR. Sinir 0.5 mm iceri
        alinmisti; dokum kenari disarida kalirsa freerouting alani
        sinir disi sayip tumden atiyor ve sessizce eski duruma
        donuyoruz.
        """
        out = []
        for z in self.b.Zones():
            lay = pcbnew.LayerName(z.GetLayer())
            if lay not in duzlem:
                continue
            net = z.GetNetname()
            if not net:
                continue
            poly = z.Outline()
            for oi in range(poly.OutlineCount()):
                ol = poly.Outline(oi)
                pts = []
                for i in range(ol.PointCount()):
                    p = ol.CPoint(i)
                    x, y = p.x / UM, -p.y / UM
                    x = min(max(x, x0), x1)
                    y = min(max(y, y0), y1)
                    pts.append(f"{x:.0f} {y:.0f}")
                if len(pts) >= 3:
                    out.append(f"    (plane {q(net)} (polygon {q(lay)} 0 "
                               + " ".join(pts) + "))")
        return out

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
            o += self.donus_yolu_keepout(x0, x1)
            # DOKUMLARI DSN'E YAZ — YONLENDIRICI ONLARI GORMUYORDU.
            #
            # Katmanlari "power" ilan etmek yetmiyor. Freerouting v2
            # karti acar acmaz soyledi:
            #     Power-plane validation failed:
            #     - Dedicated power layer 'In1.Cu' has no conduction
            #       areas defined.
            # Yani iki toprak duzleminin VARLIGINI biliyordu ama
            # ICLERININ BOS oldugunu saniyordu. Sonucu: bir GND pedini
            # via ile duzleme indirmek yerine, o pedi baska bir GND
            # pedine SINYAL KATMANINDA iz cekerek baglamaya calisiyordu.
            #
            # A kartinda GND 289 pin — 1284 pinin %22.5'i. Yani
            # yonlendiricinin isinin dortte biri, aslinda hic
            # yonlendirilmemesi gereken bir agdi. Tikanmanin buyuk
            # kismi buydu.
            #
            # NEDEN AGI LISTEDEN CIKARMAK DEGIL: bir kez denenmis ve
            # geri alinmis (asagidaki DOKUM_AG notu). Ag listede
            # olmayinca pedleri yonlendiriciye GORUNMUYOR ve uzerlerinden
            # baska aglar geciyor — J20'nin dort toprak pedinde tam
            # olarak bu olmus, dort kisa devre. Dogru cozum ucuncusu:
            # ag listede KALIYOR (pedler goruluyor), dokum da DSN'de
            # tanimli (baglanti duzlemden kuruluyor). Boylece
            # yonlendiricinin her GND pedi icin yapmasi gereken tek sey
            # bir via dusurmek.
            o += self.dokum_alanlari(duzlem, x0, x1, y0, y1)
        ds = self.b.GetDesignSettings()
        o.append('    (via "via_default")')
        # GENEL KURAL DA KARTIN TABANINA INMELI. Sinif kurallari
        # 127 um derken buradaki genel kural 200'de kalirsa
        # yonlendirici sinifsiz her seyi (ve bazi durumlarda
        # sinifli olanlari da) 200'e gore ayiriyor ve BGA kacisi
        # yine acilmiyor.
        _gb = 300 if self.kart == "D" else (127 if self.kart == "A" else 150)
        o.append(f"    (rule (width 200) (clearance {_gb})"
                 f" (clearance 100 (type smd_smd)))")
        o.append("  )")
        return "\n".join(o)

    # DSN'IN HER BOLUMU SIRALI DOLASIYOR.
    # b.Footprints() kart ici siraya gore geliyor ve o sira UUID'lere
    # bagli — pcb_kur her kurulumda yeni UUID uretiyor. Yerlesim
    # artik tekrarlanabilir ama DSN degildi: ayni yerlesimden iki
    # kosuda A'da 444, C'de 484 satiri farkli bir dosya cikiyordu.
    # Onemlisi ag bolumu — bir agin pedleri hangi sirada yazilirsa
    # yonlendirici o siraya gore agac kuruyor, yani ayni karttan
    # farkli yonlendirme cikiyordu. Karsilastirilamayan bir cikti
    # ile "bu degisiklik neyi degistirdi" sorusu cevaplanamaz.
    def yerlesim(self):
        gruplar = {}
        for fp in self.sirali():
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
        for fp in self.sirali():
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
                # BAKIRI OLMAYAN PEDI DSN'E YAZMA.
                #
                # KiCad'in "-1EP" ayak izlerinde acik pedin uzerinde
                # dort ayri MACUN acikligi var (pencere bolmesi):
                # lehim macununu boler, %100 kaplamayi onler. Bunlarin
                # bakir katmani YOK — pcbnew'de LayerSet().CuStack()
                # bos donuyor.
                #
                # Once bunlar da yaziliyordu ve ust katmana
                # dusuyorlardi: yonlendirici acik pedin TAM ICINDE
                # dort tane bagsiz bakir ped goruyordu. D kartinda
                # olculdu, DSN'de U51'in image'i 21 pinli cikiyordu
                # (17 gercek + NC, NC@1, NC@2, NC@3) ve yonlendirici
                # her turda 220 ihlal bildiriyordu — sayi hic
                # dusmuyordu cunku cozulebilir bir sey degildi.
                # Ustelik o hayalet pedler acik pedin altindan gecisi
                # de kapatiyordu.
                if not list(pad.GetLayerSet().CuStack()):
                    continue
                ps = self.ps_ad(pad, katmanlar, fp)
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
        # GECIS PADSTACK'I — 600 DEGIL 500 um.
        # 0.8 mm adimli CABGA256'da dort topun ortasindaki kosegen
        # bosluk 0.406 mm (0.8*sqrt(2)/2 - 0.32/2). 600 um'lik bir
        # via 127 um boslukla bile 0.427 mm istiyor: sigmiyor.
        # 500 um ile 0.377 mm, 29 um pay kaliyor.
        # 500 um bu projenin kendi kurali: ASGARI_DELIK 0.30 +
        # her yanda 0.10 mm halka (pcb_kur.delikleri_buyut). Yani
        # daralt derken uretim sinifindan cikmiyoruz.
        # ses_oku ice alirken via'yi ayni olcuye kuruyor.
        o.append('    (padstack "via_default"')
        for lay in katmanlar:
            o.append(f"      (shape (circle {q(lay)} {VIA_CAP}))")
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
    # ON EK LISTESI DEGIL, DESEN — iki yonde de yanlis eslesiyordu.
    #
    # Eski liste ("LPF_","RX","TX","ANT","PA_","F1","N1") iki ayri
    # hata yapiyordu ve ikisi de olculdu:
    #
    # 1 FAZLA TUTUYORDU. "PA_" on eki D kartinda PA_ADC_CS, PA_ATT_LE,
    #   PA_C0..C5, PA_INHIBIT'i de yakaliyordu — dokuz SPI/kontrol
    #   hatti iki katmanli kalabalik kartta 1.5 mm cekiliyordu. Bunlar
    #   RF degil, lojik. Bosa giden bakir dogrudan yol tikanmasi.
    #
    # 2 EKSIK TUTUYORDU, ve bu daha kotusu. "F1"/"N1" on ekleri C
    #   kartinda SADECE 1. KANALIN filtre dugumlerini tutuyordu
    #   (F11_A, N11_1...). Kanal 2/3/4'un ayni dugumleri (F21_A,
    #   F31_A, F41_A) hicbir desene uymuyor ve varsayilan 250 um'e
    #   dusuyordu: kanal 1'de 1.5 mm, otekilerde 0.25 mm. C kartinin
    #   butun degeri dort kanalin BIREBIR AYNI olmasi; alti kat
    #   genislik farki serit empedansini ve kaybini dogrudan ayirir.
    #   Kanal numarasi 1 oldugu icin gozden kacan bir hata.
    #
    # Desen kanal numarasini rakam olarak yaziyor, sabit olarak degil.
    RF_DESEN = re.compile(
        r"^(LPF_|RX\d|TX|ANT|F\d\d_|N\d\d?_"
        r"|PA_(OUT|LPF_OUT)$)")
    # RF'e BENZEYEN ama lojik olanlar. Desenden once bakiliyor.
    RF_DEGIL = re.compile(r"^PA_(ADC_|ATT_|C\d|INHIBIT)")

    def ag_sinifi(self, ad, iki_katman):
        """Agin genisligi (um) — tablodan ve TURETILEN akimdan, buyugu."""
        return max(self._tablo(ad, iki_katman), self._turetilen(ad))

    def _turetilen(self, ad):
        """Seri yoldan yayilan akimin istedigi genislik (um).

        SADECE GENISLETIR, DARALTMAZ. IPC-2221'in verdigi sayi 10 C
        sicaklik artisinin tabani — bir ISINMA siniri. Bazi raylarda
        belirleyen isinma degil GERILIM DUSUMU: +1V1'de IPC 1 A icin
        300 um diyor ama cekirdek rayinda gerilim colunce FPGA
        rastgele hata verir, o yuzden tabloda 800 um yaziyor.
        Aracin "yeterli" demesi genisligi kucultmek icin gerekce
        degil; bu yuzden asagida max() var, atama degil.
        """
        a = self.akim.get(ad)
        if not a:
            return 0
        try:
            import guc_yolu
        except Exception:
            return 0
        # 50 um'lik basamaga YUKARI yuvarla: yonlendiriciye tuhaf
        # ondalik genislikler vermenin faydasi yok.
        um = guc_yolu.ipc_genislik(a, self.oz)
        return int(-(-um // 50) * 50)

    def _tablo(self, ad, iki_katman):
        """Elle yazilmis genislik tablosu."""
        if ad == "VIN50":
            # GIRIS RAYI, CIKIS RAYIYLA AYNI AKIMI TASIYOR.
            # VIN50 = J30'dan ters polarite MOSFET'ine (Q30) giden
            # hat; MOSFET'in oteki ucu +50V. Ayni akim, ayni telden:
            # 100 W ayarinda 6.67 A. +50V'a 2200 um yaziyordum ama
            # VIN50'yi hic saymamistim ve varsayilan 250 um'e
            # dusuyordu. 2 oz bakirda 0.25 mm 1.4 A tasiyor; 6.67 A'da
            # dengeye gelecegi sicaklik ~350 C, yani iz buharlasir.
            # Kartin en tehlikeli tek hatasi buydu ve DRC bunu
            # GORMEZ — DRC genislik olcer, akim bilmez.
            return 2200          # 6.67 A @ 2 oz, +50V ile ayni
        if ad in ("DRN_A", "DRN_B"):
            # KOL BASINA IKI CIHAZ VAR: AKIM BOLUNUYOR.
            # 2200 um yaziyordu, yani +50V ile ayni. Ama +50V toplam
            # 6.67 A tasiyor; DRN_A yalnizca Q10+Q11'i, yani 3.33 A.
            # 2 oz'da 10 C artis icin 0.79 mm yetiyor (IPC-2221).
            # Bosa giden bakirin bedeli gercek: 275x185 mm IKI
            # KATMANLI kartta 1 mm ustunde 55 ag vardi ve
            # yonlendirici her cakisma sorgusunda o genis izlerle
            # ugrasiyor — D 150 agla 2.5 saat kostu. 1200 um
            # gerekenin %50 ustunde, yani pay hala genis.
            return 1200
        if ad.startswith("SRC") and ad[3:].isdigit():
            # CIHAZ BASINA 1.67 A: 2 oz'da 0.30 mm yetiyor.
            # 600 um iki kat pay birakiyor. Bu aglar 0.01R olcu
            # direncine gidiyor ve uzunluklari 10 mm mertebesinde.
            return 600
        if ad in ("+50V", "DRN_CT"):
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
        if ad == "VIN_PROT":
            # GENISLIGI YUK DEGIL SIGORTA BELIRLIYOR.
            # A kartinin girisi: XT60 -> ters polarite MOSFET -> TVS
            # -> F1 (2 A) -> TPS62130. Yuk kucuk; A kartinin butcesi
            # 2.8 W ve bu ray C kartini da besliyor (J63/J65), toplam
            # 9 V'ta ~470 mA. 0.25 mm 1 oz'da 0.84 A tasiyor, yani
            # NORMAL calismada yetiyor. Fakat arizada yetmiyor:
            # asagi tarafta bir kisa devrede sigorta 2 A'e kadar
            # akimi gecirir ve o akimi tasiyacak olan iz degil
            # sigortadir. Iz sigortadan once acilirsa koruma elemani
            # izin kendisi olur — tek kullanimlik ve tamir edilemez.
            # Kural: besleme izi her zaman kendi sigortasinin
            # anma akimina gore olculur. 2 A, 1 oz dis katman,
            # 10 C artis -> 0.78 mm.
            return 800           # 2 A sigorta, 1 oz
        # ---------------------------------------------------------- A karti
        # A'NIN RAYLARININ COGU HIC LISTEDE YOKTU.
        # Yukaridaki tablo D kartina gore yazilmisti; A'nin +1V1,
        # +1V8*, +2V5, +3V3_A gibi raylarinin hicbiri eslesmiyor ve
        # son satirdaki varsayilan 250 um'e dusuyorlardi.
        #
        # A'DA GUC DUZLEMI YOK. Alti bakirin ikisi (In1/In4) toprak
        # dokumu, kalan dordu sinyal. Yani bu raylar gercekten iz
        # olarak gidiyor; iki katmanli kartta dokumun devraldigi isi
        # burada devralan bir sey yok.
        #
        # Olcut IPC-2221 dis katman, 1 oz (1.378 mil), 10 C artis:
        #     I = 0.048 * dT^0.44 * A^0.725      A mil^2
        #     0.5 A -> 0.12 mm   1.0 A -> 0.30 mm   2.0 A -> 0.78 mm
        # Asagidaki degerler bu tabanin ustune IR dusumu ve gecici
        # akim payi konarak yuvarlandi. Cekirdek ve analog raylarda
        # belirleyen ISINMA DEGIL GERILIM KARARLILIGI: ray colunce
        # FPGA rastgele yerlerde hata verir, ve o "bazen calisiyor"
        # turu hata haftalarca aranir.
        if ad == "+1V1":
            # ECP5 cekirdegi. %59 LUT dolulukta gecici akimlarla
            # ~1 A. Isinma siniri 0.30 mm ama cekirdek rayi
            # gerilim kararliligiyla olculur; 0.8 mm hem IR dusumunu
            # hem anahtarlama gecicilerini karsiliyor.
            return 800
        if ad == "+1V8_A":
            return 500           # ADC analog, 33 ped
        if ad in ("+1V8", "+1V8_D", "+1V8_CLK", "+2V5",
                  "+3V3_A", "+3V3_CLK"):
            # LDO cikislari; her biri kendi regulatorunun siniriyla
            # (ADP150 = 150 mA, TPS7A20 = 300 mA) zaten kisitli.
            # 0.4 mm 1 oz'da 1.2 A tasiyor — regulatorun verebilecegi
            # her akimin kat kat ustunde.
            return 400
        if ad in ("GND_HDR", "GND_STRAP", "GND_MODE"):
            # BU TOPRAKLARIN DOKUMU YOK. GND dokumu tasiyor, bunlar
            # tasimiyor: konnektor topragi, 0R uzerinden GND'ye
            # bagli ayri agalar. Yani donus akimi gercekten bu izden
            # geciyor ve varsayilan 250 um yetersiz.
            return 500
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
            #
            # 400'DEN 600'E. Yukaridaki "kat kat ustunde" hesabi
            # daldan gidiyordu, GOVDEDEN degil. A kartinda +3V3
            # 77 pede gidiyor ve govdesi butun karti tasiyor: iki
            # RTL8211F (0.5 W), FPGA cekirdeginin bucki, ADC/DAC
            # LDO'lari — 3.3 V'tan cekilen toplam ~1.0-1.2 A.
            # 0.4 mm'nin 1 oz dis katmanda 10 C artistaki siniri
            # 1.23 A: marj yok, hesabin kendi belirsizligi kadar bile
            # degil. 0.6 mm ayni kosulda 1.75 A. 0.8 mm'nin yolu
            # tikadigi olculdu, 0.4 mm'nin marji yok; ikisinin arasi.
            # A'nin GUC DUZLEMI YOK — alti bakirin ikisi (In1/In4)
            # toprak, kalan dordu sinyal. Yani bu ray gercekten iz
            # olarak gidiyor, dokum yardima gelmiyor.
            return 600
        if re.match(r"^VIN_[AB]\d_[PN]$", ad):
            # BUNLAR BESLEME DEGIL, ANALOG GIRIS.
            # Ad "VIN" ile basliyor diye besleme sanmak kolay; oysa
            # VIN_A1_P/N AD9251'in diferansiyel analog giris cifti —
            # trafonun ikincilinden ADC'nin bacagina giden hat, yani
            # kartin en hassas sinyali. Varsayilan 250 um'de
            # kaliyorlardi. Alis zincirinin geri kalaniyla ayni
            # sinifta olmalilar (elle_cek de bu aglari 350 um
            # cekiyor); cift olarak esit uzunluk zaten yerlesimden
            # geliyor.
            return 350
        if self.RF_DEGIL.match(ad):
            return 250
        # ------------------------------------------------------------
        # GENISLIGI BELIRLEYEN SEY AGIN ADI DEGIL, O NOKTADAKI GUC.
        #
        # Eski kural "iki katmanliysa RF agi 1500 um" diyordu ve
        # gerekcesi "100 W / 50 ohm = 1.4 A" idi. O gerekce SADECE
        # D kartinin final CIKISINDAN SONRASI icin dogru. Olculdu,
        # uc kartin ucunde de yanlis sonuc veriyordu:
        #
        #   C: 404 agin 203'u 1500 um'ye dustu. C'ye 100 W HIC
        #      girmiyor — TX yolu A kartinin AD9767'sinden geliyor
        #      (20 mA tam olcek, 50 ohm'da ~20 mW) ve 100 W'lik yol
        #      A -> D -> panel SO-239, C'ye ugramiyor. 1.5 mm iz +
        #      0.3 mm boslu = 1.8 mm adim; 350x235 mm iki katmanli
        #      kartta 203 agi bu adimda gecirmek mumkun degil,
        #      yonlendirici bitiremedi.
        #
        #   D: TX_IN 1500 um alirken ayni sinyalin devami olan
        #      ATT_OUT 250 um aliyordu — biri "TX" ile basliyor
        #      diye. Ustelik TX_IN, PE4312'nin 0.85 x 0.25 mm'lik
        #      pedine gidiyor: iz pedin ALTI KATI genisliginde.
        #      Yonlendirici o dugumu baglayamadi ve etrafindaki
        #      alti kontrol hattini da (PA_C0..C5, PA_ATT_LE)
        #      birlikte dusurdu.
        #
        # Yeni olcut: KARTIN KENDISI ve zincirdeki KONUM. D'de
        # finalden SONRASI 100 W tasiyor, oncesi milivat. Liste kisa
        # ve acik yazilabilir; ad desenine gore tahmin etmekten
        # daha dogru.
        if self.kart == "D":
            if ad in D_YUKSEK_GUC or re.match(r"^(LPF_B\d_(IN|OUT)|LF\d_[AB]"
                                              r"|N\d_1)$", ad):
                return 1500
            # finalden onceki her sey milivat seviyesi. ATT_OUT ve
            # zayiflatici/surucu zincirinin oteki dugumleri desene
            # uymuyor ama TX_IN ile AYNI SINYAL — ayni genislikte
            # olmalilar, yoksa ayni hat boyunca alti kat genislik
            # sicramasi oluyor.
            if ad in D_ORTA_GUC:
                return 400
            return 400 if self.RF_DESEN.match(ad) else 250
        if self.kart == "C":
            # C'nin tasidigi en yuksek guc AD9767'nin tam olcegi:
            # 20 mA / 50 ohm = 20 mW. 400 um o akimin bin kati.
            return 400 if self.RF_DESEN.match(ad) else 250
        if self.RF_DESEN.match(ad):
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
        for fp in self.sirali():
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
            #
            # AMA 300 um SABIT DE YANLISTI — A KARTINDA BGA'YI OLDURDU.
            # ECP5 CABGA256: 0.8 mm top adimi, 0.32 mm top pedi.
            # Dort topun ortasindaki kosegen bosluktan via atmak icin
            #     var    = 0.8*sqrt(2)/2 - 0.32/2 = 0.406 mm
            #     gereken = via_yaricap + boslu = 0.25 + 0.30 = 0.550 mm
            # 0.550 > 0.406, yani via GEOMETRIK OLARAK SIGMIYOR.
            # Dis iki halka (112 top) ust katmandan kacabiliyor, kalan
            # 144 top via bekliyor ve atilamiyor: FPGA'nin ici hic
            # yonlendirilemez. Yonlendirici kart kalabalik oldugu icin
            # degil, IMKANSIZ oldugu icin bitiremiyordu.
            #     boslu 200 -> 0.450  sigmiyor
            #     boslu 150 -> 0.400  siginca 6 um pay kaliyor
            #     boslu 127 -> 0.377  29 um pay
            # 127 um = 5 mil, JLCPCB'nin 4+ katman STANDART sinifi
            # (min iz/aciklik 0.09 mm), ek maliyet yok. Kartin kendi
            # kurali da zaten 0.127 (pcb_kur.kurallar).
            #
            # Guc siniflari 300'de kaliyor: orada gerekce gerilim ve
            # dokum ayrimi, geometrik sikisiklik degil.
            # D karti 2 oz dis bakir: JLCPCB'nin o surecte asgari
            # iz/aciklik siniri 0.25 mm, o yuzden D'de daraltma YOK.
            if w >= 800 or self.kart == "D":
                bosluk = 300
            else:
                bosluk = 127 if self.kart == "A" else 150
            o.append(f"      (rule (width {w}) (clearance {bosluk}))")
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
        # VIA'LAR DA KORUNMALI.
        # Once via'lar atlaniyordu ve bu, elle cizilen her seyin
        # yalnizca TEK KATMANDA kalmasi anlamina geliyordu. BGA
        # kacisi (bga_kacis) top pedinden kosegen bosluga bir via
        # koyup ic katmanlara iniyor; via DSN'de yoksa yonlendirici
        # orayi bos sanip uzerinden gecer ve kart kisa devre olur.
        for tr in self.b.GetTracks():
            if not isinstance(tr, pcbnew.PCB_VIA):
                continue
            ag = tr.GetNetname()
            if not ag:
                continue
            x1, y1 = self.xy(tr.GetPosition())
            o.append(f"    (via \"via_default\" {x1:.0f} {y1:.0f}")
            o.append(f"      (net {q(ag)})(type fix))")
            n += 1
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
        open(yol + ".parmak", "w").write(parmak(self.b))
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
