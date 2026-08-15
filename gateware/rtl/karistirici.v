// Karistirici — gercek girisi karmasik taban banda indiriyor.
//
//     I = giris * cos(w t)
//     Q = giris * -sin(w t)
//
// Girisin negatif frekans bileseni +2w'ye, pozitif bileseni sifira
// gidiyor. Sifira gelen kaliyor, oteki azaltmada suzuluyor.
//
// NEDEN KARMASIK: gercek bir sinyalde pozitif ve negatif frekans
// ayni; ikisini ayirmadan azaltirsan ust ust biner (ayna girisimi).
// Karmasik taban bantta yan bantlar ayri kalir, yani USB ile LSB'yi
// sonradan sayisal olarak ayirabiliyoruz.
//
// CARPAN: kanal basina iki adet (I ve Q). Dort kanal = 8 carpan.
// ECP5-25F'te 28 MULT18X18 var; kalan 20 tanesi FIR'lara.
//
// GENISLIK: 14 bit giris x 16 bit NCO = 30 bit. Ust 16 biti aliyoruz
// ama YUVARLAYARAK — duz kirpma her ornekte asagi yonlu sabit bir
// hata birakir, ve o hata karistiricinin cikisinda DC olarak gorunur.
// Dogrudan ornekleme alicisinda DC, spektrumun tam ortasinda duran
// sahte bir tasiyici demek.

`default_nettype none

module karistirici #(
    parameter GIRIS_BIT = 14,
    parameter NCO_BIT   = 16,
    parameter CIKIS_BIT = 16
) (
    input  wire                          clk,
    input  wire                          rst,
    input  wire signed [GIRIS_BIT-1:0]   giris,
    input  wire                          giris_gecerli,
    input  wire signed [NCO_BIT-1:0]     nco_sin,
    input  wire signed [NCO_BIT-1:0]     nco_cos,
    output reg  signed [CIKIS_BIT-1:0]   i_cik,
    output reg  signed [CIKIS_BIT-1:0]   q_cik,
    output reg                           cikis_gecerli
);

    localparam CARP_BIT = GIRIS_BIT + NCO_BIT;      // 30
    localparam KAYDIR   = CARP_BIT - CIKIS_BIT - 1; // isaret biti bir kez

    reg signed [CARP_BIT-1:0] carp_i, carp_q;
    reg                       carp_gecerli;

    always @(posedge clk) begin
        if (rst) begin
            carp_i       <= {CARP_BIT{1'b0}};
            carp_q       <= {CARP_BIT{1'b0}};
            carp_gecerli <= 1'b0;
        end else begin
            carp_i       <= giris * nco_cos;
            carp_q       <= -(giris * nco_sin);
            carp_gecerli <= giris_gecerli;
        end
    end

    // YUVARLAMA: kesilen kismin en ust bitini ekle.
    // "+ yarim, sonra kes" — en yakina yuvarlama.
    wire signed [CARP_BIT-1:0] yuvarlak_i =
        carp_i + {{(CARP_BIT-KAYDIR){1'b0}}, 1'b1, {(KAYDIR-1){1'b0}}};
    wire signed [CARP_BIT-1:0] yuvarlak_q =
        carp_q + {{(CARP_BIT-KAYDIR){1'b0}}, 1'b1, {(KAYDIR-1){1'b0}}};

    always @(posedge clk) begin
        if (rst) begin
            i_cik         <= {CIKIS_BIT{1'b0}};
            q_cik         <= {CIKIS_BIT{1'b0}};
            cikis_gecerli <= 1'b0;
        end else begin
            i_cik         <= yuvarlak_i[KAYDIR +: CIKIS_BIT];
            q_cik         <= yuvarlak_q[KAYDIR +: CIKIS_BIT];
            cikis_gecerli <= carp_gecerli;
        end
    end

endmodule

`default_nettype wire
