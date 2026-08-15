// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// Paylasimli telafi FIR — sekiz yol, tek motor.
//
// NEDEN: kanal basina ayri FIR koyunca dort kanal 56 carpan istiyor,
// ECP5-25F'te 28 var. Olculdu, tahmin degil:
//     karistirici   2 carpan/kanal  x4 =  8   (80 MHz, paylasilamaz)
//     telafi FIR    12 carpan/kanal x4 = 48
//                                        --
//                                        56
//
// Karistirici tam hizda kosuyor, paylasilamaz. Ama FIR cikis
// hizinda kosuyor: R=64'te 1.25 MSPS, sistem saati 80 MHz. Yani iki
// cikis ornegi arasinda 64 saat cevrimi bos duruyor.
//
// Sekiz yol (4 kanal x I,Q) tek motorda sirayla isleniyor: her yol
// bir cevrim, sekiz cevrimde tur bitiyor. 64 cevrimlik bosluga
// fazlasiyla sigiyor.
//
// SONUC: 8 + 6 = 14 carpan. Cipin yarisi bos kaliyor.
//
// KAYDIRMALI HAT YOL BASINA AYRI. Katsayilar ortak ama gecmis ornek
// degil — sekiz yolun her biri kendi 11 ornegini tutuyor. Blok RAM
// yerine yazmac kullaniyoruz: 8 yol x 11 ornek x 17 bit = 1496 bit,
// dagitilmis bellek icin kucuk, ve blok RAM'i SDRAM tamponuna
// birakmak istiyoruz.

`default_nettype none

module fir_paylasimli #(
    parameter YOL      = 8,
    parameter GIRIS_BIT = 17,
    parameter CIKIS_BIT = 24,
    parameter KAT_BIT   = 18
) (
    input  wire                        clk,
    input  wire                        rst,
    // yol secimi ile giris
    input  wire [2:0]                  yol_no,
    input  wire signed [GIRIS_BIT-1:0] giris,
    input  wire                        giris_gecerli,
    // cikis, yol numarasiyla birlikte
    output reg  [2:0]                  cikis_yol,
    output reg  signed [CIKIS_BIT-1:0] cikis,
    output reg                         cikis_gecerli
);

    localparam DERECE = 11;
    localparam YARI   = 5;

    localparam signed [KAT_BIT-1:0] H0 =  -18'sd19;
    localparam signed [KAT_BIT-1:0] H1 =   18'sd200;
    localparam signed [KAT_BIT-1:0] H2 =  -18'sd1140;
    localparam signed [KAT_BIT-1:0] H3 =   18'sd4721;
    localparam signed [KAT_BIT-1:0] H4 =  -18'sd16826;
    localparam signed [KAT_BIT-1:0] H5 =   18'sd58896;

    // ---------------------------------------------------------------
    // TEK UZUN KAYDIRMA ZINCIRI, ADRESLEME YOK.
    //
    // Ilk denemem yol basina ayri kaydirmali hat tutup yol_no ile
    // indeksliyordu. Degisken indis, 88 x 17 bitlik dizinin uzerinde
    // devasa coklayici agaci uretti: 41827 LUT, cipte 24000 var.
    //
    // Dogrusu cok daha basit. Yollar SABIT SIRAYLA geldigi icin tek
    // bir 88 kademeli zincir zaten her yolun gecmisini tutuyor:
    // p yolunun bir onceki ornegi tam 8 kademe geride. Yani taplar
    // sabit konumlarda — 0, 8, 16, ... 80 — ve hicbir adresleme yok.
    //
    // Zamanla coklanan FIR'in klasik yapisi bu. Adresleme yerine
    // gecikmeyi yol sayisi kadar uzatiyorsun.
    // ---------------------------------------------------------------
    localparam KADEME = YOL * DERECE;      // 88

    reg signed [GIRIS_BIT-1:0] hat [0:KADEME-1];

    integer k;
    always @(posedge clk) begin
        if (rst) begin
            for (k = 0; k < KADEME; k = k + 1)
                hat[k] <= {GIRIS_BIT{1'b0}};
        end else if (giris_gecerli) begin
            for (k = KADEME-1; k > 0; k = k - 1)
                hat[k] <= hat[k-1];
            hat[0] <= giris;
        end
    end

    // Yol etiketi veriyle birlikte boru hattinda ilerliyor
    reg [2:0] hes_yol;
    reg       hes_gecerli;
    always @(posedge clk) begin
        hes_yol     <= yol_no;
        hes_gecerli <= giris_gecerli;
    end

    // Simetrik ciftler: tap k, YOL kademe arayla
    wire signed [GIRIS_BIT:0] c0 = hat[0*YOL]  + hat[10*YOL];
    wire signed [GIRIS_BIT:0] c1 = hat[1*YOL]  + hat[9*YOL];
    wire signed [GIRIS_BIT:0] c2 = hat[2*YOL]  + hat[8*YOL];
    wire signed [GIRIS_BIT:0] c3 = hat[3*YOL]  + hat[7*YOL];
    wire signed [GIRIS_BIT:0] c4 = hat[4*YOL]  + hat[6*YOL];
    wire signed [GIRIS_BIT:0] c5 = {hat[5*YOL][GIRIS_BIT-1], hat[5*YOL]};

    localparam CARP_BIT = GIRIS_BIT + 1 + KAT_BIT;
    localparam TOP_BIT  = CARP_BIT + 3;
    localparam KAYDIR   = 15;

    // ---------------------------------------------------------------
    // BORU HATTI. Simetrik toplam + carpim + toplayici agaci tek
    // cevrimde yapilinca kritik yol 57.6 MHz'e dustu; 80 MHz gerek.
    // (nextpnr olctu, tahmin degil.)
    //
    // Uc kademeye boluyoruz:
    //   1  simetrik ciftleri topla ve YAZMACA AL
    //   2  carp, ikili gruplar halinde topla
    //   3  son toplama, yuvarlama, doyurma
    //
    // Gecikme iki cevrim artiyor. Onemsiz: cikis hizi 1.25 MSPS,
    // iki cevrim 25 ns.
    // ---------------------------------------------------------------
    reg signed [GIRIS_BIT:0] r0, r1, r2, r3, r4, r5;
    reg [2:0]                k1_yol;
    reg                      k1_gecerli;

    always @(posedge clk) begin
        if (rst) begin
            k1_gecerli <= 1'b0;
        end else begin
            r0 <= c0;  r1 <= c1;  r2 <= c2;
            r3 <= c3;  r4 <= c4;  r5 <= c5;
            k1_yol     <= hes_yol;
            k1_gecerli <= hes_gecerli;
        end
    end

    reg signed [CARP_BIT:0] p01, p23, p45;
    reg [2:0]               k2_yol;
    reg                     k2_gecerli;

    always @(posedge clk) begin
        if (rst) begin
            k2_gecerli <= 1'b0;
        end else begin
            p01 <= $signed(r0) * H0 + $signed(r1) * H1;
            p23 <= $signed(r2) * H2 + $signed(r3) * H3;
            p45 <= $signed(r4) * H4 + $signed(r5) * H5;
            k2_yol     <= k1_yol;
            k2_gecerli <= k1_gecerli;
        end
    end

    reg signed [TOP_BIT-1:0] toplam;
    reg [2:0]                top_yol;
    reg                      top_gecerli;

    always @(posedge clk) begin
        if (rst) begin
            toplam      <= {TOP_BIT{1'b0}};
            top_gecerli <= 1'b0;
        end else begin
            toplam      <= p01 + p23 + p45;
            top_yol     <= k2_yol;
            top_gecerli <= k2_gecerli;
        end
    end

    wire signed [TOP_BIT-1:0] yuvarlak =
        toplam + {{(TOP_BIT-KAYDIR){1'b0}}, 1'b1, {(KAYDIR-1){1'b0}}};
    wire signed [TOP_BIT-KAYDIR-1:0] olcekli = yuvarlak >>> KAYDIR;

    wire tasma_p, tasma_n;
    // DOYURMA YALNIZCA KORUMA BITI VARSA.
    // GIRIS_BIT 24'ten 17'ye inince TOP_BIT-KAYDIR = CIKIS_BIT oldu,
    // yani olceklenmis degerin cikistan fazla biti kalmadi ve
    // olcekli[22:23] gibi ters sirali bir dilim olustu — iverilog
    // hata verdi, yosys sessizce gecti. Sentezleyicinin sessiz
    // gecmesi hatanin yoklugu anlamina gelmiyor.
    //
    // Koruma biti yoksa tasma da olamaz: 17 bit giris, kazanci en
    // fazla 1.5 olan bir filtreden gecince 18 bit ediyor, cikis 24
    // bit. Yer bol.
    localparam KORUMA = TOP_BIT - KAYDIR - CIKIS_BIT;

    generate
    if (KORUMA > 0) begin : g_doyur
        wire t_p = !olcekli[TOP_BIT-KAYDIR-1] &&
                   |olcekli[TOP_BIT-KAYDIR-2 : CIKIS_BIT-1];
        wire t_n =  olcekli[TOP_BIT-KAYDIR-1] &&
                   ~&olcekli[TOP_BIT-KAYDIR-2 : CIKIS_BIT-1];
        assign tasma_p = t_p;
        assign tasma_n = t_n;
    end else begin : g_doyur_yok
        assign tasma_p = 1'b0;
        assign tasma_n = 1'b0;
    end
    endgenerate

    always @(posedge clk) begin
        if (rst) begin
            cikis         <= {CIKIS_BIT{1'b0}};
            cikis_gecerli <= 1'b0;
        end else begin
            if (tasma_p)
                cikis <= {1'b0, {(CIKIS_BIT-1){1'b1}}};
            else if (tasma_n)
                cikis <= {1'b1, {(CIKIS_BIT-1){1'b0}}};
            else
                cikis <= olcekli[CIKIS_BIT-1:0];
            cikis_yol     <= top_yol;
            cikis_gecerli <= top_gecerli;
        end
    end

endmodule

`default_nettype wire
