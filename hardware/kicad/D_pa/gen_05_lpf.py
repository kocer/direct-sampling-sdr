#!/usr/bin/env python3
"""05_lpf: cikis harmonik filtreleri, 7 bant. Kaynak: ../../PA_TASARIM.md §7."""
import json, os, math
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

# LPF bankasi G2RL-2 kullaniyor, G6K DEGIL. G6K sinyal rolesi
# (1 A / 30 VDC); 100 W'ta hat akimi 1.4 A, tepe gerilim 100 V.
# Ustelik G6K sembolunun pinleri 1..8, G2RL-2 ayak izininki
# IEC (11/12/14/21/22/24/A1/A2) — isimler tutmayinca yedi
# rolenin 56 pedi de bagsiz kaldi ve ERC bunu goremedi.
K = "dogrudan-sdr:G2RL-2-12V"
FK = "Relay_THT:Relay_DPDT_Omron_G2RL-2"
L, C = "Device:L", "Device:C"
# CEKIRDEK BASINA AYRI AYAK IZI.
# Hepsi T50 ayak izini kullaniyordu (govde 12.7 mm) ama degerler
# daha buyuk cekirdek soyluyor: T68 gercekte 17.5 mm, T94 23.9 mm —
# neredeyse iki kati. 13-14 mm arayla dizilmis 23.9 mm'lik cekirdekler
# fiziksel olarak ic ice giriyor; kart basilir, parcalar takilmaz.
# Ustelik eski T50 ayak izinde F.CrtYd YOKTU, yani cakisma denetimi
# bu parcalari HIC gormuyordu (GetCourtyard genisligi 0 donuyor ve
# ayir.py o cifti atliyor). Uc ayak izi de artik courtyard'li.
FLT = {"T50": "dogrudan-sdr:L_Toroid_T50_Vertical",
       "T68": "dogrudan-sdr:L_Toroid_T68_Vertical",
       "T94": "dogrudan-sdr:L_Toroid_T94_Vertical"}
FCP = "Capacitor_THT:C_Disc_D7.5mm_W5.0mm_P5.00mm"
R = "Device:R"
FR = "Resistor_SMD:R_0603_1608Metric"

s = Sheet("05_lpf", "Cikis filtreleri", UU["05_lpf"],
          "7 bant alcak geciren, guc rolesi", paper="A1")

# 5. derece Chebyshev alcak geciren, 50 ohm, 0.1 dB dalgalanma.
# g = [1.1468, 1.3712, 1.9750, 1.3712, 1.1468]  (n=5, 0.1 dB)
G5 = [1.1468, 1.3712, 1.9750, 1.3712, 1.1468]
Z0 = 50.0
E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3,
       3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]


def e24(x):
    if x <= 0:
        return x
    d = math.floor(math.log10(x))
    m = x / 10 ** d
    return min(E24, key=lambda v: abs(math.log(v) - math.log(m))) * 10 ** d


# kesim frekansi bandin ustunden %10 yukarida
# TUZAKLI (ELIPTIK) FILTRE — DUZ CHEBYSHEV YETMIYOR.
#
# Olculdu (lpf_sim.py, ngspice): duz 5 kutup Chebyshev ile ikinci
# harmonik bastirmasi her bantta yasal sinirin ALTINDA kaliyordu.
#     160m -25 dB, 80_60m -3, 40_30m -10, 20_17m -18,
#     15_10m -14, 6m -30   (gereken: HF'te 43, 30 MHz ustu 60)
#
# 80_60m'de -3.4 dB, yani filtre ikinci harmonige neredeyse hic
# dokunmuyor: kesim 5.37 MHz'i gecirmek icin 6.0 MHz'te, ama 3.5
# MHz'in ikinci harmonigi 7.0 MHz — kesimin hemen ustu.
#
# Kutup sayisi kurtarmiyor: Chebyshev bastirma formuluyle hesaplandi,
# 80_60m icin 9 kutup bile 32 dB veriyor.
#
# Cozum tuzak: her seri bobine PARALEL bir kondansator, iletim
# sifirini tam harmonige oturtuyor. Amatör telsiz filtrelerinde
# standart yontem. Olculen sonuc -58 ile -83 dB.
#
# 80 ve 60 m AYRILDI. Birlikteyken 3.5'in harmonigi (7.0) 5.37'lik
# gecirme kenarina cok yakin ve tuzak bandin kendisini de bastiriyor.
# Ayri pozisyonlarda ikisi de -80 dB'nin ustunde. Yedinci role
# pozisyonu bypass'ti; artik 60 m orada. Vericide filtresiz yayin
# zaten hicbir durumda mesru degil.
#
# (ad, kesim MHz, 1. tuzak MHz, 2. tuzak MHz)
BANTLAR = [
    ("160m",    2.3,   3.6,   5.4),
    ("80m",     4.3,   7.0,  10.5),
    ("60m",     6.2,  10.70, 16.05),
    ("40_30m", 14.1,  14.0,  21.0),
    ("20_17m", 22.4,  28.0,  42.0),
    ("15_10m", 39.7,  42.0,  63.0),
    ("6m",     58.8, 100.0, 150.0),
]


def sentez(fc_mhz):
    """C-L-C-L-C topolojisi: tek indisler bobin, cift indisler kondansator."""
    w = 2 * math.pi * fc_mhz * 1e6
    vals = []
    for i, g in enumerate(G5):
        if i % 2 == 0:
            vals.append(("C", e24(g / (Z0 * w) * 1e12)))     # pF
        else:
            vals.append(("L", e24(g * Z0 / w * 1e9)))        # nH
    return vals


nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{499 + nr[0]}"


# Zincirin iki ucu: finalden gelen ve kuplore giden.
s.sym(R, "R500", "0R", 640, 60, rot=90, fp=FR)
s.pin_label(R, "1", 640, 60, 90, "PA_OUT", "input")
s.pin_label(R, "2", 640, 60, 90, "LPF_B1_IN", "output")
s.sym(R, "R501", "0R", 680, 60, rot=90, fp=FR)
s.pin_label(R, "1", 680, 60, 90, "LPF_B1_OUT", "input")
s.pin_label(R, "2", 680, 60, 90, "PA_LPF_OUT", "output")
s.text("Zincir giris/cikisi. 0R yerine dogrudan tel de olurdu ama\\n"
       "yerlesimde olcum noktasi olarak ise yariyor.", 620, 80, 1.3)

s.text("CIKIS HARMONIK FILTRELERI — 7 pozisyon", 16, 14, 2.2)
s.text("A sinifi bile harmonik uretir. 100 W'ta ikinci harmonik -30 dBc\\n"
       "olsa 100 mW eder — yasal sinirin cok ustunde.\\n\\n"
       "5. derece Chebyshev alcak geciren, bant basina bir tane.\\n"
       "Kesim frekansi bandin ustunden %10 yukarida; ikinci harmonikte\\n"
       "en az 35 dB bastirma veriyor.\\n\\n"
       "** BU FILTRELER C KARTINDAKINDEN TAMAMEN AYRI. **\\n"
       "Orasi ALIS, milivat, SMD. Burasi VERIS, 100 W:\\n"
       "  bobin        hava cekirdekli / toz demir toroid (SMD 100 W tasimaz)\\n"
       "  kondansator  mika ya da ATC (seramik isinir, degeri kayar)\\n"
       "  role         GUC rolesi, sinyal rolesi degil", 16, 22, 1.4)


def bolum(bant, fc, tuzak1, tuzak2, x, y, idx, son=False):
    ad = bant
    vals = sentez(fc)
    net_in = f"LPF_B{idx}_IN"
    net_out = f"LPF_B{idx}_OUT"
    # SON BOLUM ZINCIRI KAPATIYOR. Yedinci pozisyon eskiden bypass'ti
    # ve zinciri PA_LPF_OUT'a baglıyordu; simdi orada 60 m filtresi var.
    nxt_in = "PA_LPF_OUT" if son else f"LPF_B{idx + 1}_IN"
    nxt_out = "PA_LPF_OUT" if son else f"LPF_B{idx + 1}_OUT"

    s.sym(K, f"KL{idx}", "G2RL-2 DC12", x, y, fp=FK)
    s.pin_label(K, "11", x, y, 0, net_in, "passive", d=7.62)
    s.pin_label(K, "21", x, y, 0, net_out, "passive", d=12.7)
    s.pin_label(K, "12", x, y, 0, nxt_in, "passive", d=7.62)
    s.pin_label(K, "22", x, y, 0, nxt_out, "passive", d=12.7)
    s.pin_label(K, "14", x, y, 0, f"LF{idx}_A", "passive", d=17.78)
    s.pin_label(K, "24", x, y, 0, f"LF{idx}_B", "passive", d=22.86)
    s.pin_label(K, "A1", x, y, 0, "+12V", "input", d=17.78)
    s.pin_label(K, "A2", x, y, 0, f"KL{idx}_LO", "passive", d=22.86)

    fx = x + 60
    node = [f"LF{idx}_A", f"N{idx}_1", f"LF{idx}_B"]
    ci = 0
    for i, (tip, v) in enumerate(vals):
        if tip == "C":
            s.sym(C, cnt("C"), f"{v:g}pF", fx + i * 22, y + 20, rot=90, fp=FCP)
            s.pin_label(C, "1", fx + i * 22, y + 20, 90, node[ci], "passive")
            s.pin_power(C, "2", fx + i * 22, y + 20, 90, "GND")
        else:
            # Sarim sayisi ve cekirdek degerin icinde: elde sarilacak,
            # BOM'da "470nH" yazmasi ise yaramaz. manyetik_hesap.py
            cek = "T94-2" if fc < 8 else ("T68-2" if fc < 25 else "T50-6")
            import math as _m
            AL = {"T94-2": 8.4, "T68-2": 5.7, "T50-6": 4.0}[cek]
            Nt = _m.ceil(_m.sqrt(v / AL))
            nm = f"{cek} {Nt}s"
            s.sym(L, cnt("L"), nm, fx + i * 22, y, rot=90,
                  fp=FLT[cek.split("-")[0]])
            s.pin_label(L, "1", fx + i * 22, y, 90, node[ci], "passive")
            a_dugum = node[ci]
            ci += 1
            s.pin_label(L, "2", fx + i * 22, y, 90, node[ci], "passive")
            # TUZAK: bobine PARALEL kondansator, iletim sifiri harmonikte.
            ft = (tuzak1 if a_dugum == node[0] else tuzak2) * 1e6
            Ct = 1.0 / ((2 * _m.pi * ft) ** 2 * (v * 1e-9)) * 1e12
            s.sym(C, cnt("C"), f"{e24(Ct):g}pF", fx + i * 22 + 11, y - 18,
                  rot=90, fp=FCP)
            s.pin_label(C, "1", fx + i * 22 + 11, y - 18, 90, a_dugum,
                        "passive")
            s.pin_label(C, "2", fx + i * 22 + 11, y - 18, 90, node[ci],
                        "passive")


for i, (ad, fc, t1, t2) in enumerate(BANTLAR):
    bolum(ad, fc, t1, t2, 55 + (i % 2) * 340, 120 + (i // 2) * 70, i + 1,
          son=(i == len(BANTLAR) - 1))

# Yedinci pozisyon artik 60 m filtresi; bypass kaldirildi.

s.text("DEGERLER — 5. derece Chebyshev 0.1 dB, C-L-C-L-C\\n"
       "g = 1.1468 / 1.3712 / 1.9750 / 1.3712 / 1.1468\\n"
       "Kesim frekanslari: 2.2 / 6.0 / 11 / 19 / 31 / 56 MHz\\n\\n"
       "Bobinler HAVA CEKIRDEKLI ya da T68-2 sinifi toz demir: 100 W'ta\\n"
       "ferrit doyar ve harmonik URETIR — tam engellemeye calistigin sey.\\n"
       "Kondansatorler mika/ATC: 100 W'ta seramikte dielektrik isinmasi\\n"
       "degeri kaydirir ve filtre kayar.\\n\\n"
       "ROLE: G2RL-2, 8 A / 250 V. 100 W'ta 50 ohm'da 1.4 A ve 70 V rms\\n"
       "var; sinyal rolesi (G6K, 0.3 A) yapisirdi. Bunlar KILITLENMEYEN —\\n"
       "guc kesilince bypass'a donsun, filtre yanlis bantta kalmasin.",
       400, 330, 1.35)

s.text("SEBEKE SIRASI: once bant secilir, SONRA veris baslar.\\n"
       "Role RF altinda anahtarlanirsa kontak ark yapar ve yapisir.\\n"
       "Firmware sirasi: LPF rolesi -> 20 ms bekle -> T/R -> 10 ms ->\\n"
       "bias kur -> surucuyu ac. Kapanista tersi.", 400, 420, 1.35)

s.write(os.path.join(HERE, "05_lpf.kicad_sch"))
print("05_lpf.kicad_sch yazildi")
