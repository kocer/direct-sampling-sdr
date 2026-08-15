#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""C karti bant filtresi bankasi — deger sentezi.

Yedi pozisyon, dordu ayni: her kanalda ayni banka.
Topoloji: uc rezonatorlu, tepeden kapasitif kuplajli bant gecirenler.

NEDEN BU TOPOLOJI
  - Paralel LC rezonator: bobin sayisi az (3), her biri toprakli
  - Tepeden kuplaj: kuplaj kondansatorleri ile bant genisligi ayarlanir
  - Alici on secicisi icin klasik; 40-60 dB uzak-bant bastirma

Q SINIRI
  JLCPCB'de yuksek Q'lu RF bobini yok. Murata LQW18AN sarim tipi,
  HF'te Q ~ 40-60. Bu ekleme kaybini ve bant kenari yuvarlanmasini
  belirliyor; asagida hesaplaniyor.
"""
import math

# Bant kenarlari. Amator bantlarin biraz disina tasiyoruz ki kenar
# yuvarlanmasi bandin icine girmesin.
BANTLAR = [
    ("160m",   1.75,   2.05),
    ("80/60m", 3.40,   5.50),
    ("40/30m", 6.90,  10.30),
    ("20/17m", 13.90, 18.30),
    ("15/10m", 20.90, 29.80),
    ("6m",     49.50, 54.50),
]
Z0 = 50.0
# Bobin Q'su banda ve parcaya gore DEGISIYOR. Tek sayi kullanmak
# yaniltiyordu: 620 nH'lik bir RF bobini 50 MHz'te Q=60 verirken,
# 16 uH'lik bir guc bobini 2 MHz'te Q=25 veriyor.
#   SMD  : LCSC'de o degerde bulunabilen en iyi parcanin gercekci Q'su
#   TORO : elde sarilmis toz demir toroid (T50-2 / T50-6)
Q_SMD  = {"160m": 25, "80/60m": 30, "40/30m": 40,
          "20/17m": 50, "15/10m": 55, "6m": 60}
Q_TORO = {"160m": 180, "80/60m": 200, "40/30m": 200,
          "20/17m": 180, "15/10m": 160, "6m": 120}

# 3 kutuplu Chebyshev 0.1 dB dalgalanma prototipi
G = [1.0, 1.0316, 1.1474, 1.0316, 1.0]

E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7,
       3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5,
       8.2, 9.1]


def e24(x):
    """En yakin E24 degerine yuvarla."""
    if x <= 0:
        return x
    d = math.floor(math.log10(x))
    m = x / 10 ** d
    best = min(E24, key=lambda v: abs(math.log(v) - math.log(m)))
    return best * 10 ** d


def tasarla(ad, f1, f2):
    f1 *= 1e6
    f2 *= 1e6
    f0 = math.sqrt(f1 * f2)
    bw = f2 - f1
    Qbp = f0 / bw                      # bant gecirenin yuklu Q'su
    w0 = 2 * math.pi * f0

    # Rezonator bobini: REAKTANSI hedefliyoruz, kapasiteyi degil.
    # Once kondansatoru 100 pF'a sabitleyip L'yi bulmustum; 160m'de
    # 68 uH cikti ve o degerde RF bobini yok. Dogrusu makul bir
    # rezonator empedansi secmek: X_L = 200 ohm.
    #   cok dusuk -> bobinin seri direnci baskin, Q duser
    #   cok yuksek -> kondansatorler pF altina iner, parazitik baskin
    XL = 200.0
    L = e24(XL / w0 * 1e9) * 1e-9
    C = 1 / (w0 ** 2 * L)

    # Tepeden kuplaj kondansatorleri (Cochrane/Zverev yaklasik bagintisi)
    # k_ij = 1/(Qbp * sqrt(g_i * g_j)),  C_ij = k_ij * C
    k12 = 1 / (Qbp * math.sqrt(G[1] * G[2]))
    k23 = 1 / (Qbp * math.sqrt(G[2] * G[3]))
    C12 = k12 * C
    C23 = k23 * C

    # Uc kondansatorleri: 50 ohm'a donusturur.
    # Rezonator sont direnci Rp = Qu * w0 * L,  gereken donusum orani
    Qu = Q_SMD[ad]
    Rp = Qu * w0 * L
    # kaynak uctan gorulen yuk = Z0; seri C ile donusum
    Qext = Qbp * G[0] * G[1]
    Cuc = 1 / (w0 * Z0 * math.sqrt(max(Qext ** 2 - 1, 0.01)))

    # Ekleme kaybi: sonlu Q yuzunden (Cohn yaklasimi)
    #   IL ≈ 4.343 * sum(g_i) * Qbp / Qu   [dB]
    gsum = G[1] + G[2] + G[3]
    IL = 4.343 * gsum * Qbp / Q_SMD[ad]
    IL_t = 4.343 * gsum * Qbp / Q_TORO[ad]

    return dict(ad=ad, f0=f0 / 1e6, bw=bw / 1e6, Qbp=Qbp, IL_t=IL_t,
                L=L * 1e9, C=e24(C * 1e12), C12=e24(C12 * 1e12),
                C23=e24(C23 * 1e12), Cuc=e24(Cuc * 1e12), IL=IL, Rp=Rp)


print(f"{'bant':<8} {'f0':>7} {'BW':>7} {'Qbp':>6} {'L':>8} {'Crez':>7} "
      f"{'C12':>7} {'C23':>7} {'Cuc':>7} {'IL':>6}")
print("-" * 82)
sonuc = []
for ad, f1, f2 in BANTLAR:
    r = tasarla(ad, f1, f2)
    sonuc.append(r)
    print(f"{r['ad']:<8} {r['f0']:>7.2f} {r['bw']:>7.2f} {r['Qbp']:>6.2f} "
          f"{r['L']:>7.0f}n {r['C']:>6.0f}p {r['C12']:>6.1f}p "
          f"{r['C23']:>6.1f}p {r['Cuc']:>6.1f}p {r['IL']:>5.2f}d")

print()
print("EKLEME KAYBI — SMD BOBIN vs ELDE SARILI TOROID")
print(f"{'bant':<9} {'Q_smd':>6} {'IL_smd':>8}   {'Q_toro':>6} {'IL_toro':>8}   karar")
for r in sonuc:
    a = r["ad"]
    fark = r["IL"] - r["IL_t"]
    karar = "SMD yeter" if r["IL"] < 1.2 else (
        "toroid onerilir" if fark > 1.0 else "SMD kabul")
    print(f"  {a:<7} {Q_SMD[a]:>6} {r['IL']:>7.2f} dB {Q_TORO[a]:>7} "
          f"{r['IL_t']:>7.2f} dB   {karar}")
print()
print("Alicida on yukseltec YOK — ekleme kaybi dogrudan duyarliliktan")
print("dusuyor. 1 dB kayip = 1 dB daha kotu MDS.")
print()
print("TOROID BEDELI: elde sarilir, yani kanaldan kanala DEGISIR.")
print("Faz uyumu icin dort kanalin ozdes olmasi sart. Cozum: 30 tane")
print("sarip LCR ile olcup en yakin dortlulere ayirmak. Ogrenci isi,")
print("egitici, ve satin alinamayan tek sey bu.")
print()
print(f"TOPLAM PARCA: 6 bant x (3 bobin + 5 kondansator) x 4 kanal = "
      f"{6 * 8 * 4} pasif")
print(f"             + 7 pozisyon x 4 kanal = {7 * 4} role (bypass dahil)")
