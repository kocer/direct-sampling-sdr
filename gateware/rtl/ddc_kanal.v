// Tek alis kanali — NCO, karistirici, CIC ve telafi bir arada.
//
// Dort tane kosacak. Bu dosyanin varlik sebebi kaynak butcesini
// olculebilir kilmak: bir kanalin maliyeti belliyse dordunun de belli.
//
// KANAL BASINA CARPAN:
//     karistirici   2   (I ve Q)
//     telafi FIR    12  (6 simetrik cift x 2 yol)
//     CIC           0   (carpan kullanmiyor — zaten sebebi bu)
//     toplam       14
// Dort kanal 56 carpan eder. ECP5-25F'te 28 MULT18X18 var.
// SIGMIYOR — ve bu, ancak sentezleyip olcunce goruluyor.
//
// Cozum: telafi FIR'i dort kanal ARASINDA PAYLASMAK. Cikis hizi
// 1.25 MSPS, sistem saati 80 MHz; bir carpan cevrim basina bir
// carpim yapiyor, yani 64 kat bos zaman var. Sekiz yolu (4 kanal x
// I,Q) tek FIR motoruyla sirayla islemek fazlasiyla mumkun.
//
// Simdilik kanal tam bagimsiz yaziliyor; paylasimli surum sonraki
// adim. Once olcup gormek gerek, tahminle tasarlamamak icin.

`default_nettype none

module ddc_kanal #(
    parameter ADC_BIT = 14,
    parameter CIK_BIT = 24
) (
    input  wire                       clk,
    input  wire                       rst,
    input  wire signed [ADC_BIT-1:0]  adc,
    input  wire                       adc_gecerli,
    input  wire [31:0]                faz_artis,
    input  wire [31:0]                faz_ofset,
    input  wire                       faz_yukle,
    input  wire [11:0]                azalt_orani,
    output wire signed [CIK_BIT-1:0]  i_cik,
    output wire signed [CIK_BIT-1:0]  q_cik,
    output wire                       cikis_gecerli
);

    wire signed [15:0] nco_s, nco_c;
    wire signed [15:0] mix_i, mix_q;
    wire               mix_gecerli;
    wire signed [23:0] cic_i, cic_q;
    wire               cic_i_gecerli, cic_q_gecerli;

    nco u_nco (
        .clk(clk), .rst(rst),
        .faz_artis(faz_artis), .faz_ofset(faz_ofset),
        .yukle_ofset(faz_yukle),
        .sin_cik(nco_s), .cos_cik(nco_c)
    );

    karistirici u_mix (
        .clk(clk), .rst(rst),
        .giris(adc), .giris_gecerli(adc_gecerli),
        .nco_sin(nco_s), .nco_cos(nco_c),
        .i_cik(mix_i), .q_cik(mix_q), .cikis_gecerli(mix_gecerli)
    );

    cic_azalt #(.GIRIS_BIT(16), .CIKIS_BIT(24)) u_cic_i (
        .clk(clk), .rst(rst), .oran(azalt_orani),
        .giris(mix_i), .giris_gecerli(mix_gecerli),
        .cikis(cic_i), .cikis_gecerli(cic_i_gecerli)
    );

    cic_azalt #(.GIRIS_BIT(16), .CIKIS_BIT(24)) u_cic_q (
        .clk(clk), .rst(rst), .oran(azalt_orani),
        .giris(mix_q), .giris_gecerli(mix_gecerli),
        .cikis(cic_q), .cikis_gecerli(cic_q_gecerli)
    );

    // CIC 24 bit veriyor, FIR 17 bit aliyor: ust 17 biti al.
    // Kaybedilen alt 7 bit, CIC'in kazanci geri alindiktan sonra
    // zaten gurultunun altinda kaliyor.
    wire signed [16:0] fir_gi = cic_i[23:7];
    wire signed [16:0] fir_gq = cic_q[23:7];

    fir_telafi u_fir_i (
        .clk(clk), .rst(rst),
        .giris(fir_gi), .giris_gecerli(cic_i_gecerli),
        .cikis(i_cik), .cikis_gecerli(cikis_gecerli)
    );

    fir_telafi u_fir_q (
        .clk(clk), .rst(rst),
        .giris(fir_gq), .giris_gecerli(cic_q_gecerli),
        .cikis(q_cik), .cikis_gecerli()
    );

endmodule

`default_nettype wire
