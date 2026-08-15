#!/usr/bin/env python3
"""Toprak dikis via'lari — dokum adalarini birbirine bagla.

    python3 dikis.py D_pa/dogrudan_sdr_D.kicad_pcb

NEDEN: GND'yi yonlendiriciye vermiyoruz, dokum tasiyor. Ama iki
katmanli bir kartta ust dokumu ust katmanin izleri, alt dokumu alt
katmanin izleri kesiyor. Kesilen parcalar ADA oluyor ve adanin oteki
katmandaki saglam dokume gecebilecegi bir yol yoksa oradaki pedler
bagsiz kaliyor — D kartinda 42 tane boyle ped cikti.

Dikis via'si tam bunu yapiyor: dokumun iki yuzunu belirli araliklarla
birbirine bagliyor. Bir yuzde ada olusursa oteki yuzden dolaniyor.

ARALIK NEDEN ONEMLI: RF'te donus akimi sinyalin hemen altindan akmak
ister. Katman degistiren bir iz, donus akiminin da katman degistirmesi
demek, ve o akim en yakin dikis via'sindan gecmek zorunda. Via uzaksa
donus yolu buyuk bir ilmek ciziyor; ilmek hem yayiyor hem topluyor.
Kural olarak en yuksek frekansin dalga boyunun 1/20'si:
    54 MHz -> lambda 5.5 m -> 275 mm
Bu cok gevsek. Gercek kisit ADA OLUSMASINI ENGELLEMEK, o yuzden
10 mm izgara kullaniyoruz — kartin her yerinden en fazla 5 mm otede
bir via var.

PEDLERDEN VE IZLERDEN UZAK DUR: via bir sinyal izinin uzerine
dusrse kisa devre. Yerlestirmeden once her noktayi butun pedlere ve
izlere karsi deniyoruz.
"""
import math
import os
import sys

import pcbnew

MM = 1e6
ARALIK = 10.0        # mm, izgara adimi
VIA_CAP = 0.6        # mm
VIA_DELIK = 0.3      # mm
# Ize ve pede en az bu kadar uzak. 0.4 mm ile dikis via'lari ve
# saplari alt kenardaki role kontrol izlerine dedi (DPD_OUT, RLY_*
# uzerinde 8'er ihlal). 0.65 mm, 0.6 mm'lik via + 0.25 mm iz icin
# uretim boslugunun ustunde kaliyor.
PAY = 0.65


def engeller(b):
    """(x, y, yaricap) listesi — via'nin degemeyecegi her sey."""
    out = []
    for fp in sorted(b.Footprints(), key=lambda f: f.GetReference()):
        for p in fp.Pads():
            q = p.GetPosition()
            r = max(p.GetSizeX(), p.GetSizeY()) / 2 / MM
            out.append((q.x / MM, q.y / MM, r + VIA_CAP / 2 + PAY))
    return out


def iz_engeli(b):
    """(x1, y1, x2, y2, yaricap) — izler."""
    out = []
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            q = t.GetPosition()
            out.append((q.x / MM, q.y / MM, q.x / MM, q.y / MM,
                        t.GetWidth() / 2 / MM + VIA_CAP / 2 + PAY))
        else:
            a, c = t.GetStart(), t.GetEnd()
            out.append((a.x / MM, a.y / MM, c.x / MM, c.y / MM,
                        t.GetWidth() / 2 / MM + VIA_CAP / 2 + PAY))
    return out


def parca_uzak_mi(x1, y1, x2, y2, ped, iz, adim=0.15, haric=None):
    """Bir DOGRU PARCASI boyunca engel var mi.

    Once yalnizca via'nin yerini deniyordum; sap (pedden via'ya giden
    kisa iz) baska izlerin uzerinden geciyordu — 6 kisa devre, 14
    maske koprusu, 8 iz kesismesi. Via'yi koymak yetmiyor, ona giden
    yolu da denemek gerek.
    """
    d = math.hypot(x2 - x1, y2 - y1)
    n = max(2, int(d / adim))
    for i in range(n + 1):
        u = i / n
        if not uzak_mi(x1 + (x2 - x1) * u, y1 + (y2 - y1) * u, ped, iz,
                       haric):
            return False
    return True


def uzak_mi(x, y, ped, iz, haric=None):
    """haric: (x, y) — bu engeli yok say.

    Sap denetimi sifir via yerlestirdi cunku baglanacak PEDIN KENDISI
    de engel listesinde. Pedden cikan bir sapin pede degmesi normal;
    o pedi denetim disinda tutmak gerek.
    """
    for px, py, r in ped:
        if haric is not None and abs(px - haric[0]) < 1e-6 \
                and abs(py - haric[1]) < 1e-6:
            continue
        if (x - px) ** 2 + (y - py) ** 2 < r * r:
            return False
    for x1, y1, x2, y2, r in iz:
        dx, dy = x2 - x1, y2 - y1
        uz2 = dx * dx + dy * dy
        if uz2 < 1e-9:
            d2 = (x - x1) ** 2 + (y - y1) ** 2
        else:
            u = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / uz2))
            ex, ey = x1 + u * dx - x, y1 + u * dy - y
            d2 = ex * ex + ey * ey
        if d2 < r * r:
            return False
    return True


def ped_viasi(b, gnd_kod, ust, alt, ped, iz):
    """Dokumun ULASAMADIGI toprak pedlerine yandan via + sap.

    QFN'in toprak bacaklari 0.5 mm adimla diziliyor; dokumun 0.3 mm
    boslugu + 0.2 mm asgari genisligi o araliga giremiyor. Yani o
    pedler dokumden beslenemez, ve D kartinda 36 tanesi boyle kaldi
    (U10, U30, U31, U51 — hepsi QFN).
    
    Elle cizen biri ne yaparsa onu yapiyoruz: pedin hemen yanina bir
    via, pedden via'ya kisa bir sap. Via oteki katmandaki saglam
    dokume iniyor.
    """
    yeni_via, yeni_iz = 0, 0
    for fp in sorted(b.Footprints(), key=lambda f: f.GetReference()):
        fx = fp.GetPosition().x / MM
        fy = fp.GetPosition().y / MM
        for pd in fp.Pads():
            if pd.GetNetname() != "GND":
                continue
            q = pd.GetPosition()
            px, py = q.x / MM, q.y / MM
            w = max(pd.GetSizeX(), pd.GetSizeY()) / 2 / MM
            # parcanin disina dogru
            dx, dy = px - fx, py - fy
            d = math.hypot(dx, dy) or 1.0
            for mesafe in (w + 0.75, w + 1.1, w + 1.5):
                vx = px + dx / d * mesafe
                vy = py + dy / d * mesafe
                # via'nin yeri VE sapin yolu, ikisi de temiz olmali.
                # Sapin baslangici pedin kendisi oldugu icin ilk
                # 0.3 mm'yi atliyoruz — yoksa pedin kendisine takiliyor.
                bx = px + dx / d * (w + 0.05)
                by = py + dy / d * (w + 0.05)
                if (uzak_mi(vx, vy, ped, iz, (px, py))
                        and parca_uzak_mi(bx, by, vx, vy, ped, iz,
                                          haric=(px, py))):
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(pcbnew.VECTOR2I(int(vx * MM), int(vy * MM)))
                    v.SetWidth(int(VIA_CAP * MM))
                    v.SetDrill(int(VIA_DELIK * MM))
                    v.SetLayerPair(ust, alt)
                    v.SetNetCode(gnd_kod)
                    b.Add(v)
                    tr = pcbnew.PCB_TRACK(b)
                    tr.SetStart(q)
                    tr.SetEnd(pcbnew.VECTOR2I(int(vx * MM), int(vy * MM)))
                    tr.SetWidth(int(0.3 * MM))
                    tr.SetLayer(pd.GetLayer() if pd.GetLayer() in (ust, alt)
                                else ust)
                    tr.SetNetCode(gnd_kod)
                    b.Add(tr)
                    ped.append((vx, vy, VIA_CAP / 2 + PAY))
                    yeni_via += 1
                    yeni_iz += 1
                    break
    return yeni_via, yeni_iz


def dik(pcb, aralik=ARALIK):
    b = pcbnew.LoadBoard(pcb)
    kutu = b.GetBoardEdgesBoundingBox()
    x0, y0 = kutu.GetLeft() / MM, kutu.GetTop() / MM
    x1, y1 = kutu.GetRight() / MM, kutu.GetBottom() / MM

    gnd_kod = 0
    for fp in b.Footprints():
        for p in fp.Pads():
            if p.GetNetname() == "GND":
                gnd_kod = p.GetNetCode()
                break
        if gnd_kod:
            break
    if not gnd_kod:
        print("GND agi bulunamadi")
        return 0

    ped = engeller(b)
    iz = iz_engeli(b)

    ust = None
    alt = None
    for i in b.GetEnabledLayers().CuStack():
        if ust is None:
            ust = i
        alt = i

    n = 0
    y = y0 + aralik / 2
    while y < y1:
        x = x0 + aralik / 2
        while x < x1:
            # kart kenarindan uzak dur
            if (x - x0 > 2.5 and x1 - x > 2.5
                    and y - y0 > 2.5 and y1 - y > 2.5
                    and uzak_mi(x, y, ped, iz)):
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
                v.SetWidth(int(VIA_CAP * MM))
                v.SetDrill(int(VIA_DELIK * MM))
                v.SetLayerPair(ust, alt)
                v.SetNetCode(gnd_kod)
                b.Add(v)
                n += 1
            x += aralik
        y += aralik

    pv, pi = ped_viasi(b, gnd_kod, ust, alt, ped, iz)
    print(f"   izgara {n} via, ped dibi {pv} via + {pi} sap")

    # dokumleri yeniden doldur ki yeni via'lar bagansin
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(pcb)
    return n


def fiducial(pcb, pay=6.0):
    """Uc hizalama isareti — otomatik dizgi makinesi icin.

    ** UC KARTTA DA SIFIR TANE VARDI. ** Dizgi makinesi karti
    fiducial'lardan hizaliyor; yoksa JLCPCB gibi servisler ya karti
    geri ceviriyor ya da kendileri rastgele bir yere ekliyor — o
    zaman hizalama toleransi dusuyor ve 0.5 mm adimli QFN'lerde
    (PE4312, DRV8833, TPS62130, AD8318) bu dogrudan koprulenmis
    bacak demek.

    Uc tane, KOSEGEN OLMAYAN uc kosede: makine kartin donusunu
    ancak asimetrik bir uclu ile anlayabiliyor. 1 mm bakir daire,
    2 mm maske acikligi (standart).

    ** NEDEN ICE ALMA ADIMINDA: ** fiducial'in agi yok, netlistte
    yok, yerlesime de katilmiyor. pcb_kur'a koysaydik ayak izi
    sayisi degisir ve DSN parmak izi bozulurdu — yani her fiducial
    eklemesi butun yonlendirmeyi gecersiz kilardi. Buraya, dikis
    via'larinin yanina ait.
    """
    b = pcbnew.LoadBoard(pcb)
    for fp in list(b.Footprints()):
        if fp.GetReference().startswith("FID"):
            return 0                      # zaten var, ikinci kez ekleme
    kutu = b.GetBoardEdgesBoundingBox()
    x0, y0 = kutu.GetLeft() / MM, kutu.GetTop() / MM
    x1, y1 = kutu.GetRight() / MM, kutu.GetBottom() / MM
    # YER ARANIYOR, SABIT KOSE DEGIL. Kose noktalari ZATEN DOLU:
    # montaj delikleri (5,5), guc konnektoru (A'da XT60 14,6) ve
    # kenar konnektorleri oralarda. Fiducial'in etrafinda 2 mm
    # maske acikligi var; parcanin ustune denk gelirse dizgi
    # makinesi onu bulamaz.
    # Uc kose bolgesinde 1 mm adimla tarayip ilk BOS noktayi
    # aliyoruz. Bos = hicbir ayak izinin courtyard'ina 3 mm'den
    # yakin degil.
    kutular = []
    for fp in b.Footprints():
        try:
            k = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            if k.GetWidth() <= 0:
                k = fp.GetBoundingBox()
        except Exception:
            k = fp.GetBoundingBox()
        kutular.append((k.GetLeft() / MM, k.GetRight() / MM,
                        k.GetTop() / MM, k.GetBottom() / MM))

    def bos_mu(x, y, pay2=3.0):
        for l, r, u, a2 in kutular:
            if l - pay2 < x < r + pay2 and u - pay2 < y < a2 + pay2:
                return False
        return True

    def ara(bx, by, ax, ay):
        for adim in range(0, 60):
            for k in range(adim + 1):
                x = bx + ax * k
                y = by + ay * (adim - k)
                if x0 + 3 < x < x1 - 3 and y0 + 3 < y < y1 - 3 and bos_mu(x, y):
                    return (x, y)
        return None

    yerler = [ara(x0 + pay, y0 + pay, 1, 1),
              ara(x1 - pay, y0 + pay, -1, 1),
              ara(x0 + pay, y1 - pay, 1, -1)]
    yerler = [p for p in yerler if p]
    try:
        import pcb_kur
        libs = pcb_kur.fp_kutuphaneleri()
        kutuphane = libs["Fiducial"]
    except Exception:
        return 0
    n = 0
    for i, (x, y) in enumerate(yerler):
        try:
            fp = pcbnew.FootprintLoad(kutuphane, "Fiducial_1mm_Mask2mm")
        except Exception:
            fp = None
        if fp is None:
            continue
        fp.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
        fp.SetReference(f"FID{i + 1}")
        b.Add(fp)
        n += 1
    if n:
        b.Save(pcb)
    return n


if __name__ == "__main__":
    yol = sys.argv[1]
    a = float(sys.argv[2]) if len(sys.argv) > 2 else ARALIK
    print(f"{os.path.basename(yol)}: {dik(yol, a)} dikis via'si")
    nf = fiducial(yol)
    if nf:
        print(f"   {nf} fiducial eklendi")
