// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// MULT18X18D — SIMULASYON MODELI, SADECE KAPI DUZEYI KOSU ICIN.
//
// yosys'in ecp5 kutuphanesinde bu hucrenin davranis modeli yok (ne
// cells_sim.v'de ne digerlerinde), sadece kara kutu bildirimi var.
// Kapi duzeyi simulasyonda 22 adedi kullaniliyor — NCO'nun sinus
// carpimlari ve karistiricinin carpimlari — ve modelsiz olunca
// sentez sonrasi netlist kosturulamiyor.
//
// YAPILANDIRMA: sentez sonrasi netliste bu hucrenin HIC PARAMETRESI
// YOK, yani hepsi ontanimli. Ontanimda giris/cikis yazmaclari
// kapali (REG_*_CLK = "NONE"), dolayisiyla hucre SAF BIRLESIMSEL bir
// carpan: P = A * B.
//
// Isaret SIGNEDA/SIGNEDB ile geliyor. Bu tasarimda ikisi de isaretli
// (NCO cikisi ve ADC ornegi ikisi de isaretli), ama model ikisini de
// ayri ayri destekliyor — sabitlemek, parametre degisirse sessizce
// yanlis olmak demekti.
//
// C girisi ve SOURCEA/SOURCEB kullanilmiyor; kaskad ve toplama
// kipleri bu tasarimda devrede degil. Portlar yine de tanimli, cunku
// netlist onlari BAGLIYOR ve tanimsiz port baglama hatasi verir.

`default_nettype none

module MULT18X18D (
    input  wire A0,  A1,  A2,  A3,  A4,  A5,  A6,  A7,  A8,
    input  wire A9,  A10, A11, A12, A13, A14, A15, A16, A17,
    input  wire B0,  B1,  B2,  B3,  B4,  B5,  B6,  B7,  B8,
    input  wire B9,  B10, B11, B12, B13, B14, B15, B16, B17,
    input  wire C0,  C1,  C2,  C3,  C4,  C5,  C6,  C7,  C8,
    input  wire C9,  C10, C11, C12, C13, C14, C15, C16, C17,
    input  wire SIGNEDA, SIGNEDB, SOURCEA, SOURCEB,
    input  wire CLK0, CLK1, CLK2, CLK3,
    input  wire CE0, CE1, CE2, CE3,
    input  wire RST0, RST1, RST2, RST3,
    input  wire SRIA0,  SRIA1,  SRIA2,  SRIA3,  SRIA4,  SRIA5,
    input  wire SRIA6,  SRIA7,  SRIA8,  SRIA9,  SRIA10, SRIA11,
    input  wire SRIA12, SRIA13, SRIA14, SRIA15, SRIA16, SRIA17,
    input  wire SRIB0,  SRIB1,  SRIB2,  SRIB3,  SRIB4,  SRIB5,
    input  wire SRIB6,  SRIB7,  SRIB8,  SRIB9,  SRIB10, SRIB11,
    input  wire SRIB12, SRIB13, SRIB14, SRIB15, SRIB16, SRIB17,
    output wire P0,  P1,  P2,  P3,  P4,  P5,  P6,  P7,  P8,
    output wire P9,  P10, P11, P12, P13, P14, P15, P16, P17,
    output wire P18, P19, P20, P21, P22, P23, P24, P25, P26,
    output wire P27, P28, P29, P30, P31, P32, P33, P34, P35,
    output wire SROA0,  SROA1,  SROA2,  SROA3,  SROA4,  SROA5,
    output wire SROA6,  SROA7,  SROA8,  SROA9,  SROA10, SROA11,
    output wire SROA12, SROA13, SROA14, SROA15, SROA16, SROA17,
    output wire SROB0,  SROB1,  SROB2,  SROB3,  SROB4,  SROB5,
    output wire SROB6,  SROB7,  SROB8,  SROB9,  SROB10, SROB11,
    output wire SROB12, SROB13, SROB14, SROB15, SROB16, SROB17,
    output wire SIGNEDP
);
    wire [17:0] a = {A17, A16, A15, A14, A13, A12, A11, A10, A9,
                     A8,  A7,  A6,  A5,  A4,  A3,  A2,  A1,  A0};
    wire [17:0] b = {B17, B16, B15, B14, B13, B12, B11, B10, B9,
                     B8,  B7,  B6,  B5,  B4,  B3,  B2,  B1,  B0};

    // Isaret genisletme SIGNEDA/SIGNEDB'ye gore. Ikisi 19 bite
    // genisletilip carpiliyor; sonucun alt 36 biti P.
    wire signed [18:0] as = {SIGNEDA & a[17], a};
    wire signed [18:0] bs = {SIGNEDB & b[17], b};
    wire signed [37:0] p  = as * bs;

    assign {P35, P34, P33, P32, P31, P30, P29, P28, P27,
            P26, P25, P24, P23, P22, P21, P20, P19, P18,
            P17, P16, P15, P14, P13, P12, P11, P10, P9,
            P8,  P7,  P6,  P5,  P4,  P3,  P2,  P1,  P0} = p[35:0];

    assign SIGNEDP = SIGNEDA | SIGNEDB;

    // kaskad cikislari kullanilmiyor
    assign {SROA17, SROA16, SROA15, SROA14, SROA13, SROA12,
            SROA11, SROA10, SROA9,  SROA8,  SROA7,  SROA6,
            SROA5,  SROA4,  SROA3,  SROA2,  SROA1,  SROA0} = 18'd0;
    assign {SROB17, SROB16, SROB15, SROB14, SROB13, SROB12,
            SROB11, SROB10, SROB9,  SROB8,  SROB7,  SROB6,
            SROB5,  SROB4,  SROB3,  SROB2,  SROB1,  SROB0} = 18'd0;
endmodule

`default_nettype wire
