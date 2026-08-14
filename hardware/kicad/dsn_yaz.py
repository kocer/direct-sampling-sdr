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
        n = self.b.GetCopperLayerCount()
        ad = []
        for i in range(n):
            lay = self.b.GetLayerID(pcbnew.LayerName(
                pcbnew.F_Cu if i == 0 else (pcbnew.B_Cu if i == n - 1
                                            else pcbnew.In1_Cu + i - 1)))
            ad.append(pcbnew.LayerName(
                pcbnew.F_Cu if i == 0 else (pcbnew.B_Cu if i == n - 1
                                            else pcbnew.In1_Cu + i - 1)))
        return ad

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
        o = ["  (structure"]
        for i, lay in enumerate(katmanlar):
            o.append(f"    (layer {q(lay)} (type signal) "
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

    def ag(self):
        aglar = {}
        for fp in self.b.Footprints():
            adlar = ped_adlari(fp)
            for pad, pad_ad in zip(fp.Pads(), adlar):
                n = pad.GetNetname()
                if n and pad.GetNumber():
                    aglar.setdefault(n, []).append(
                        f"{fp.GetReference()}-{pad_ad}")
        o = ["  (network"]
        for n, pins in sorted(aglar.items()):
            if len(pins) < 2:
                continue
            o.append(f"    (net {q(n)}")
            o.append("      (pins " + " ".join(q(p) for p in pins) + "))")
        o.append('    (class kicad_default ' +
                 " ".join(q(n) for n in sorted(aglar) if len(aglar[n]) > 1))
        o.append("      (circuit (use_via via_default))")
        o.append("      (rule (width 200) (clearance 200))")
        o.append("    )")
        o.append("  )")
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
        govde.append("  (wiring)")
        govde.append(")")
        open(yol, "w", encoding="utf-8").write("\n".join(govde) + "\n")
        return len(katmanlar)


if __name__ == "__main__":
    pcb, dsn = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(pcb)
    y = Yazici(b)
    n = y.yaz(dsn)
    print(f"{os.path.basename(dsn)}: {n} katman, "
          f"{len(list(b.Footprints()))} parca, "
          f"{len(y.padstack)} padstack, {os.path.getsize(dsn) // 1024} KB")
