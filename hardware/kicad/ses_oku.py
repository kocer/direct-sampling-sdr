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
    n = 0
    for t in list(board.GetTracks()):
        board.Remove(t)
        n += 1
    return n


def oku(pcb, ses):
    board = pcbnew.LoadBoard(pcb)
    kok = coz(open(ses, encoding="utf-8", errors="replace").read())
    # kok = [["session", ...]]
    oturum = kok[0] if kok and isinstance(kok[0], list) else kok
    rotalar = ilk(oturum, "routes")
    if rotalar is None:
        raise SystemExit("SES icinde 'routes' yok — yonlendirme bitmemis")
    k = olcek(rotalar)
    kat = katman_haritasi(board)
    aglar = board.GetNetInfo()

    silinen = temizle(board)
    iz = via = atlanan = 0
    cikis = ilk(rotalar, "network_out")
    for net in bul(cikis or [], "net"):
        ad = net[1]
        ni = aglar.GetNetItem(ad)
        kod = ni.GetNetCode() if ni else 0
        if ni is None:
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
            u.SetWidth(int(0.6 * MM))
            u.SetDrill(int(0.3 * MM))
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
    board.BuildConnectivity()
    doldurucu = pcbnew.ZONE_FILLER(board)
    doldurucu.Fill(board.Zones())
    board.Save(pcb)
    return silinen, iz, via, atlanan


if __name__ == "__main__":
    pcb, ses = sys.argv[1], sys.argv[2]
    s, i, v, a = oku(pcb, ses)
    print(f"{os.path.basename(pcb)}: {s} eski iz silindi, "
          f"{i} iz + {v} via eklendi" + (f", {a} atlandi" if a else ""))
