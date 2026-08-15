#!/usr/bin/env python3
"""Kritik aglari ELLE cek — simetri yonlendiriciye birakilmaz.

    python3 elle_cek.py D_pa/dogrudan_sdr_D.kicad_pcb

NEDEN: yerlesim dort kapiyi surucuden esit uzaklikta kurdu (19.5 mm),
ama yonlendirici bunu bilmiyor ve en kisa yolu ariyor. Sonuc 66.7 /
80.1 / 95.4 / 123.4 mm oldu. Itme-cekme cift harmonikleri ancak iki
kol esit oldugu surece bastiriyor; 57 mm'lik bir fark o bastirmayi
bitirir.

Cozum yerlesimdekiyle ayni: onemli olani elle koy, gerisini algoritma
doldursun. Buradaki izler DSN'e `(type protect)` ile yaziliyor —
yonlendirici onlara dokunmuyor, kalan aglari etraflarindan dolastiriyor.

DOGRUDAN HAT. Pedler zaten esit uzaklikta oldugu icin iki ped
arasindaki duz cizgi hem en kisa hem esit. Meander gerekmiyor:
simetri geometriden geliyor, sonradan duzeltmeden.
"""
import itertools
import math
import os
import sys

import pcbnew

MM = 1e6

# ag -> (genislik mm, katman). Yonlendiriciden korunacaklar.
D_KRITIK = {
    # dort finalin kapisi: surucuden esit uzaklikta
    "G10": (0.5, "F.Cu"), "G11": (0.5, "F.Cu"),
    "G12": (0.5, "F.Cu"), "G13": (0.5, "F.Cu"),
    # itme-cekme kollari: cikis trafosuna esit
    # 2 oz bakir: 6.67 A icin 2.2 mm yeterli, 4 mm degil
    "DRN_A": (2.2, "F.Cu", "T"), "DRN_B": (2.2, "F.Cu", "T"),
    # surucunun kendi kollari
    "D2_DA": (1.5, "F.Cu", "T"), "D2_DB": (1.5, "F.Cu", "T"),
    "D2_GA_S": (0.5, "F.Cu", "Q"), "D2_GB_S": (0.5, "F.Cu", "Q"),
}


# A karti: dort alis zinciri ve saat. Bunlarin esitligi kartin
# butun degeri — yonlendirici D'nin kapilarina ne yaptiysa bunlara
# da ayni seyi yapar.
A_KRITIK = {}
for _k in ("A1", "B1", "A2", "B2"):
    A_KRITIK[f"RF_{_k}"] = (0.35, "F.Cu")
    A_KRITIK[f"SEC_{_k}_P"] = (0.35, "F.Cu")
    A_KRITIK[f"SEC_{_k}_N"] = (0.35, "F.Cu")
    A_KRITIK[f"VIN_{_k}_P"] = (0.35, "F.Cu")
    A_KRITIK[f"VIN_{_k}_N"] = (0.35, "F.Cu")

# C karti: dort kanalin anten girisi ve ilk bant. Ayni gerekce.
C_KRITIK = {}
for _k in range(1, 5):
    C_KRITIK[f"ANT{_k}"] = (1.5, "F.Cu")
    C_KRITIK[f"RX{_k}_ANT"] = (1.5, "F.Cu")
    C_KRITIK[f"RX{_k}_B1_IN"] = (1.5, "F.Cu")
    C_KRITIK[f"RX{_k}_OUT"] = (1.5, "F.Cu")

TABLOLAR = {"A": A_KRITIK, "C": C_KRITIK, "D": D_KRITIK}


def pedler(b, ag):
    out = []
    for fp in b.Footprints():
        for p in fp.Pads():
            if p.GetNetname() == ag:
                q = p.GetPosition()
                out.append((q.x, q.y, fp.GetReference(), p.GetNumber()))
    return out


def agac(noktalar):
    """En kisa baglanti agaci — Prim, kucuk kume icin yeterli."""
    if len(noktalar) < 2:
        return []
    icinde = {0}
    kenarlar = []
    while len(icinde) < len(noktalar):
        en = None
        for i in icinde:
            for j in range(len(noktalar)):
                if j in icinde:
                    continue
                d = math.dist(noktalar[i][:2], noktalar[j][:2])
                if en is None or d < en[0]:
                    en = (d, i, j)
        kenarlar.append((en[1], en[2]))
        icinde.add(en[2])
    return kenarlar


def temiz(b, iz, ag):
    """Iz baska bir agin pedini kesiyor mu?"""
    a, c = iz.GetStart(), iz.GetEnd()
    yari = iz.GetWidth() / 2
    for fp in b.Footprints():
        for p in fp.Pads():
            if p.GetNetname() == ag or not p.GetNetname():
                continue
            q = p.GetPosition()
            r = max(p.GetSizeX(), p.GetSizeY()) / 2 + yari
            dx, dy = c.x - a.x, c.y - a.y
            uz2 = dx * dx + dy * dy
            if uz2 == 0:
                continue
            u = max(0.0, min(1.0, ((q.x - a.x) * dx + (q.y - a.y) * dy) / uz2))
            ex, ey = a.x + u * dx - q.x, a.y + u * dy - q.y
            if ex * ex + ey * ey < r * r:
                return False
    return True


def cek(pcb, tablo):
    b = pcbnew.LoadBoard(pcb)
    kat = {pcbnew.LayerName(i): i
           for i in b.GetEnabledLayers().CuStack()}
    # ESKI IZ SILMEK YOK. b.Remove() bir izde surec cokuyor
    # (PCB_TEXT'te de ayni). Gerek de yok: bu arac TEMIZ kartta
    # calisiyor, pcb_kur'dan hemen sonra, yonlendiriciden once.
    silinen = 0
    kodlar = {}
    for fp in b.Footprints():
        for p in fp.Pads():
            n = p.GetNetname()
            if n and n not in kodlar:
                kodlar[n] = p.GetNetCode()
    n = 0
    rapor = []
    atlanan = set()
    cizilen = set()
    for ag, kayit in sorted(tablo.items()):
        gen, katman = kayit[0], kayit[1]
        zincir = kayit[2] if len(kayit) > 2 else None
        pts = pedler(b, ag)
        if len(pts) < 2:
            continue
        kod = kodlar.get(ag, 0)
        toplam = 0.0
        # HEPSI YA DA HICBIRI, AG BASINA.
        # Once parca parca cizip cakisani atliyordum; sonuc yarim
        # zincir oldu. DRN_A'da dort pedin ucu baglandi, biri acikta
        # kaldi, ve o ag ne elle ne yonlendiriciyle tamamlandi cunku
        # yonlendirici bu aglari atliyor. Yarim elle-cizim hic
        # cizmemekten kotu.
        # Liste her ag icin SIFIRLANMALI — once disarida biraktim ve
        # bir ag bozulunca ondan sonraki hepsi cizilmedi.
        adaylar = []
        # SIMETRIK AGLARDA TOPOLOJI DE SIMETRIK OLMALI.
        # En kisa agac (Prim) iki kolda farkli topoloji secebiliyor:
        # DRN_A ile DRN_B ayni geometride olmasina ragmen 65.8 ve
        # 77.2 mm cikti, cunku agac birinde once cihazlari sonra
        # trafoyu, otekinde tersini bagladi. Cozum sirayi sabitlemek:
        # pedler HEDEFE (listedeki son parca tipine) olan uzakliga
        # gore siralanip zincir halinde baglaniyor. Ayni kural iki
        # kolda ayni topolojiyi veriyor.
        if zincir:
            hedef = next((q for q in pts if q[2].startswith(zincir)), None)
            if hedef:
                pts = sorted(pts, key=lambda q: -math.dist(q[:2], hedef[:2]))
                kenarlar = [(i, i + 1) for i in range(len(pts) - 1)]
            else:
                kenarlar = agac(pts)
        else:
            kenarlar = agac(pts)
        for i, j in kenarlar:
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(pts[i][0], pts[i][1]))
            t.SetEnd(pcbnew.VECTOR2I(pts[j][0], pts[j][1]))
            t.SetWidth(int(gen * MM))
            t.SetLayer(kat.get(katman, pcbnew.F_Cu))
            t.SetNetCode(kod)
            # PEDIN USTUNDEN GECEN IZI CIZME.
            # Arac iki ped arasina duz cizgi cekiyor ve hicbir seyin
            # etrafindan dolasmiyor. Yogun kartta bu, baska bir agin
            # pedini kesiyor: A'da 10 kisa devre, 92 maske koprusu.
            # Boyle bir izi cizmektense o agi yonlendiriciye
            # birakmak dogru — simetriyi kaybederiz ama kisa devre
            # kalmaz, ve o agin koridoru kat planinda acilinca
            # burasi kendiliginden calisir.
            adaylar.append(t)
            toplam += math.dist(pts[i][:2], pts[j][:2]) / MM
        if all(temiz(b, t, ag) for t in adaylar):
            for t in adaylar:
                b.Add(t)
                n += 1
            rapor.append((ag, toplam, len(pts)))
            cizilen.add(ag)
        else:
            atlanan.add(ag)
    # CIZILENLERIN LISTESINI YAZ.
    # ses_oku bu aglari yonlendiriciden almiyor. Ama elle_cek bir agi
    # cizemezse (yol baska pedin ustunden geciyorsa) ve ses_oku yine
    # de atlarsa, o ag HIC cekilmiyor. Atlanacak liste sabit degil,
    # gercekten cizilenler olmali.
    with open(os.path.join(os.path.dirname(os.path.abspath(pcb)),
                           "elle.txt"), "w") as fh:
        fh.write("\n".join(sorted(cizilen)))
    b.Save(pcb)
    if atlanan:
        rapor.append(("ATLANAN", len(atlanan), 0))
    return silinen, n, rapor


if __name__ == "__main__":
    pcb = sys.argv[1] if len(sys.argv) > 1 else "D_pa/dogrudan_sdr_D.kicad_pcb"
    kart = "D"
    for k in ("A", "C", "D"):
        if f"_{k.lower()}" in pcb or f"_{k}." in pcb:
            kart = k
    s, n, rapor = cek(pcb, TABLOLAR[kart])
    print(f"{os.path.basename(pcb)}: {s} eski iz silindi, {n} iz cekildi")
    for ag, uz, p in rapor:
        print(f"   {ag:9s} {uz:6.1f} mm  ({p} ped)")
