#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
"""Kat planlari — parcalar tek tek, elektriksel mantiga gore.

Kuvvet-guduml u yerlesim baglantilari kisaltti ama kart hala "kume"
yerlesimi: hangi parcanin nereye ait oldugunu fizik degil algoritma
seciyordu. Burada plan ACIKCA yaziliyor.

Uc kural bu dosyayi belirliyor:

1 SINYAL AKISI DUZ OLMALI. Anten kenardan girer, saga dogru ilerler,
  ADC'ye varir. Geri donen yol yoktur. Zincir ne kadar duzse yol o
  kadar kisa ve o kadar az kuplaj.

2 DORT ALIS ZINCIRI BIREBIR AYNI OLMALI. Faz uyumu bu kartin butun
  degeri. Zincir 1 elle konumlandirilir, 2/3/4 AYNI GEOMETRININ
  otelenmisi olur — boylece yol uzunluklari da ayni cikar.

3 SAAT IKI ADC'NIN TAM ORTASINDA. ADCLK846'dan iki ADC'ye giden LVDS
  ciftleri esit uzunlukta olsun diye. Saati bir kenara koyup iki
  farkli uzunlukta yol cekmek, kalibre edilemeyen bir faz farki
  birakir.

Kat plani, A karti:

    0        45        90       135      180
  0 +-------------------------------------+
    | RX1 --zincir-->  [ADC U20 ]  SDRAM  |
 25 | RX2 --zincir-->              U50    |
    |                                     |
 55 |    [ SAAT ADASI ]   [ FPGA U10 ]    |   <- saat iki ADC arasi
    |     Y10 + U15                       |
 85 | RX3 --zincir-->  [ADC U21 ]  PHY+MAG|
    | RX4 --zincir-->                     |
115 | [DAC U30/U31] --> T --> TX SMA      |   GUC (sag ust kose)
145 +-------------------------------------+

Analog sol, sayisal sag, guc ADC'den en uzak kosede.
"""

# ------------------------------------------------------------------ A karti
# (ref, x, y, aci)  — aci derece, 0 = sema yonu
A_CAPA = {
    # --- alis SMA'lari SOL KENARDA, kenar montaj
    "J20": (4, 20, 0), "J21": (4, 42, 0), "J22": (4, 96, 0), "J23": (4, 118, 0),
    # --- ADC'ler: U20 ust cift (RX1/RX2), U21 alt cift (RX3/RX4)
    "U20": (62, 31, 0), "U21": (62, 107, 0),
    # --- saat adasi: IKI ADC'NIN TAM ORTASI
    "Y10": (30, 66, 0), "U15": (55, 69, 0),
    # --- FPGA merkez
    "U10": (110, 69, 0),
    # --- SDRAM, FPGA'nin ustunde (banka 7 o tarafta)
    "U50": (110, 25, 0),
    # --- ethernet SAG KENAR, magjack kenarda
    "U40": (140, 55, 0), "J40": (168, 55, 0),
    "U41": (140, 88, 0), "J41": (168, 88, 0),
    # --- DAC ve veris, ALT SOL
    "U30": (55, 132, 0), "U31": (85, 132, 0),
    "J30": (20, 156, 0), "J31": (45, 156, 0),
    "J32": (70, 156, 0), "J33": (95, 156, 0),
    # --- guc, SAG UST KOSE (ADC'den en uzak)
    "J1": (172, 8, 0), "U1": (150, 14, 0), "U2": (150, 30, 0),
    # --- konfig ve kontrol
    "U11": (132, 100, 0), "J10": (150, 105, 0),
    "J61": (4, 168, 0), "U62": (30, 175, 0),
    "J63": (140, 168, 0), "J65": (160, 168, 0), "J66": (176, 168, 0),
    "J60": (120, 168, 0), "J62": (100, 168, 0), "J64": (80, 168, 0),
}

# Alis zinciri: sirayla, SMA'dan ADC'ye. dx = bir sonraki parcaya
# yatay mesafe. Zincir 1 icin acikca yaziliyor, otekiler otelenmis.
A_RX_ZINCIR = [
    ("R{term}", 14, 0),      # 49.9R sonlandirma
    ("T{n}", 24, 0),         # ADT1-1WT trafo
    ("R{s1}", 40, -2),       # seri direnc VIN+
    ("R{s2}", 40, +2),       # seri direnc VIN-
    ("C{dif}", 48, 0),       # diferansiyel C
]
# Kanal basina y ofseti; zincir 1'in y'si SMA'nin y'si.
A_RX_KANAL = [("A1", 20, "T1"), ("B1", 42, "T2"),
              ("A2", 96, "T3"), ("B2", 118, "T4")]

# Veris zinciri: DAC cikisindan trafoya, trafodan SMA'ya
A_TX_KANAL = [("1", "T10", 20), ("2", "T11", 45),
              ("3", "T12", 70), ("4", "T13", 95)]

# ------------------------------------------------------------------ C karti
# Dort kanal, her kanalda yedi pozisyonluk zincir. Kanal 1 aciktan
# yerlestiriliyor, 2/3/4 otelenmis — filtre bankasinda simetri sart.
C_KANAL_Y = [22, 78, 134, 190]        # dort kanalin y ekseni
C_BOLUM_X = 60                        # ilk filtre bolumunun x'i
C_BOLUM_ADIM = 40                     # bolumler arasi mesafe
C_CAPA = {
    "J1": (4, 22, 0), "J2": (4, 78, 0), "J3": (4, 134, 0), "J4": (4, 190, 0),
    "J80": (330, 40, 0), "J81": (330, 70, 0), "J90": (330, 95, 0),
    "U80": (330, 130, 0), "L80": (330, 150, 0),
}

# ------------------------------------------------------------------ D karti
# Tek bir guc zinciri: giris -> zayiflatici -> surucu -> final ->
# filtre -> kuplor -> anten. Duz bir hat, geri donus yok.
D_CAPA = {
    "J10": (4, 30, 0),          # A kartindan TX girisi
    "U10": (25, 30, 0),         # PE4312
    "U11": (50, 30, 0),         # PGA-103+
    "T10": (72, 30, 0),         # surucu 2 giris trafosu
    "Q20": (88, 24, 0), "Q21": (88, 38, 0),
    "T11": (108, 30, 0),        # surucu 2 cikis
    "T10_f": (128, 30, 0),
    # final: dort cihaz iki kol, simetrik
    "Q10": (150, 18, 0), "Q11": (150, 30, 0),
    "Q12": (150, 46, 0), "Q13": (150, 58, 0),
    "T11_f": (180, 38, 0),      # cikis trafosu
    # bias servolari cihazlarin yaninda
    "U20": (150, 82, 0), "U21": (175, 82, 0),
    # LPF zinciri
    "KL1": (30, 110, 0), "KL2": (60, 110, 0), "KL3": (90, 110, 0),
    "KL4": (120, 110, 0), "KL5": (150, 110, 0), "KL6": (180, 110, 0),
    "KL7": (210, 110, 0),
    # kuplor ve detektorler cikista
    "T20": (215, 38, 0), "T21": (215, 60, 0),
    "U30": (240, 38, 0), "U31": (240, 60, 0),
    "J20": (240, 15, 0),
    # guc kosede
    "J30": (4, 175, 0), "U50": (40, 175, 0), "U51": (75, 175, 0),
    "J31": (240, 175, 0), "J32": (240, 195, 0),
}
