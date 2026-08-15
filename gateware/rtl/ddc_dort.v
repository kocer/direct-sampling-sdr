// Dort kanalli DDC — paylasimli telafi FIR ile.
//
// Kaynak butcesi olculdu, tahmin edilmedi:
//
//   ayri FIR ile      kanal basina 14 carpan  x4 = 56   SIGMIYOR
//   paylasimli FIR    4x2 karistirici + 6 FIR = 14      sigiyor
//
// ECP5-25F'te 28 MULT18X18 var. Yarisi bos kaliyor, kalanini DPD ve
// veris yolu kullanacak.
//
// DORT KANAL AYNI SAAT ALANINDA. Faz uyumunun tek sarti bu; kanal
// basina PLL kullanilsaydi aralarindaki faz belirsizligi kalibre
// edilemezdi.
//
// FIR SIRALAMASI: sekiz yol (4 kanal x I,Q) sirayla motora giriyor.
// CIC'ler ayni anda cikis verdigi icin araya kucuk bir sira tamponu
// koyuyoruz; cikis hizi 1.25 MSPS ve saat 80 MHz oldugu icin sekiz
// yolun hepsi rahat yetisiyor.

`default_nettype none

module ddc_dort #(
    parameter ADC_BIT = 14,
    parameter CIK_BIT = 24
) (
    input  wire                        clk,
    input  wire                        rst,

    input  wire signed [ADC_BIT-1:0]   adc0,
    input  wire signed [ADC_BIT-1:0]   adc1,
    input  wire signed [ADC_BIT-1:0]   adc2,
    input  wire signed [ADC_BIT-1:0]   adc3,
    input  wire                        adc_gecerli,

    input  wire [31:0]                 faz_artis,
    input  wire [31:0]                 faz_ofset0,
    input  wire [31:0]                 faz_ofset1,
    input  wire [31:0]                 faz_ofset2,
    input  wire [31:0]                 faz_ofset3,
    input  wire                        faz_yukle,
    input  wire [11:0]                 azalt_orani,

    // PORTTA DIZI YOK. yosys port listesinde paketlenmemis dizi
    // kabul etmiyor; dort kanali ayri ayri yaziyoruz. Ic tarafta
    // dizi kullanmaya devam ediyoruz.
    output wire signed [CIK_BIT-1:0]   i_cik0,
    output wire signed [CIK_BIT-1:0]   i_cik1,
    output wire signed [CIK_BIT-1:0]   i_cik2,
    output wire signed [CIK_BIT-1:0]   i_cik3,
    output wire signed [CIK_BIT-1:0]   q_cik0,
    output wire signed [CIK_BIT-1:0]   q_cik1,
    output wire signed [CIK_BIT-1:0]   q_cik2,
    output wire signed [CIK_BIT-1:0]   q_cik3,
    output reg  [3:0]                  kanal_gecerli
);

    // ---------------------------------------------------------------
    // Kanal on ucu: NCO + karistirici + iki CIC. FIR paylasimli.
    // ---------------------------------------------------------------
    wire signed [23:0] cic_i [0:3];
    wire signed [23:0] cic_q [0:3];
    wire [3:0] cic_gecerli;

    genvar g;
    generate
        for (g = 0; g < 4; g = g + 1) begin : kanal
            wire signed [ADC_BIT-1:0] adc_g =
                (g == 0) ? adc0 : (g == 1) ? adc1 :
                (g == 2) ? adc2 : adc3;
            wire [31:0] ofset_g =
                (g == 0) ? faz_ofset0 : (g == 1) ? faz_ofset1 :
                (g == 2) ? faz_ofset2 : faz_ofset3;

            wire signed [15:0] ns, nc, mi, mq;
            wire mv, qv;

            nco u_nco (.clk(clk), .rst(rst), .izin(1'b1),
                       .faz_artis(faz_artis), .faz_ofset(ofset_g),
                       .yukle_ofset(faz_yukle),
                       .sin_cik(ns), .cos_cik(nc));

            karistirici u_mix (.clk(clk), .rst(rst),
                               .giris(adc_g), .giris_gecerli(adc_gecerli),
                               .nco_sin(ns), .nco_cos(nc),
                               .i_cik(mi), .q_cik(mq),
                               .cikis_gecerli(mv));

            cic_azalt #(.GIRIS_BIT(16), .CIKIS_BIT(24)) u_ci (
                .clk(clk), .rst(rst), .oran(azalt_orani),
                .giris(mi), .giris_gecerli(mv),
                .cikis(cic_i[g]), .cikis_gecerli(cic_gecerli[g]));

            cic_azalt #(.GIRIS_BIT(16), .CIKIS_BIT(24)) u_cq (
                .clk(clk), .rst(rst), .oran(azalt_orani),
                .giris(mq), .giris_gecerli(mv),
                .cikis(cic_q[g]), .cikis_gecerli(qv));
        end
    endgenerate

    // ---------------------------------------------------------------
    // Sekiz yolu sirayla FIR'a ver.
    // Yol numarasi: {kanal[1:0], iq} — cift I, tek Q.
    // ---------------------------------------------------------------
    reg [3:0]  sira;          // 0..7 tur, 8 = bos
    reg        sira_calisiyor;

    always @(posedge clk) begin
        if (rst) begin
            sira           <= 4'd8;
            sira_calisiyor <= 1'b0;
        end else if (cic_gecerli[0] && !sira_calisiyor) begin
            // dort CIC ayni anda cikis veriyor; birini tetik say
            sira           <= 4'd0;
            sira_calisiyor <= 1'b1;
        end else if (sira_calisiyor) begin
            if (sira == 4'd7) begin
                sira           <= 4'd8;
                sira_calisiyor <= 1'b0;
            end else begin
                sira <= sira + 1'b1;
            end
        end
    end

    wire [1:0] sira_kanal = sira[2:1];
    wire       sira_iq    = sira[0];

    wire signed [16:0] fir_giris =
        sira_iq ? cic_q[sira_kanal][23:7] : cic_i[sira_kanal][23:7];

    wire [2:0]         fir_yol;
    wire signed [23:0] fir_cikis;
    wire               fir_gecerli;

    fir_paylasimli u_fir (
        .clk(clk), .rst(rst),
        .yol_no(sira[2:0]),
        .giris(fir_giris),
        .giris_gecerli(sira_calisiyor),
        .cikis_yol(fir_yol),
        .cikis(fir_cikis),
        .cikis_gecerli(fir_gecerli)
    );

    // ---------------------------------------------------------------
    // Cikisi yol numarasina gore dagit
    // ---------------------------------------------------------------
    reg signed [CIK_BIT-1:0] i_reg [0:3];
    reg signed [CIK_BIT-1:0] q_reg [0:3];
    assign i_cik0 = i_reg[0];  assign q_cik0 = q_reg[0];
    assign i_cik1 = i_reg[1];  assign q_cik1 = q_reg[1];
    assign i_cik2 = i_reg[2];  assign q_cik2 = q_reg[2];
    assign i_cik3 = i_reg[3];  assign q_cik3 = q_reg[3];

    integer c;
    always @(posedge clk) begin
        if (rst) begin
            kanal_gecerli <= 4'd0;
            for (c = 0; c < 4; c = c + 1) begin
                i_reg[c] <= {CIK_BIT{1'b0}};
                q_reg[c] <= {CIK_BIT{1'b0}};
            end
        end else begin
            kanal_gecerli <= 4'd0;
            if (fir_gecerli) begin
                if (fir_yol[0])
                    q_reg[fir_yol[2:1]] <= fir_cikis;
                else
                    i_reg[fir_yol[2:1]] <= fir_cikis;
                // kanal tamam: Q geldiginde I zaten gelmisti
                if (fir_yol[0])
                    kanal_gecerli[fir_yol[2:1]] <= 1'b1;
            end
        end
    end

endmodule

`default_nettype wire
