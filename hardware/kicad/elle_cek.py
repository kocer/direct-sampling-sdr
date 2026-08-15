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
    # ITME-CEKME KOLLARI: DENGELI TEE.
    #
    # Olculdu: T31'in DRN_A pedinden Q10'a 44.8 mm, Q11'e 33.2 mm.
    # Iki KOL birbirinin aynasi (A: 44.8/33.2, B: 33.2/44.8) yani
    # kollar arasi simetri TAM — ama KOL ICINDEKI iki paralel cihaz
    # esit degil, 11.6 mm fark var. Paralel guc MOSFET'lerinde drain
    # yolu farkli olursa akim paylasimi bozulur: kisa yoldaki cihaz
    # daha cok ceker, daha cok isinir, Rds(on) artar. A sinifinda
    # cihaz basina 58 W dagilirken bu fark hangi cihazin once
    # gidecegini belirler.
    #
    # Bu yerlesimde geometrik olarak esitlenemez (dort cihaz bir
    # sirada, trafo bir yanda). Cozum yonlendirmede: trafonun
    # pedinden IKI CIHAZIN TAM ORTASINA tek bir iz, oradan iki yana
    # SIMETRIK ayrilma. Tee noktasi iki drain pedinin orta noktasi
    # oldugu icin iki dal MATEMATIKSEL OLARAK esit uzunlukta.
    # 2.2 -> 1.2 mm: kol basina iki cihaz paralel, yani bu iz
    # 6.67 A degil 3.33 A tasiyor (2 oz'da 0.79 mm yetiyor).
    # Ag sinifiyla ayni genislik olmali, yoksa elle cizilen dal
    # ile yonlendiricinin cektigi govde arasinda basamak olur.
    "DRN_A": (1.2, "F.Cu", "T", "tee"),
    "DRN_B": (1.2, "F.Cu", "T", "tee"),
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


def temiz(b, iz, ag, bosluk=300000):
    """Iz baska bir agin pedine BOSLUK KADAR yaklasiyor mu?

    ONCEKI SURUM PEDI DAIRE SANIYORDU VE DAIREYI KUCUK ALIYORDU.
    Yaricap "max(en, boy) / 2" idi. Bir dikdortgenin KOSESI merkeze
    hypot(en, boy) / 2 uzaklikta — yani gercek uzanim %41'e kadar
    eksik sayiliyordu. TO-247'nin 2.5 x 4.5 mm pedinde fark
    2.250 yerine 2.574 mm.

    Bedeli olculdu: D kartinda DRN_A izi Q10'un KAPI pedinin uzerine
    35 mikron BINIYORDU. 50 V'luk dren rayi ile 100 W'lik bir gucun
    kapisi arasinda kisa devre; parca calisir calismaz olur ve
    sebebi kartta gozle gorunmez cunku ortusme kosede ve mikron
    mertebesinde. Tee kaymasi arayan dongu (kay = 5..19 mm) bu yolu
    "temiz" bulup kabul etmisti.

    Iki degisiklik:
      1 Pedin GERCEK sekli kullaniliyor (pcbnew'un kendi carpisma
        testi; dairesel, oval, dikdortgen, dondurulmus, hepsi).
      2 Sadece ortusmeye degil, BOSLUGA bakiliyor. Ortusmeyen ama
        50 mikron kalan bir iz de uretilemez.
    """
    kat = iz.GetLayer()
    try:
        iz_sekil = iz.GetEffectiveShape(kat)
    except Exception:
        iz_sekil = None
    a, c = iz.GetStart(), iz.GetEnd()
    yari = iz.GetWidth() / 2
    for fp in b.Footprints():
        for p in fp.Pads():
            if p.GetNetname() == ag or not p.GetNetname():
                continue
            if not p.IsOnLayer(kat):
                continue
            if iz_sekil is not None:
                try:
                    if iz_sekil.Collide(p.GetEffectiveShape(kat), int(bosluk)):
                        return False
                    continue
                except Exception:
                    pass
            # yedek yol: kosegeni kapsayan daire (max degil hypot)
            q = p.GetPosition()
            r = math.hypot(p.GetSizeX(), p.GetSizeY()) / 2 + yari + bosluk
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
        kip = kayit[3] if len(kayit) > 3 else None
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
        if kip == "tee" and zincir:
            # DENGELI TEE: kok (trafo pedi) -> yapraklarin ORTASI ->
            # her yaprak. Orta nokta iki yapraga esit uzaklikta
            # oldugu icin iki dal birebir ayni uzunlukta cikiyor;
            # ortak govde ikisinde de ayni, yani toplam yollar da
            # esit. Meander gerekmiyor.
            # YAPRAK = CIHAZ PEDI. Bu agda cihazlarin disinda baska
            # pedler de var (geri besleme direncinin ucu gibi);
            # onlari ortalamaya katmak tee noktasini kaydiriyor ve
            # simetriyi bozuyordu (olculdu: J 8.2 yerine 19.4'e
            # kaydi ve iki dal esitsizlesti).
            yaprak = [k for k, q in enumerate(pts) if q[2].startswith("Q")]
            if len(yaprak) >= 2:
                jx = sum(pts[k][0] for k in yaprak) // len(yaprak)
                jy = sum(pts[k][1] for k in yaprak) // len(yaprak)
                # TEE NOKTASI PIN SIRASININ DISINDA.
                # TO-247'nin uc bacagi AYNI y'de, 5.08 mm arayla:
                # iki drain pedini birlestiren yatay cizgi aradaki
                # KAPI ve KAYNAK pedlerinin uzerinden geciyor
                # (olculdu: Q10 ped 1, G10). Tee noktasini trafo
                # tarafina 8 mm kaydiriyoruz; iki dal hala jx
                # ekseninde simetrik, yani esit uzunlukta.
                kok = next((k for k, q in enumerate(pts)
                            if q[2].startswith(zincir)), None)
                yon = 1 if (kok is not None and pts[kok][1] > jy) else -1
                # KAYMA MIKTARINI ARA, TAHMIN ETME.
                # 8 mm denendi: tam servo direnci sirasina denk
                # geldi (R244, y=17.2). 6 mm denendi: cihazin kendi
                # kapi pedinin 2.4 mm yakinindan geciyor. Aradaki
                # bosluklar 1-2 mm; sabit bir sayi yazmak yerine
                # temizini buluyoruz. jx degismedigi icin iki dal
                # her kaymada esit uzunlukta kaliyor.
                jy0 = jy
                for kay in range(5, 20):
                    jy = jy0 + yon * int(kay * MM)
                    tamam = True
                    for k in yaprak:
                        tt = pcbnew.PCB_TRACK(b)
                        tt.SetStart(pcbnew.VECTOR2I(int(jx), int(jy)))
                        tt.SetEnd(pcbnew.VECTOR2I(pts[k][0], pts[k][1]))
                        tt.SetWidth(int(gen * MM))
                        if not temiz(b, tt, ag):
                            tamam = False
                            break
                    if tamam:
                        break
                pts = list(pts) + [(jx, jy, "TEE", "0")]
                j = len(pts) - 1
                # GOVDEYI CIZMIYORUZ, SADECE IKI DALI.
                # Trafodan tee noktasina giden govde kalabalik
                # bolgeden geciyor (akim olcum yukselteci tam
                # aralarinda) ve duz cizgiyle cizilemiyor. Onu
                # yonlendirici cekiyor: cizilen iki dal aynı agin
                # korumali bakiri, yonlendirici trafonun pedini o
                # bakira bagliyor. Simetriyi belirleyen sey zaten
                # dallar — govde ikisinde de ORTAK.
                kenarlar = [(j, k) for k in yaprak]
            else:
                kenarlar = agac(pts)
        elif zincir:
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


# ------------------------------------------------------------------ BGA kacisi
#
# ** 0.8 mm ADIMLI BGA'DA KACISI YONLENDIRICIYE BIRAKMA. **
#
# ECP5 CABGA256: 16x16 top, 0.8 mm adim, 0.32 mm top pedi. Dis iki
# halka (112 top) ust katmandan yatay kacabiliyor; ic 144 topun
# kacisi ancak KOSEGEN bosluktan via ile mumkun:
#     kosegen bosluk merkezi ... en yakin top KENARI
#         0.8*sqrt(2)/2 - 0.32/2 = 0.406 mm
#     via (0.50 dis cap) + boslu (0.127) = 0.377 mm    -> 29 um pay
# Yani yer VAR ama sadece 29 um. Yonlendirici bu yerlestirmeyi arama
# ile buluyor: her aday via icin alti katmandaki her komsuyu
# sorguluyor. Olculdu (jstack): tek is parcacikli MazeShoveTraceAlgo
# 2.5 saat boyunca %97 CPU ile bu isi yapiyor ve bitiremiyor.
#
# Oysa bu is ARAMA GEREKTIRMIYOR: hangi topun hangi kosegen bosluga
# ineceği geometriden belli. Via'yi biz koyuyoruz, yonlendiriciye
# "via'dan hedefe" diye cok daha kolay bir problem kaliyor.
#
# Olculdu, ic 144 topun dagilimi:
#     60 sinyal, 21 guc, 15 toprak, 4 bos
# Guc ve toprak toplari zaten sadece duzleme inmek istiyor; onlarin
# via'si da buradan geliyor ve yonlendiricinin isi 36 kalem azaliyor.
#
# ATAMA TEK ANLAMLI: (i,j) indisli top DISA dogru kosegen bosluga
# gidiyor, yani sol yaridaki i-0.5'e, sag yaridaki i+0.5'e. Bu
# eşleme birebir — iki top ayni bosluga talip olamiyor.
BGA_ADIM = 0.8
BGA_HALKA = 2          # dis iki halka ust katmandan kaciyor
BGA_VIA = 0.50         # dis cap, mm (pcb_kur.ASGARI_DELIK + 2x0.10 halka)
BGA_DELIK = 0.30
BGA_IZ = 0.15          # top pedinden via'ya giden kisa sap


def bga_kacis(pcb, ref="U10"):
    """BGA'nin ic toplarindan kosegen bosluga via + kisa sap ciz."""
    b = pcbnew.LoadBoard(pcb)
    fp = next((f for f in b.Footprints() if f.GetReference() == ref), None)
    if fp is None:
        return 0, 0
    kat = {pcbnew.LayerName(i): i for i in b.GetEnabledLayers().CuStack()}
    ust = list(kat.values())[0]
    alt = list(kat.values())[-1]
    c = fp.GetPosition()
    # zaten cizilmis mi (zincir iki kez kosarsa via birikmesin)
    varolan = {(v.GetPosition().x, v.GetPosition().y)
               for v in b.GetTracks() if isinstance(v, pcbnew.PCB_VIA)}
    n_via = n_iz = 0
    for pad in sorted(fp.Pads(), key=lambda p: p.GetNumber()):
        ag = pad.GetNetname()
        if not ag or "unconnected" in ag:
            continue
        q = pad.GetPosition()
        dx = (q.x - c.x) / MM
        dy = (q.y - c.y) / MM
        # halka indisi: merkezden kacinci sira
        ix = round(abs(dx) / BGA_ADIM - 0.5)
        iy = round(abs(dy) / BGA_ADIM - 0.5)
        halka = 7 - max(ix, iy)          # 0 = en distaki halka
        if halka < BGA_HALKA:
            continue                      # dis halkalar ustten kaciyor
        vx = q.x + int((BGA_ADIM / 2 * MM) * (1 if dx >= 0 else -1))
        vy = q.y + int((BGA_ADIM / 2 * MM) * (1 if dy >= 0 else -1))
        if (vx, vy) in varolan:
            continue
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(vx, vy))
        v.SetWidth(int(BGA_VIA * MM))
        v.SetDrill(int(BGA_DELIK * MM))
        v.SetLayerPair(ust, alt)
        v.SetNetCode(pad.GetNetCode())
        b.Add(v)
        varolan.add((vx, vy))
        n_via += 1
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(q)
        t.SetEnd(pcbnew.VECTOR2I(vx, vy))
        t.SetWidth(int(BGA_IZ * MM))
        t.SetLayer(ust)
        t.SetNetCode(pad.GetNetCode())
        b.Add(t)
        n_iz += 1
    b.Save(pcb)
    return n_via, n_iz


# BGA'SI OLAN KARTLAR: ayak izi referansi -> kacis cizilecek mi
BGA_KARTLARI = {"A": "U10"}


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
    if kart in BGA_KARTLARI:
        nv, ni = bga_kacis(pcb, BGA_KARTLARI[kart])
        print(f"   BGA kacisi {nv} via + {ni} sap ({BGA_KARTLARI[kart]})")
