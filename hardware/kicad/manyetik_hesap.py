#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""Elde sarilacak manyetiklerin sarim sayilari.

Uc kartta satin alinamayan tek parca sinifi bu: guc trafolari, yonlu
kuplor ve dusuk bantlarin yuksek Q'lu bobinleri. Hepsi elde sarilacak,
o yuzden sarim sayisi, tel kalinligi ve cekirdek secimi burada
hesaplaniyor — deneme yanilma degil.

Calistir:  python3 manyetik_hesap.py
"""
import math

# --------------------------------------------------------------- cekirdekler
# AL: nH / N^2.  Uretici verisi (Amidon / Fair-Rite katalogu).
# Bmax: doyma oncesi guvenli tepe akı yogunlugu, mT.
CEKIRDEK = {
    # toz demir — yuksek Q, dusuk gecirgenlik, filtre isi
    "T50-2":   dict(AL=4.9,  Ae=0.121, le=3.20, mu=10, Bmax=150, tip="toz demir"),
    "T50-6":   dict(AL=4.0,  Ae=0.121, le=3.20, mu=8,  Bmax=150, tip="toz demir"),
    "T68-2":   dict(AL=5.7,  Ae=0.196, le=4.24, mu=10, Bmax=150, tip="toz demir"),
    "T94-2":   dict(AL=8.4,  Ae=0.385, le=6.00, mu=10, Bmax=150, tip="toz demir"),
    # ferrit — genis bant trafo isi, dusuk Q ama yuksek gecirgenlik
    "FT50-43": dict(AL=523,  Ae=0.133, le=3.02, mu=850, Bmax=50, tip="ferrit 43"),
    "FT82-43": dict(AL=557,  Ae=0.246, le=5.26, mu=850, Bmax=50, tip="ferrit 43"),
    "FT114-43": dict(AL=603, Ae=0.375, le=7.42, mu=850, Bmax=50, tip="ferrit 43"),
    "BN43-202": dict(AL=2890, Ae=0.190, le=2.20, mu=850, Bmax=50, tip="binokuler 43"),
    "BN43-3312": dict(AL=6000, Ae=0.640, le=3.50, mu=850, Bmax=50, tip="binokuler 43"),
}

FMIN = 1.8e6      # en dusuk calisma frekansi, HF


def sarim(L_nH, cekirdek):
    """AL'den sarim sayisi.  L = AL * N^2  ->  N = sqrt(L/AL)"""
    return math.sqrt(L_nH / CEKIRDEK[cekirdek]["AL"])


def min_sarim_aki(P_watt, Z_ohm, cekirdek, f=FMIN):
    """Doymamak icin GEREKEN EN AZ sarim.

    Sarim sayisini yalnizca endüktans sartindan almak yetmiyor: az
    sarim = yuksek aki yogunlugu = doyma. Iki sart birden:
        N >= sqrt(L / AL)                 endüktans
        N >= V / (4.44 * f * Ae * Bmax)   doyma
    Ilk hesabimda ikincisini atlamistim; BN43-3312 icin 1 sarim
    cikti ve 69 mT ile doyuyordu.
    """
    V = math.sqrt(P_watt * Z_ohm)
    Ae_m2 = CEKIRDEK[cekirdek]["Ae"] * 1e-4
    Bmax_T = CEKIRDEK[cekirdek]["Bmax"] / 1000
    return V / (4.44 * f * Ae_m2 * Bmax_T)


def akı(P_watt, Z_ohm, N, cekirdek, f=FMIN):
    """Tepe aki yogunlugu, mT.  B = V / (4.44 * f * N * Ae)

    Doyma kontrolu SART: ferrit doyunca gecirgenligi cokuyor, trafo
    kisa devre gibi davraniyor ve HARMONIK URETIYOR — tam engellemeye
    calistigin sey. En dusuk frekansta ve en yuksek gucte kontrol et.
    """
    V = math.sqrt(P_watt * Z_ohm)          # rms
    Ae_m2 = CEKIRDEK[cekirdek]["Ae"] * 1e-4
    return V / (4.44 * f * N * Ae_m2) * 1000


def tel_capi(I_rms):
    """Akim yogunlugu 4 A/mm^2 (dogal sogutma) icin tel capi, mm."""
    A = I_rms / 4.0
    return 2 * math.sqrt(A / math.pi)


def awg(d_mm):
    """En yakin AWG."""
    tablo = {14: 1.63, 16: 1.29, 18: 1.02, 20: 0.81, 22: 0.64,
             24: 0.51, 26: 0.40, 28: 0.32, 30: 0.25}
    return min(tablo.items(), key=lambda kv: abs(kv[1] - d_mm))[0]


print("=" * 74)
print("D KARTI — GUC TRAFOLARI")
print("=" * 74)

# --- final cikis trafosu -------------------------------------------------
# Push-pull, 50 V besleme, 100 W cikis.
#   Pout = Vcc^2 / (2 * R_dd)  ->  R_dd = 2500 / (2*100) = 12.5 ohm
#   yuk 50 ohm  ->  empedans orani 1:4  ->  sarim orani 1:2
Vcc, Pout, Zload = 50.0, 100.0, 50.0
R_dd = Vcc ** 2 / (2 * Pout)
oran_z = Zload / R_dd
oran_n = math.sqrt(oran_z)
print(f"\nT31 FINAL CIKIS  (02_final)   ** BIRINCIL ORTA UCLU **")
print(f"  drain-drain empedansi  R_dd = Vcc^2/(2*Pout) = {R_dd:.1f} ohm")
print(f"  yuk {Zload:.0f} ohm  ->  empedans orani 1:{oran_z:.0f}, "
      f"sarim orani 1:{oran_n:.0f}")
# birincil endüktansi: en dusuk frekansta reaktans >= 4 x empedans
XL_gereken = 4 * R_dd
L_pri = XL_gereken / (2 * math.pi * FMIN) * 1e9      # nH
print(f"  birincil XL >= 4*R_dd = {XL_gereken:.0f} ohm @1.8 MHz")
print(f"  -> L_pri >= {L_pri / 1000:.2f} uH")
print(f"  {'cekirdek':<11} {'N(endük)':>8} {'N(doyma)':>8} {'secilen':>8}"
      f" {'ikincil':>8} {'B':>7}")
for c in ("BN43-3312", "FT114-43", "FT82-43"):
    N_L = sarim(L_pri, c)
    N_B = min_sarim_aki(Pout, R_dd, c)
    Np = math.ceil(max(N_L, N_B))
    Ns = Np * round(oran_n)
    B = akı(Pout, R_dd, Np, c)
    durum = "OK" if B < CEKIRDEK[c]["Bmax"] else "DOYUYOR"
    print(f"  {c:<11} {N_L:>8.1f} {N_B:>8.1f} {Np:>8} {Ns:>8}"
          f" {B:>5.1f}mT {durum}")
I_pri = math.sqrt(Pout / R_dd)
print(f"  birincil akim {I_pri:.1f} A rms -> tel {tel_capi(I_pri):.2f} mm "
      f"(AWG {awg(tel_capi(I_pri))})")
print("  NOT: birincil ORTA UCLU, iki yarim sarim simetrik olmali.")
print("       Asimetri cift harmonik iptalini bozar — push-pull'un")
print("       tek kazandirdigi sey o.")

# --- final giris trafosu -------------------------------------------------
print(f"\nT30 FINAL GIRIS  (02_final)")
Zin_gate = 1.0        # bastirma direnci ile ayarlanan gecit yuku
oran_z_in = 50.0 / Zin_gate
oran_n_in = math.sqrt(oran_z_in)
XL_in = 4 * 50.0
L_in = XL_in / (2 * math.pi * FMIN) * 1e9
print(f"  50 ohm -> {Zin_gate:.0f} ohm, empedans orani {oran_z_in:.0f}:1, "
      f"sarim orani {oran_n_in:.1f}:1")
print(f"  birincil XL >= {XL_in:.0f} ohm  ->  L >= {L_in / 1000:.1f} uH")
for c in ("BN43-202", "FT50-43"):
    N = math.ceil(sarim(L_in, c))
    print(f"    {c:<10} birincil {N:>2} sarim, ikincil {max(1, round(N / oran_n_in)):>2} sarim")
print("  Surucuden gelen guc yarim watt; doyma sorunu yok.")

# --- surucu 2 trafolari ---------------------------------------------------
print(f"\nT10 / T12 SURUCU 2  (01_driver)  ** T12 ORTA UCLU **")
for ad, z1, z2, P in (("giris  4:1", 50.0, 12.5, 0.5),
                      ("cikis  1:2", 25.0, 50.0, 8.0)):
    orz = z2 / z1
    L = 4 * min(z1, z2) / (2 * math.pi * FMIN) * 1e9
    c = "BN43-202"
    N = math.ceil(max(sarim(L, c), min_sarim_aki(P, min(z1, z2), c)))
    Ns = max(1, round(N * math.sqrt(orz)))
    B = akı(P, min(z1, z2), N, c)
    print(f"  {ad}: {c} birincil {N} sarim, ikincil {Ns} sarim, "
          f"B = {B:.1f} mT")

# --- yonlu kuplor ---------------------------------------------------------
# TANDEM MATCH. Iki ozdes trafo, iki AYRI is:
#   T20  1 sarim hatta seri        -> AKIM ornegi   i = I/N
#   T21  N sarim hat-toprak arasi  -> GERILIM ornegi v = V/N
# Portlar T20'nin N sarimli sarginin iki ucu; her portun soguk ucu
# 51R uzerinden ortak dugume (CPL_COM) gidiyor ve o dugumu T21'in
# tek sarimli ucu suruyor. Sonuc:
#     V_ileri = v + 51 i        V_yansiyan = v - 51 i
# Yansiyan port yuk 51 ohm iken sifir. Iki ornek toplandigi icin
# kuplaj tek trafolu devrenin 2 kati (+6 dB).
print(f"\nT20/T21 YONLU KUPLOR — TANDEM MATCH  (04_detect)")
N_kuplor = 32
kuplaj_db = 20 * math.log10(N_kuplor / 2.0)
print(f"  sarim orani 1:{N_kuplor}  ->  kuplaj -{kuplaj_db:.1f} dB")
print(f"  T20: birincil 1 sarim (duz gecen tel), ikincil {N_kuplor} sarim")
print(f"  T21: {N_kuplor} sarim hat-toprak arasi, 1 sarim CPL_COM'a")
print(f"  her iki port 51 ohm (1%) ile CPL_COM'a sonlandirilmis")
_p = 100 / 10 ** (kuplaj_db / 10) * 1000
print(f"  100 W'ta orneklenen: {_p:.0f} mW = +{10 * math.log10(_p):.1f} dBm")
print("  Dedektor onundeki sont 19R1'e indirildi: 6 dB'lik kazanci geri")
print("  aliyor, AD8318 100 W'ta yine ~0 dBm goruyor.")
print("  YONLULUK sarimin duzgunlugune bagli: cok sarimli sargi")
print("  cekirdege ESIT aralikli ve tam olarak sarilmali. 20 dB")
print("  yonluluk yeterli, dikkatli sarimla cikiyor; ozensiz sarimda")
print("  10 dB'ye duser ve SWR olcumu yaniltir.")
print("  SARIM YONU: devreye almada 50 ohm kukla yukte REV'in")
print("  sifirlandigi dogrulanacak; ters cikarsa T21'in TEK SARIMLI")
print("  ucu ters baglanacak (semada ifade edilemeyen tek sey bu).")

print()
print("=" * 74)
print("D KARTI — CIKIS ALCAK GECIREN FILTRELERI (05_lpf)")
print("=" * 74)
# 5. derece Chebyshev, C-L-C-L-C. g2 ve g4 bobinler.
G5 = [1.1468, 1.3712, 1.9750, 1.3712, 1.1468]
Z0 = 50.0
LPF = [("160m", 2.2), ("80/60m", 6.0), ("40/30m", 11.0),
       ("20/17m", 19.0), ("15/10m", 31.0), ("6m", 56.0)]
print(f"\n{'bant':<9} {'fc':>5} {'L2=L4':>8}  cekirdek     sarim   B@100W")
for ad, fc in LPF:
    w = 2 * math.pi * fc * 1e6
    L_nH = G5[1] * Z0 / w * 1e9
    # toz demir: yuksek guc, dusuk kayip. Frekansa gore karisim.
    c = "T94-2" if fc < 8 else ("T68-2" if fc < 25 else "T50-6")
    N = math.ceil(max(sarim(L_nH, c), min_sarim_aki(100, 50, c, f=fc * 1e6)))
    I = math.sqrt(100 / 50)
    B = akı(100, 50, N, c, f=fc * 1e6)
    print(f"{ad:<9} {fc:>4.0f}M {L_nH:>7.0f}n  {c:<10} {N:>4}    {B:>5.1f} mT")
I_lpf = math.sqrt(100 / 50)
print(f"\n  akim {I_lpf:.1f} A rms -> tel {tel_capi(I_lpf):.2f} mm "
      f"(AWG {awg(tel_capi(I_lpf))})")
print("  TOZ DEMIR, FERRIT DEGIL. Ferrit 100 W'ta doyar ve harmonik")
print("  uretir — filtrenin engellemeye calistigi seyi kendisi yapar.")

print()
print("=" * 74)
print("C KARTI — 160m VE 6m FILTRE BOBINLERI (03_filter)")
print("=" * 74)
print("Diger dort bantta SMD bobin yeterli (Q > 40). Bu ikisinde SMD'nin")
print("Q'su cokuyor; toroid sart. Ayrinti: C_rf/filtre_hesap.py")
CF = [("160m", 16000, "T68-2", 4), ("6m", 620, "T50-6", 4)]
print(f"\n{'bant':<8} {'L':>8}  cekirdek    sarim   adet  toplam")
toplam = 0
for ad, L_nH, c, kanal in CF:
    N = math.ceil(sarim(L_nH, c))
    adet = 3 * kanal            # uc rezonator x dort kanal
    toplam += adet
    print(f"{ad:<8} {L_nH:>7}n  {c:<10} {N:>5}   {adet:>4}   {adet}")
print(f"\n  TOPLAM {toplam} toroid elde sarilacak.")
print("  Alis tarafi, guc yok: ince tel yeter (AWG 28-30).")
print()
print("  ** ESLESTIRME SART. ** Dort kanalin faz uyumu bobinlerin")
print("  ozdes olmasina bagli. Elde sarim %5-10 sacilma yapar; 30 tane")
print("  sarip LCR ile olcup en yakin dortlulere ayirmak gerekiyor.")
print("  Satin alinamayan tek sey bu — ve tam bir kulup isi.")
