#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""CRC32 bayt adiminin DUZLESTIRILMIS halini uret.

    python3 rtl/crc32_uret.py > rtl/crc32_bayt.vh

NEDEN. rgmii_veris.v'de CRC bayt adimi bit-seri dongu olarak
yaziliydi:

    t = c ^ d;
    for (i = 0; i < 8; i = i + 1)
        t = t[0] ? ((t >> 1) ^ 32'hEDB88320) : (t >> 1);

Bu okunakli ama SENTEZ ICIN KOTU: yosys donguyu birebir kuruyor,
sekiz adim birbirine zincirli ve her adim bir LUT katmani. Sonuc
uzun bir birlesimsel yol.

nextpnr olcumu: clk_eth'in kritik yolu tam burasi ve azami frekans
tohuma gore 112-138 MHz arasinda geziniyor — hedef 125 MHz. Yani
yapinin gecmesi TOHUM SANSINA kalmis durumdaydi; alti tohum ust uste
denendi, alti da dustu.

FONKSIYON DOGRUSAL. Kosullu gibi gorunuyor ama t[0]'a gore secim
yapmak, XOR'un kendisi. Cikisin her biti, giris bitlerinin bir alt
kumesinin XOR'u. Yani ayni fonksiyon DENGELI bir XOR agaci olarak
yazilabilir ve derinlik sekiz katmandan ~3 katmana iner.

Denklemler elle yazilmiyor — elle yazilan bir CRC tablosu sessizce
yanlis olur. Burada referans algoritma taban vektorleriyle kosturulup
dogrusal donusum CIKARILIYOR:

    her giris biti tek basina 1 yapilip cikis okunuyor
    sabit terim (butun girisler 0) ayrica cikariliyor

Uretilen dosya rgmii_veris.v tarafindan `include ediliyor ve
esdegerligi tb_crc32.v ile TUKETICI olarak dogrulaniyor: iki bicim
de butun 2^8 bayt degeri ve rastgele CRC durumlariyla karsilastiriliyor.
"""
import sys

POLI = 0xEDB88320


def referans(c, d):
    """rgmii_veris.v'deki ozgun dongunun birebir karsiligi."""
    t = (c ^ d) & 0xFFFFFFFF
    for _ in range(8):
        t = ((t >> 1) ^ POLI) if (t & 1) else (t >> 1)
    return t & 0xFFFFFFFF


def dogrusal_cikar():
    """Doner: (sabit, [40 adet 32 bitlik maske]).

    Giris vektoru: bit 0..31 = c[0..31], bit 32..39 = d[0..7].
    """
    sabit = referans(0, 0)
    maskeler = []
    for i in range(40):
        if i < 32:
            v = referans(1 << i, 0)
        else:
            v = referans(0, 1 << (i - 32))
        maskeler.append(v ^ sabit)
    return sabit, maskeler


def dogrula(sabit, maskeler):
    """Cikarilan dogrusal bicim referansla ayni mi — genis ornekle."""
    import random
    rnd = random.Random(20260816)
    for _ in range(20000):
        c = rnd.getrandbits(32)
        d = rnd.getrandbits(8)
        giris = c | (d << 32)
        y = sabit
        for i in range(40):
            if (giris >> i) & 1:
                y ^= maskeler[i]
        if y != referans(c, d):
            return False
    return True


if __name__ == "__main__":
    sabit, maskeler = dogrusal_cikar()
    if not dogrula(sabit, maskeler):
        sys.stderr.write("CIKARIM DOGRULANAMADI\n")
        raise SystemExit(1)

    ç = sys.stdout
    ç.write("// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA\n")
    ç.write("// SPDX-License-Identifier: GPL-3.0-only\n")
    ç.write("//\n")
    ç.write("// URETILMIS DOSYA — ELLE DEGISTIRME.\n")
    ç.write("// Ureten: rtl/crc32_uret.py   (gerekce orada yazili)\n")
    ç.write("//\n")
    ç.write("// CRC32 bayt adimi, bit-seri dongu yerine DUZLESTIRILMIS\n")
    ç.write("// XOR denklemleri. Ayni fonksiyon, kisa birlesimsel yol.\n")
    ç.write("// Esdegerlik sim/tb_crc32.v ile dogrulaniyor.\n")
    ç.write("\n")
    ç.write("function [31:0] crc_bayt;\n")
    ç.write("    input [31:0] c;\n")
    ç.write("    input [7:0]  d;\n")
    ç.write("    begin\n")
    for bit in range(32):
        terimler = []
        for i in range(40):
            if (maskeler[i] >> bit) & 1:
                terimler.append("c[%d]" % i if i < 32 else "d[%d]" % (i - 32))
        if (sabit >> bit) & 1:
            terimler.append("1'b1")
        if not terimler:
            ifade = "1'b0"
        else:
            ifade = " ^ ".join(terimler)
        ç.write("        crc_bayt[%2d] = %s;\n" % (bit, ifade))
    ç.write("    end\n")
    ç.write("endfunction\n")
