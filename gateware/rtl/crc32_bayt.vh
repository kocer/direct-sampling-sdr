// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// URETILMIS DOSYA — ELLE DEGISTIRME.
// Ureten: rtl/crc32_uret.py   (gerekce orada yazili)
//
// CRC32 bayt adimi, bit-seri dongu yerine DUZLESTIRILMIS
// XOR denklemleri. Ayni fonksiyon, kisa birlesimsel yol.
// Esdegerlik sim/tb_crc32.v ile dogrulaniyor.

function [31:0] crc_bayt;
    input [31:0] c;
    input [7:0]  d;
    begin
        crc_bayt[ 0] = c[2] ^ c[8] ^ d[2];
        crc_bayt[ 1] = c[0] ^ c[3] ^ c[9] ^ d[0] ^ d[3];
        crc_bayt[ 2] = c[0] ^ c[1] ^ c[4] ^ c[10] ^ d[0] ^ d[1] ^ d[4];
        crc_bayt[ 3] = c[1] ^ c[2] ^ c[5] ^ c[11] ^ d[1] ^ d[2] ^ d[5];
        crc_bayt[ 4] = c[0] ^ c[2] ^ c[3] ^ c[6] ^ c[12] ^ d[0] ^ d[2] ^ d[3] ^ d[6];
        crc_bayt[ 5] = c[1] ^ c[3] ^ c[4] ^ c[7] ^ c[13] ^ d[1] ^ d[3] ^ d[4] ^ d[7];
        crc_bayt[ 6] = c[4] ^ c[5] ^ c[14] ^ d[4] ^ d[5];
        crc_bayt[ 7] = c[0] ^ c[5] ^ c[6] ^ c[15] ^ d[0] ^ d[5] ^ d[6];
        crc_bayt[ 8] = c[1] ^ c[6] ^ c[7] ^ c[16] ^ d[1] ^ d[6] ^ d[7];
        crc_bayt[ 9] = c[7] ^ c[17] ^ d[7];
        crc_bayt[10] = c[2] ^ c[18] ^ d[2];
        crc_bayt[11] = c[3] ^ c[19] ^ d[3];
        crc_bayt[12] = c[0] ^ c[4] ^ c[20] ^ d[0] ^ d[4];
        crc_bayt[13] = c[0] ^ c[1] ^ c[5] ^ c[21] ^ d[0] ^ d[1] ^ d[5];
        crc_bayt[14] = c[1] ^ c[2] ^ c[6] ^ c[22] ^ d[1] ^ d[2] ^ d[6];
        crc_bayt[15] = c[2] ^ c[3] ^ c[7] ^ c[23] ^ d[2] ^ d[3] ^ d[7];
        crc_bayt[16] = c[0] ^ c[2] ^ c[3] ^ c[4] ^ c[24] ^ d[0] ^ d[2] ^ d[3] ^ d[4];
        crc_bayt[17] = c[0] ^ c[1] ^ c[3] ^ c[4] ^ c[5] ^ c[25] ^ d[0] ^ d[1] ^ d[3] ^ d[4] ^ d[5];
        crc_bayt[18] = c[0] ^ c[1] ^ c[2] ^ c[4] ^ c[5] ^ c[6] ^ c[26] ^ d[0] ^ d[1] ^ d[2] ^ d[4] ^ d[5] ^ d[6];
        crc_bayt[19] = c[1] ^ c[2] ^ c[3] ^ c[5] ^ c[6] ^ c[7] ^ c[27] ^ d[1] ^ d[2] ^ d[3] ^ d[5] ^ d[6] ^ d[7];
        crc_bayt[20] = c[3] ^ c[4] ^ c[6] ^ c[7] ^ c[28] ^ d[3] ^ d[4] ^ d[6] ^ d[7];
        crc_bayt[21] = c[2] ^ c[4] ^ c[5] ^ c[7] ^ c[29] ^ d[2] ^ d[4] ^ d[5] ^ d[7];
        crc_bayt[22] = c[2] ^ c[3] ^ c[5] ^ c[6] ^ c[30] ^ d[2] ^ d[3] ^ d[5] ^ d[6];
        crc_bayt[23] = c[3] ^ c[4] ^ c[6] ^ c[7] ^ c[31] ^ d[3] ^ d[4] ^ d[6] ^ d[7];
        crc_bayt[24] = c[0] ^ c[2] ^ c[4] ^ c[5] ^ c[7] ^ d[0] ^ d[2] ^ d[4] ^ d[5] ^ d[7];
        crc_bayt[25] = c[0] ^ c[1] ^ c[2] ^ c[3] ^ c[5] ^ c[6] ^ d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[5] ^ d[6];
        crc_bayt[26] = c[0] ^ c[1] ^ c[2] ^ c[3] ^ c[4] ^ c[6] ^ c[7] ^ d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[6] ^ d[7];
        crc_bayt[27] = c[1] ^ c[3] ^ c[4] ^ c[5] ^ c[7] ^ d[1] ^ d[3] ^ d[4] ^ d[5] ^ d[7];
        crc_bayt[28] = c[0] ^ c[4] ^ c[5] ^ c[6] ^ d[0] ^ d[4] ^ d[5] ^ d[6];
        crc_bayt[29] = c[0] ^ c[1] ^ c[5] ^ c[6] ^ c[7] ^ d[0] ^ d[1] ^ d[5] ^ d[6] ^ d[7];
        crc_bayt[30] = c[0] ^ c[1] ^ c[6] ^ c[7] ^ d[0] ^ d[1] ^ d[6] ^ d[7];
        crc_bayt[31] = c[1] ^ c[7] ^ d[1] ^ d[7];
    end
endfunction
