// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// ECP5 ILKELLERININ SIMULASYON MODELLERI — SADECE TEST ICIN.
//
// Sentezde kullanilmaz. yosys'in ecp5 kutuphanesinde bu uc hucrenin
// DAVRANIS modeli yok, sadece kara kutu bildirimi var (cells_bb.v).
// Ust modul bunlari kullandigi icin, modeller olmadan butun sistem
// simule EDILEMIYOR — ve gercekten de edilmiyordu: sim/ dizininde
// tb_ust yok, ust modul sadece sentezden geciyordu. Moduller tek tek
// test edilmis, birlestirilmis sistem hic kosmamis.
//
// BU MODELLER YANLIS OLURSA TEST TEZGAHI YALAN SOYLER. O yuzden her
// birinin davranisi veri sayfasindan ve ust.v'deki kullanimdan
// dogrulanarak yazildi; asagida gerekceleri var.

`timescale 1ns/1ps
`default_nettype none

// ---------------------------------------------------------------------
// ODDRX1F — cikis DDR yazmaci
//
// Iki veri girisi SCLK'in YUKSELEN kenarinda birlikte yakalaniyor.
// Sonra Q, saatin YUKSEK yarisinda D0'i, DUSUK yarisinda D1'i
// gosteriyor.
//
// Bu davranis ust.v'deki iki kullanimla dogrulaniyor:
//
//   u_tclk: D0=1, D1=0  ->  Q, SCLK ile ayni fazda bir saat olur.
//           RGMII verici saati boyle uretiliyor.
//
//   u_iqwrt (dac_cogullu): D0=0, D1=1  ->  Q, SCLK'in DUSEN
//           kenarinda yukselir. dac_cogullu.v'nin basligi tam bunu
//           soyluyor: "veri posedge'de degisiyor, IQWRT negedge'de
//           YUKSELIYOR". Kurulum suresi yarim cevrim bu sayede.
// ---------------------------------------------------------------------
module ODDRX1F (
    input  wire SCLK,
    input  wire RST,
    input  wire D0,
    input  wire D1,
    output wire Q
);
    reg d0_r = 1'b0, d1_r = 1'b0;
    always @(posedge SCLK or posedge RST)
        if (RST) begin d0_r <= 1'b0; d1_r <= 1'b0; end
        else     begin d0_r <= D0;   d1_r <= D1;   end
    assign Q = SCLK ? d0_r : d1_r;
endmodule

// ---------------------------------------------------------------------
// IDDRX1F — giris DDR yazmaci
//
// D, saatin her iki kenarinda ornekleniyor ve iki ornek de SCLK
// alaninda sunuluyor:
//   Q0 = YUKSELEN kenardaki ornek
//   Q1 = DUSEN kenardaki ornek
//
// IKI KADEME SART — ILK YAZDIGIMDA TEK KADEMEYDI VE YANLISTI.
//
// Once soyle yazmistim:
//     always @(negedge SCLK) d_neg <= D;
//     always @(posedge SCLK) begin Q0 <= D; Q1 <= d_neg; end
//
// Burada Q0, o anki yukselen kenarin ornegi; Q1 ise BIR ONCEKI dusen
// kenarin ornegi. Ama o dusen kenar, Q0'in ornegiden ONCE gelmisti —
// yani ikisi ayni bit periyoduna ait DEGIL, yarim cevrim kaymislar.
//
// rgmii_alis.v rd_yuk ve rd_dus'u tek bayta birlestiriyor ve ikisinin
// AYNI bit periyodundan gelmesini varsayiyor. Kayik modelle her bayt
// iki komsu bayttan yarim yarim olusurdu; belirtisi de "her cerceve
// CRC hatasi veriyor" olurdu ve insan CRC'de hata ararrdi.
//
// Dogrusu: iki kenarin ornekleri once kendi yazmaclarina alinip,
// SONRAKI yukselen kenarda BIRLIKTE cikisa veriliyor. Bir cevrim
// gecikme oluyor ama ikisi ayni bit periyoduna ait.
//
// Bu hatayi tb_ecp5_sim.v yakaladi. Modelin kendi testi olmasaydi
// butun sistem testi bu kayikligin uzerine kurulurdu.
//
// RGMII'de once ALT nibble geliyor (yukselen kenar), sonra UST
// (dusen kenar) — tb_rgmii_alis.v'deki bayt_ver gorevi de boyle
// suruyor. Yani Q0 alt, Q1 ust nibble.
// ---------------------------------------------------------------------
module IDDRX1F (
    input  wire SCLK,
    input  wire RST,
    input  wire D,
    output reg  Q0,
    output reg  Q1
);
    reg d_pos = 1'b0, d_neg = 1'b0;
    always @(posedge SCLK or posedge RST)
        if (RST) d_pos <= 1'b0;
        else     d_pos <= D;
    always @(negedge SCLK or posedge RST)
        if (RST) d_neg <= 1'b0;
        else     d_neg <= D;
    always @(posedge SCLK or posedge RST)
        if (RST) begin Q0 <= 1'b0; Q1 <= 1'b0; end
        else     begin Q0 <= d_pos; Q1 <= d_neg; end
endmodule

// ---------------------------------------------------------------------
// EHXPLLL — PLL
//
// Cikis frekansi parametrelerden hesaplaniyor. FEEDBK_PATH="CLKOP"
// oldugunda geri besleme CLKOP'tan alindigi icin:
//
//     f_PFD  = CLKI / CLKI_DIV
//     CLKOP  = f_PFD * CLKFB_DIV
//
// Karttaki degerlerle: 80 MHz / 16 = 5 MHz, x25 = 125 MHz. RGMII
// verici saati bu — 1000BASE-T icin dogru deger.
//
// Model CLKI'nin periyodunu OLCUP calisiyor, sabit bir sayiya
// gomulmuyor: test tezgahi giris saatini degistirirse cikis da
// dogru degisiyor ve model sessizce yanlis olmuyor.
//
// LOCK, olcum tamamlaninca yukseliyor. Gercek PLL'de kilitlenme
// mikrosaniyeler suruyor; burada birkac cevrim. Onemli olan
// LOCK'un BASLANGICTA DUSUK olmasi — ust.v reseti ona bagliyor ve
// eger model LOCK'u sabit 1 verseydi resetin calisip calismadigi
// hic test edilmemis olurdu.
// ---------------------------------------------------------------------
module EHXPLLL #(
    parameter CLKI_DIV = 1,
    parameter CLKFB_DIV = 1,
    parameter CLKOP_DIV = 1,
    parameter CLKOS_DIV = 1,
    parameter CLKOP_CPHASE = 0,
    parameter CLKOP_FPHASE = 0,
    parameter CLKOS_CPHASE = 0,
    parameter CLKOS_FPHASE = 0,
    parameter FEEDBK_PATH = "CLKOP",
    parameter CLKOP_ENABLE = "ENABLED",
    parameter CLKOS_ENABLE = "DISABLED",
    parameter INTFB_WAKE = "DISABLED",
    parameter STDBY_ENABLE = "DISABLED",
    parameter PLLRST_ENA = "DISABLED",
    parameter DPHASE_SOURCE = "DISABLED"
) (
    input  wire CLKI,
    input  wire CLKFB,
    input  wire RST,
    input  wire STDBY,
    input  wire PHASESEL0, PHASESEL1, PHASEDIR,
    input  wire PHASESTEP, PHASELOADREG,
    input  wire PLLWAKESYNC, ENCLKOP,
    output reg  CLKOP,
    output reg  CLKOS,
    output reg  LOCK
);
    real t_giris = 0.0;
    real t_kenar = 0.0;
    real periyot_op;
    integer olcum = 0;

    initial begin CLKOP = 1'b0; CLKOS = 1'b0; LOCK = 1'b0; end

    // giris periyodunu olc
    always @(posedge CLKI) begin
        if (t_kenar > 0.0) begin
            t_giris = $realtime - t_kenar;
            olcum = olcum + 1;
        end
        t_kenar = $realtime;
    end

    // olcum oturunca cikis saatini uret
    initial begin
        wait (olcum >= 2);
        periyot_op = t_giris * CLKI_DIV / CLKFB_DIV;
        #1 LOCK = 1'b1;
        forever begin
            #(periyot_op / 2.0) CLKOP = ~CLKOP;
        end
    end
endmodule

`default_nettype wire
