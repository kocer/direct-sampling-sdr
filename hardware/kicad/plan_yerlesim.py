#!/usr/bin/env python3
"""Kat planina gore yerlesim.

    python3 plan_yerlesim.py A

Uc asama:
  1 CAPALAR  kat_plani.py'deki acik konumlar (SMA'lar kenarda, FPGA
    merkezde, saat iki ADC'nin ortasinda). Bunlar sabit.
  2 ZINCIRLER netlist'ten IZLENEREK. Bir SMA'dan ADC'ye giden yol
    graf uzerinde bulunur ve aradaki parcalar o dogru boyunca sirayla
    dizilir. Referans elle yazilmiyor — sema degisince yerlesim de
    kendiliginden dogru kaliyor.
  3 KALANLAR bagli olduklari parcanin dibine. Ayristirma kondansatoru
    besledigi entegrenin GUC BACAGINA, otekiler en cok bagli olduklari
    komsunun yanina.
"""
import math, os, re, subprocess, sys
from collections import deque
import pcbnew
import kat_plani as KP

MM = 1000000
ATLA = re.compile(r"^(GND|\+|VIN_PROT|CHASSIS|GND_HDR|GND_STRAP|GND_MODE)")


def netlist(dizin, proj):
    out = f"/tmp/pl_{proj}.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 dizin, proj + ".kicad_sch"),
                    "-o", out, "--format", "kicadsexpr"],
                   capture_output=True, check=True)
    t = open(out, encoding="utf-8").read()
    padnet = {}
    for m in re.finditer(
            r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', t, re.S):
        ag, body = m.groups()
        for ref, pad in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body):
            padnet.setdefault(ref, {})[pad] = ag
    return padnet


def komsuluk(padnet):
    """ref -> {komsu ref} (guc/toprak aglari haric)."""
    ag_uye = {}
    for ref, padlar in padnet.items():
        for ag in set(padlar.values()):
            if not ATLA.match(ag):
                ag_uye.setdefault(ag, set()).add(ref)
    k = {}
    for ag, uyeler in ag_uye.items():
        if len(uyeler) > 12:        # cok genis yol: komsuluk saymaz
            continue
        for a in uyeler:
            k.setdefault(a, set()).update(uyeler - {a})
    return k


def yol_bul(kom, bas, son):
    """bas'tan son'a en kisa parca yolu (referans listesi)."""
    if bas not in kom:
        return []
    onceki = {bas: None}
    q = deque([bas])
    while q:
        u = q.popleft()
        if u == son:
            break
        for v in sorted(kom.get(u, ())):
            if v not in onceki:
                onceki[v] = u
                q.append(v)
    if son not in onceki:
        return []
    yol, u = [], son
    while u is not None:
        yol.append(u)
        u = onceki[u]
    return list(reversed(yol))


def koy(fps, ref, x, y, aci=0):
    fp = fps.get(ref)
    if fp is None:
        return False
    fp.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
    if aci:
        fp.SetOrientationDegrees(aci)
    return True


def zincir_koy(fps, kom, bas, son, x0, y0, x1, y1, kondu):
    """bas ile son arasindaki parcalari dogru boyunca sirayla diz."""
    yol = yol_bul(kom, bas, son)
    ara = [r for r in yol[1:-1] if r not in kondu and r in fps]
    if not ara:
        return 0
    n = len(ara)
    for i, ref in enumerate(ara):
        t = (i + 1) / (n + 1)
        # cift sayida parca varsa hafifce ayir: seri direnc ciftleri
        # ust uste binmesin
        sap = 2.2 if (i % 2 and n > 2) else (-2.2 if n > 2 else 0)
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        koy(fps, ref, x0 + dx * t + nx * sap, y0 + dy * t + ny * sap)
        kondu.add(ref)
    return len(ara)


def guc_bacagi(fp, ag_adi):
    """Bir entegrenin o raya bagli ilk bacaginin konumu (mm)."""
    for pad in fp.Pads():
        if pad.GetNetname() == ag_adi:
            p = pad.GetPosition()
            return p.x / MM, p.y / MM
    return None


def kalanlari_koy(fps, padnet, kom, kondu, en, boy):
    """Kondu disinda kalanlari: ayristirma kondansatorleri besledikleri
    entegrenin guc bacagina, otekiler en cok bagli komsularinin yanina."""
    yerlesik = {r: True for r in kondu}
    for tur in range(6):
        yeni = 0
        for ref in sorted(fps):
            if ref in yerlesik:
                continue
            padlar = padnet.get(ref, {})
            aglar = set(padlar.values())
            # ayristirma: iki bacakli, biri GND biri ray
            hedef = None
            if ref.startswith("C") and len(padlar) == 2 and "GND" in aglar:
                ray = next((a for a in aglar if a != "GND"), None)
                aday = [r for r in kom.get(ref, ()) if r in yerlesik]
                if not aday and ray:
                    aday = [r for r, pn in padnet.items()
                            if r in yerlesik and r.startswith("U")
                            and ray in pn.values()]
                if aday:
                    ic = max(aday, key=lambda r: sum(
                        1 for v in padnet[r].values() if v == ray))
                    p = guc_bacagi(fps[ic], ray) if ray else None
                    if p is None:
                        q = fps[ic].GetPosition()
                        p = (q.x / MM, q.y / MM)
                    hedef = (p[0] + 2.6, p[1] + 2.6)
            if hedef is None:
                aday = [r for r in kom.get(ref, ()) if r in yerlesik]
                if not aday:
                    continue
                xs = [fps[r].GetPosition().x / MM for r in aday]
                ys = [fps[r].GetPosition().y / MM for r in aday]
                hedef = (sum(xs) / len(xs), sum(ys) / len(ys) + 4.0)
            koy(fps, ref, min(max(hedef[0], 4), en - 4),
                min(max(hedef[1], 4), boy - 4))
            yerlesik[ref] = True
            yeni += 1
        if not yeni:
            break
    # hic baglantisi bulunamayanlar: alt kenara
    bos = [r for r in sorted(fps) if r not in yerlesik]
    for i, ref in enumerate(bos):
        koy(fps, ref, 6 + (i % 40) * 4.5, boy - 6 - (i // 40) * 4.5)
    return len(bos)


KARTLAR = {
    "A": ("A_main", "dogrudan_sdr_A", 185, 180),
    "C": ("C_rf", "dogrudan_sdr_C", 345, 215),
    "D": ("D_pa", "dogrudan_sdr_D", 265, 200),
}


def uygula(kart):
    dizin, proj, en, boy = KARTLAR[kart]
    HERE = os.path.dirname(os.path.abspath(__file__))
    pcb = os.path.join(HERE, dizin, proj + ".kicad_pcb")
    b = pcbnew.LoadBoard(pcb)
    fps = {fp.GetReference(): fp for fp in b.Footprints()}
    padnet = netlist(dizin, proj)
    kom = komsuluk(padnet)
    kondu = set()

    capa = {"A": KP.A_CAPA, "C": KP.C_CAPA, "D": KP.D_CAPA}[kart]
    for ref, (x, y, aci) in capa.items():
        if koy(fps, ref, x, y, aci):
            kondu.add(ref)

    zincir = 0
    if kart == "A":
        # dort alis zinciri: SMA'dan ADC'ye, DUZ ve BIREBIR AYNI
        for (kanal, ysma, tref), (sma, adc) in zip(
                KP.A_RX_KANAL, [("J20", "U20"), ("J21", "U20"),
                                ("J22", "U21"), ("J23", "U21")]):
            zincir += zincir_koy(fps, kom, sma, adc, 10, ysma, 56, ysma, kondu)
        # dort veris zinciri: DAC'tan SMA'ya
        for (n, tref, xsma), dac in zip(KP.A_TX_KANAL,
                                        ["U30", "U30", "U31", "U31"]):
            zincir += zincir_koy(fps, kom, dac, f"J{29 + int(n)}",
                                 xsma + 8, 140, xsma, 152, kondu)
    elif kart == "C":
        # dort kanal x yedi bolum; kanal 1 aciktan, otekiler ayni
        for ch, ybase in enumerate(KP.C_KANAL_Y, start=1):
            for poz in range(1, 8):
                ref = f"K{ch}{poz}"
                if koy(fps, ref, KP.C_BOLUM_X + (poz - 1) * KP.C_BOLUM_ADIM,
                       ybase):
                    kondu.add(ref)
            zincir += zincir_koy(fps, kom, f"J{ch}", f"K{ch}1",
                                 10, ybase, KP.C_BOLUM_X - 12, ybase, kondu)
    elif kart == "D":
        zincir += zincir_koy(fps, kom, "J10", "U11", 10, 30, 44, 30, kondu)
        zincir += zincir_koy(fps, kom, "T11", "T20", 116, 30, 208, 38, kondu)

    bos = kalanlari_koy(fps, padnet, kom, kondu, en, boy)

    # dis hat guncelle
    for d in list(b.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            b.Remove(d)
    for a, bb, c, dd in ((0, 0, en, 0), (en, 0, en, boy),
                         (en, boy, 0, boy), (0, boy, 0, 0)):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(int(a * MM), int(bb * MM)))
        s.SetEnd(pcbnew.VECTOR2I(int(c * MM), int(dd * MM)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(int(0.1 * MM))
        b.Add(s)
    b.Save(pcb)

    # Olcum AYRI betikte (olc.py): ayni surecte ikinci LoadBoard
    # bozuk nesne donduruyor.
    print(f"{kart}: capa {len(capa)}, zincir {zincir}, bagsiz {bos}, "
          f"{en}x{boy} mm")


if __name__ == "__main__":
    for k in (sys.argv[1:] or ["A", "C", "D"]):
        uygula(k)
