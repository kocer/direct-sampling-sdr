#!/usr/bin/env python3
"""Specctra SES -> KiCad PCB. Yonlendiricinin cizdigi yollari geri al.

    python3 ses_oku.py A_main/dogrudan_sdr_A.kicad_pcb /tmp/A.ses

NEDEN KENDIMIZ YAZIYORUZ: dsn_yaz.py ile ayni sebep. pcbnew'un
ImportSpecctraSES'i kart baglamini GUI'den aliyor, bagimsiz python'da
sessizce basarisiz oluyor. Disari kendimiz yaziyorsak iceri de
kendimiz okuyacagiz.

SES'in uc tuzagi:

1 Y EKSENI TERS, dsn_yaz.py'deki gibi. Cevirmeyi unutursan butun
  yollar kartin aynasinda cikiyor ve hicbir ped tutmuyor.

2 KOORDINAT BIRIMI BASLIKTA. (resolution um 10) demek "sayilar
  1/10 mikron". Sabit varsayip mikron kabul edersen kart 10 kat
  buyuyor.

3 wire'in path'i ZINCIR. (path LAYER WIDTH x1 y1 x2 y2 x3 y3 ...)
  tek bir yol degil, ardisik noktalar; her ardisik cift bir iz
  parcasi. Sadece ilk ve son noktayi alirsan koseler kaybolur ve
  yol pedlerin uzerinden gecer.

Eski izler SILINIYOR: yonlendirici tam cozum uretiyor, yarisini
tutup yarisini eklemek kisa devre demek.
"""
import os
import re
import sys

import pcbnew
import dsn_yaz

MM = 1e6


def coz(metin):
    """S-ifadeyi ic ice listelere cevir."""
    jeton = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', metin)
    yigin, gecerli = [], []
    for j in jeton:
        if j == "(":
            yigin.append(gecerli)
            gecerli = []
        elif j == ")":
            ust = yigin.pop()
            ust.append(gecerli)
            gecerli = ust
        else:
            gecerli.append(j.strip('"'))
    return gecerli


def bul(dugum, ad):
    """Alt dugumleri ada gore don."""
    for d in dugum:
        if isinstance(d, list) and d and d[0] == ad:
            yield d


def ilk(dugum, ad):
    return next(bul(dugum, ad), None)


def olcek(kok):
    """(resolution um 10) -> nm carpani."""
    r = ilk(kok, "resolution")
    if not r:
        return 1000.0
    birim, bolen = r[1], float(r[2])
    taban = {"um": 1000.0, "mm": 1e6, "inch": 25.4e6, "mil": 25400.0}
    return taban.get(birim, 1000.0) / bolen


def katman_haritasi(board):
    h = {}
    for i in range(pcbnew.PCB_LAYER_ID_COUNT):
        if board.IsLayerEnabled(i):
            h[pcbnew.LayerName(i)] = i
            h[board.GetLayerName(i)] = i
    return h


def temizle(board):
    """ESKI IZ SILINMIYOR — board.Remove() surece cokuyor.

    Gerek de yok. Akis su: pcb_kur karti izsiz kuruyor, elle_cek
    simetrik aglari ciziyor, yonlendirici gerisini yapiyor, bu arac
    onu ekliyor. Silinecek bir sey yok, ve elle cizilenler zaten
    KALMALI.
    """
    return 0


# Yonlendiriciden ICE ALINMAYACAK aglar: simetrisi elle kurulanlar.
# freerouting'e `(type protect)` ile soylemeyi denedim, kabul etmedi.
# Bunun yerine router her seyi cizsin, biz onun bu aglar icin
# cizdigini almayalim; elle_cek.py sonra kendi izini koyuyor.
ELLE = {"G10", "G11", "G12", "G13", "DRN_A", "DRN_B",
        "D2_DA", "D2_DB", "D2_GA_S", "D2_GB_S"}
# A karti: dort alis zinciri. C karti: dort kanalin girisi.
for _k in ("A1", "B1", "A2", "B2"):
    ELLE |= {f"RF_{_k}", f"SEC_{_k}_P", f"SEC_{_k}_N",
             f"VIN_{_k}_P", f"VIN_{_k}_N"}
for _k in range(1, 5):
    ELLE |= {f"ANT{_k}", f"RX{_k}_ANT", f"RX{_k}_B1_IN", f"RX{_k}_OUT"}


def elle_cizilenler(pcb):
    """elle_cek.py'nin GERCEKTEN cizdigi aglar.

    Sabit liste yanlisti: elle_cek bir agi cizemeyince (yol baska
    pedin ustunden geciyor) ve biz yine de atlayinca, o ag hicbir
    yerde cekilmiyordu. Atlanacak olan, cizilmis olan.
    """
    import os
    d = os.path.join(os.path.dirname(os.path.abspath(pcb)), "elle.txt")
    try:
        return {s.strip() for s in open(d) if s.strip()}
    except OSError:
        return set()


def oku(pcb, ses, elle=None):
    if elle is None:
        elle = elle_cizilenler(pcb)
    board = pcbnew.LoadBoard(pcb)
    kok = coz(open(ses, encoding="utf-8", errors="replace").read())
    # kok = [["session", ...]]
    oturum = kok[0] if kok and isinstance(kok[0], list) else kok
    rotalar = ilk(oturum, "routes")
    if rotalar is None:
        raise SystemExit("SES icinde 'routes' yok — yonlendirme bitmemis")
    k = olcek(rotalar)
    kat = katman_haritasi(board)
    # AG KODLARINI BASTA TOPLA. board.GetNetInfo().GetNetItem() sonra
    # sarmalanmamis nesne donduruyor (GetNetCode() yok) — pcbnew'un
    # surec icinde bozulan proxy'lerinden biri daha. Pedlerden
    # okumak hem guvenli hem yeterli.
    kodlar = {}
    for fp in board.Footprints():
        for p in fp.Pads():
            n = p.GetNetname()
            if n and n not in kodlar:
                kodlar[n] = p.GetNetCode()

    silinen = temizle(board)
    iz = via = atlanan = 0
    cikis = ilk(rotalar, "network_out")
    atlanan_ag = 0
    for net in bul(cikis or [], "net"):
        ad = net[1]
        if ad in elle:
            atlanan_ag += 1
            continue
        kod = kodlar.get(ad, 0)
        if not kod:
            atlanan += 1
        for w in bul(net, "wire"):
            p = ilk(w, "path")
            if not p:
                continue
            lay = kat.get(p[1])
            if lay is None:
                atlanan += 1
                continue
            gen = int(float(p[2]) * k)
            sayi = [float(v) for v in p[3:]]
            nokta = [(sayi[i], sayi[i + 1]) for i in range(0, len(sayi) - 1, 2)]
            # ZINCIRIN HER PARCASI. Ilk-son almak koseleri yutuyor.
            for (x1, y1), (x2, y2) in zip(nokta, nokta[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(int(x1 * k), int(-y1 * k)))
                t.SetEnd(pcbnew.VECTOR2I(int(x2 * k), int(-y2 * k)))
                t.SetWidth(gen)
                t.SetLayer(lay)
                t.SetNetCode(kod)
                board.Add(t)
                iz += 1
        for v in bul(net, "via"):
            x, y = float(v[2]), float(v[3])
            u = pcbnew.PCB_VIA(board)
            u.SetPosition(pcbnew.VECTOR2I(int(x * k), int(-y * k)))
            # VIA OLCUSU DSN ILE AYNI OLMALI. Yonlendirici
            # dsn_yaz.VIA_CAP capinda planliyor; burada daha buyugunu
            # kurarsak planlanan boslugu yeriz. A kartinda BGA
            # kacisi 500 um via + 127 um bosluga gore hesaplandi.
            u.SetWidth(int(dsn_yaz.VIA_CAP / 1000 * MM))
            u.SetDrill(int(dsn_yaz.VIA_DELIK / 1000 * MM))
            u.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            u.SetNetCode(kod)
            board.Add(u)
            via += 1
    # DOKUMLERI DOLDUR. Yonlendirici toprak duzlemini gormuyor;
    # QFN'lerin acik termal pedleri (U30/U31/U51 ped 17) yola degil
    # dokume baglaniyor. Doldurmadan DRC onlari "bagsiz" sayiyor ve
    # gercek eksikler bu gurultunun icinde kayboluyor.
    # ONCE BAGLANTI HARITASI. BuildConnectivity() cagirmadan
    # ZONE_FILLER True donuyor ama dokumler BOS kaliyor: doldurucu
    # hangi pedin hangi aga ait oldugunu bilmiyor.
    # SMD PEDE TAM BAKIR, DELIKLI PEDE TERMAL ROLE.
    #
    # Once hepsi FULL idi. SMD tarafinda dogru: varsayilan termal
    # role dort ince kolla bagliyor ve PA'nin 6.67 A donus akimi
    # ile cihaz kulaklarindan gelen isi icin o kollar yetmiyordu
    # (19 starved_thermal).
    #
    # Ama gerekce "bu kartlar firinda dizilecek" idi ve DELIKLI
    # parcalar icin bu DOGRU DEGIL — onlar elle lehimleniyor.
    # Olculdu, GND'ye bagli delikli ped sayisi:
    #     A  16   (7'si >= 1.5 mm)   XT60, JTAG, basliklar
    #     C 220   (28'i >= 1.5 mm)   24 elle sarilan toroid, basliklar
    #     D  50   (44'u >= 1.5 mm)   470uF elektrolitikler, trafo orta
    #                                uclari, "sonraki PA" konnektoru
    # C'deki toroidler elde sariliyor, firina hic girmiyorlar. Tam
    # bakirla her biri 82000 mm2'lik dokume dogrudan bagli: havyayla
    # o pedi lehim sicakligina getirmek cok guc, zorlayan pedi
    # kaldiriyor.
    #
    # ZONE_CONNECTION_THT_THERMAL tam bunun icin: SMD'de FULL,
    # delikli pedde termal role. Iki gereksinim de karsilaniyor.
    for z in board.Zones():
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
    board.BuildConnectivity()
    doldurucu = pcbnew.ZONE_FILLER(board)
    doldurucu.Fill(board.Zones())
    board.Save(pcb)
    return silinen, iz, via, atlanan + atlanan_ag


if __name__ == "__main__":
    pcb, ses = sys.argv[1], sys.argv[2]
    s, i, v, a = oku(pcb, ses)
    print(f"{os.path.basename(pcb)}: {s} eski iz silindi, "
          f"{i} iz + {v} via eklendi" + (f", {a} atlandi" if a else ""))
