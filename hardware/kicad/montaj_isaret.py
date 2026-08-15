#!/usr/bin/env python3
"""Fiducial ve test noktalarini karta ekle.

    python3 montaj_isaret.py A      # tek kart
    python3 montaj_isaret.py        # uc kart

ZINCIRDE NEREYE GIRER: pcb_kur ve gercek_yerlesim'den SONRA, ayir'dan
ONCE. pcb_kur karti netlistten yeniden kurdugu icin bu parcalar her
seferinde yeniden eklenmeli; onceki calistirmanin ekledikleri
dosyadan siliniyor (ipek.py ile ayni yontem — board.Remove()
segfault atiyor).

NEDEN FIDUCIAL. Otomatik dizgi makinesi karti fiducial'lardan
hizaliyor. Yoksa ureticinin kendi koydugu referanslara kaliyor ve
hizalama toleransi duser; 0.5 mm adimli QFN ve 0.8 mm adimli BGA'da
bu farkin bedeli yanlis dizilmis bir parca.
UCU DE ASIMETRIK yerlestiriliyor: uc fiducial simetrik olursa makine
karti 180 derece donuk da hizalayabilir ve butun kart ayna dizilir.

NEDEN TEST NOKTASI. Uc kart da ilk kez calisacak. D'de 100 W RF ve
50 V var; prob tutacak yer yoksa devreye alma sirasinda parca
bacagina krokodil takilir. Kayan bir prob ucu 50 V'ta finali
oldurur, ve o hata bir kez olur.

YER SECIMI OLCUYLE. Bos alan aranarak yerlestiriliyor: mevcut
parcalarin kapladigi kutulara ve kart kenarina bakip, istenen
yaricapta bos bir nokta bulunana kadar spiral taraniyor. Elle
koordinat yazmak, yerlesim degistiginde sessizce parcanin ustune
dusen bir test noktasi birakir.
"""
import math
import os
import re
import sys

import pcbnew

KARTLAR = {
    "A": "A_main/dogrudan_sdr_A.kicad_pcb",
    "C": "C_rf/dogrudan_sdr_C.kicad_pcb",
    "D": "D_pa/dogrudan_sdr_D.kicad_pcb",
}

FID_KUTU = "/usr/share/kicad/footprints/Fiducial.pretty"
FID_AD = "Fiducial_1mm_Mask2mm"
TP_KUTU = "/usr/share/kicad/footprints/TestPoint.pretty"
TP_AD = "TestPoint_Pad_D1.5mm"

# Bu isaretle eklenen parcalari bir sonraki kosuda taniyoruz.
IZ = "​"          # sifir genislikli bosluk, ipek.py ile ayni hile

# Kart basina test edilecek aglar. Devreye almada gercekten olculecek
# olanlar; her ag icin bir nokta.
TEST_AGLARI = {
    "A": ["+1V1", "+1V8_A", "+1V8_D", "+2V5", "+3V3", "VIN_PROT",
          "FPGA_CLK80", "DONE", "nINIT", "REF10_IN"],
    "C": ["+5V", "+3V3", "VIN_PROT", "RX1_OUT", "RX2_OUT",
          "RX3_OUT", "RX4_OUT"],
    # D'dekiler bias ayarinda olculecek; o sirada cihaz basina ~83 W
    # dagiliyor ve prob kaymasi pahali.
    "D": ["+50V", "+12V", "+5V", "+3V3", "DRN_CT",
          "GATE1", "GATE2", "GATE3", "GATE4",
          "IMEAS1", "IMEAS2", "IMEAS3", "IMEAS4",
          "FWD_LOG", "REV_LOG"],
}


def yukle(kutu, ad):
    fp = pcbnew.FootprintLoad(kutu, ad)
    if fp is None:
        sys.exit("footprint yuklenemedi: %s / %s" % (kutu, ad))
    return fp


def eski_sil(pcb):
    """Onceki kosunun ekledigi fiducial/test noktalarini DOSYADAN sil.

    board.Remove() bu KiCad surumunde segfault atiyor; ipek.py ile
    ayni yol izleniyor.
    """
    s = open(pcb, encoding="utf-8").read()
    n = 0
    out = []
    i = 0
    while True:
        j = s.find('(footprint ', i)
        if j < 0:
            out.append(s[i:])
            break
        # blogun sonunu parantez sayarak bul
        k = j
        derinlik = 0
        while k < len(s):
            if s[k] == '(':
                derinlik += 1
            elif s[k] == ')':
                derinlik -= 1
                if derinlik == 0:
                    break
            k += 1
        blok = s[j:k + 1]
        if IZ in blok and re.search(r'"(FID|TP)\d+', blok):
            out.append(s[i:j])
            n += 1
        else:
            out.append(s[i:k + 1])
        i = k + 1
    if n:
        open(pcb, "w", encoding="utf-8").write("".join(out))
    return n


def dolu_kutular(b):
    """Isgal edilmis alanlar — COURTYARD VE BBOX'IN BUYUGU.

    Once sadece courtyard kullaniyordum ve test noktalari komsu
    parcalarin IPEK YAZISININ altina dusuyordu (olctum: A'da 11,
    C'de 9, D'de 15 yerde). Courtyard sadece govdeyi kapsiyor;
    bounding box referans ve deger metnini de iceriyor.

    Ipek boyasi test noktasi pedinin ustune basarsa prob temasi
    bozulur — ve test noktasinin varlik sebebi guvenilir temas.
    Ihtiyatli taraf: ikisinin BUYUGUNU al.
    """
    k = []
    for f in b.GetFootprints():
        c = f.GetCourtyard(pcbnew.F_CrtYd)
        gb = f.GetBoundingBox()
        if c and c.OutlineCount() > 0:
            cb = c.BBox()
            cb.Merge(gb)
            k.append(cb)
        else:
            k.append(gb)
    for t in b.GetTracks():
        k.append(t.GetBoundingBox())
    return k


def bos_mu(x, y, r, kutular, bb):
    """(x,y) merkezli r yaricapli daire bos mu — kart icinde ve
    hicbir parcaya degmiyor mu."""
    if not (bb.GetLeft() + r < x < bb.GetRight() - r and
            bb.GetTop() + r < y < bb.GetBottom() - r):
        return False
    for k in kutular:
        if (k.GetLeft() - r < x < k.GetRight() + r and
                k.GetTop() - r < y < k.GetBottom() + r):
            return False
    return True


def bos_yer_bul(x0, y0, r, kutular, bb, kullanilan, adim=1000000):
    """(x0,y0) civarinda spiral tarayarak bos nokta bul."""
    for halka in range(0, 200):
        for a in range(0, max(1, halka * 8)):
            ac = 2 * math.pi * a / max(1, halka * 8)
            x = int(x0 + halka * adim * math.cos(ac))
            y = int(y0 + halka * adim * math.sin(ac))
            if not bos_mu(x, y, r, kutular, bb):
                continue
            if any(math.hypot(x - u[0], y - u[1]) < 2 * r for u in kullanilan):
                continue
            return x, y
    return None


def kart_isle(ad):
    yol = KARTLAR[ad]
    silinen = eski_sil(yol)
    b = pcbnew.LoadBoard(yol)
    bb = b.GetBoardEdgesBoundingBox()
    kutular = dolu_kutular(b)
    kullanilan = []
    eklendi = {"fid": 0, "tp": 0}

    # --- fiducial: uc kose, ASIMETRIK ---
    # ZATEN VARSA DOKUNMA. Ajan bunlari sema/yerlesim tarafinda
    # ekledi; ikinci takim eklemek karti bozar ve dizgi makinesi
    # hangi ucluyu kullanacagini bilemez. Once olctum, sonra yazdim:
    # uc kartta da 3'er tane var ve konumlari asimetrik (L seklinde),
    # yani makine karti ters hizalayamaz. Dogru durumdalar.
    varolan = [f for f in b.GetFootprints()
               if "iducial" in f.GetFPIDAsString()]
    if varolan:
        print("   fiducial zaten var (%d), atlandi" % len(varolan))
        kose = []
    else:
    # Dordunculuk yerine ucluk: uc nokta yeterli ve asimetrik olunca
    # makine karti ters hizalayamaz.
        kose = [(bb.GetLeft() + 6000000, bb.GetTop() + 6000000),
                (bb.GetRight() - 6000000, bb.GetTop() + 6000000),
                (bb.GetLeft() + 6000000, bb.GetBottom() - 6000000)]
    for i, (x0, y0) in enumerate(kose, 1):
        yer = bos_yer_bul(x0, y0, 2500000, kutular, bb, kullanilan)
        if yer is None:
            print("   FID%d icin yer bulunamadi" % i)
            continue
        fp = yukle(FID_KUTU, FID_AD)
        fp.SetPosition(pcbnew.VECTOR2I(yer[0], yer[1]))
        fp.SetReference("FID%d" % i)
        fp.SetValue(IZ + "FID")
        fp.Reference().SetVisible(False)
        b.Add(fp)
        kullanilan.append(yer)
        kutular.append(fp.GetBoundingBox())
        eklendi["fid"] += 1

    # --- test noktalari ---
    # Her agin mevcut bir pedinin YANINA konuyor; boylece test noktasi
    # o agin kendi bolgesinde kaliyor ve router'a uzun bir dal
    # cektirmiyor.
    agpos = {}
    for f in b.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if n and n not in agpos:
                agpos[n] = p.GetPosition()

    netmap = {n.GetNetname(): n for n in b.GetNetInfo().NetsByName().values()}

    for i, ag in enumerate(TEST_AGLARI.get(ad, []), 1):
        if ag not in agpos:
            print("   %s: kartta boyle bir ag yok, atlandi" % ag)
            continue
        p0 = agpos[ag]
        yer = bos_yer_bul(p0.x, p0.y, 1600000, kutular, bb, kullanilan)
        if yer is None:
            print("   TP%d (%s) icin yer bulunamadi" % (i, ag))
            continue
        fp = yukle(TP_KUTU, TP_AD)
        fp.SetPosition(pcbnew.VECTOR2I(yer[0], yer[1]))
        fp.SetReference("TP%d" % i)
        fp.SetValue(IZ + ag)
        # deger gorunur olsun: prob tutan kisi hangi ag oldugunu bilsin
        fp.Value().SetVisible(True)
        fp.Value().SetTextSize(pcbnew.VECTOR2I(800000, 800000))
        fp.Value().SetTextThickness(150000)
        fp.Reference().SetVisible(False)
        for pad in fp.Pads():
            if ag in netmap:
                pad.SetNet(netmap[ag])
        b.Add(fp)
        kullanilan.append(yer)
        kutular.append(fp.GetBoundingBox())
        eklendi["tp"] += 1

    b.Save(yol)
    print("%s: %d eski silindi, %d fiducial + %d test noktasi eklendi"
          % (ad, silinen, eklendi["fid"], eklendi["tp"]))
    return eklendi


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        if k in KARTLAR:
            kart_isle(k)
