// DDC zinciri testi — NCO + karistirici + CIC birlikte.
//
// Bu testin sordugu soru sudur: anten girisine bilinen bir sinus
// koyarsam, cikista dogru genlikte ve dogru frekansta bir sey
// aliyor muyum?
//
// Uc olcum:
//
// 1 TAM UZERINDE. NCO'yu girisin frekansina kurunca cikis DC olmali
//   (I sabit, Q sabit). Degilse karistirici ya da NCO yanlis.
//
// 2 YANDA. NCO'yu 1 kHz yana kurunca cikis 1 kHz'lik karmasik bir
//   dondu olmali. Genligi ayni kalmali — kalmiyorsa CIC'in gecirme
//   bandi bekledigimizden dar.
//
// 3 BANT DISI. Girisi azaltilmis bandin disina koyunca cikis
//   bastirilmali. Bastirilmiyorsa azaltma ayna girisimi uretiyor ve
//   o girisim gercek sinyalin uzerine biner.

`timescale 1ns/1ps
`default_nettype none

module tb_ddc;

    localparam real F_SAAT  = 80.0e6;
    localparam      FAZ_BIT = 32;
    localparam      R       = 64;

    reg clk = 0, rst = 1;
    always #6.25 clk = ~clk;

    // ------------------------------------------------ giris uretici
    reg [FAZ_BIT-1:0] gir_faz = 0, gir_artis = 0;
    reg signed [13:0] adc;
    reg               adc_gecerli = 0;

    always @(posedge clk) begin
        if (rst) begin
            gir_faz <= 0;
            adc     <= 0;
        end else begin
            gir_faz <= gir_faz + gir_artis;
            // 14 bit tam olcegin yarisi
            adc <= $rtoi($sin(3.14159265358979 * 2.0 *
                   gir_faz / 4294967296.0) * 4000.0);
        end
    end

    // ------------------------------------------------ DDC
    reg [FAZ_BIT-1:0] nco_artis = 0;
    wire signed [15:0] ns, nc;
    wire signed [15:0] mi, mq;
    wire mv;
    wire signed [23:0] ci, cq;
    wire civ, cqv;

    nco u_nco (.clk(clk), .rst(rst), .faz_artis(nco_artis),
               .faz_ofset(32'd0), .yukle_ofset(1'b0),
               .sin_cik(ns), .cos_cik(nc));

    karistirici u_mix (.clk(clk), .rst(rst), .giris(adc),
                       .giris_gecerli(adc_gecerli),
                       .nco_sin(ns), .nco_cos(nc),
                       .i_cik(mi), .q_cik(mq), .cikis_gecerli(mv));

    cic_azalt #(.GIRIS_BIT(16)) u_ci (.clk(clk), .rst(rst), .oran(12'd64),
        .giris(mi), .giris_gecerli(mv), .cikis(ci), .cikis_gecerli(civ));
    cic_azalt #(.GIRIS_BIT(16)) u_cq (.clk(clk), .rst(rst), .oran(12'd64),
        .giris(mq), .giris_gecerli(mv), .cikis(cq), .cikis_gecerli(cqv));

    // ------------------------------------------------ olcum
    integer n;
    integer buyuk_maks, buyuk_min;
    real    buyukluk;
    integer ornek_sayisi;
    reg     izle = 0;

    always @(posedge clk) begin
        if (izle && civ) begin
            ornek_sayisi = ornek_sayisi + 1;
            if (ornek_sayisi > 40) begin
                buyukluk = $sqrt($itor(ci) * $itor(ci) +
                                 $itor(cq) * $itor(cq));
                if ($rtoi(buyukluk) > buyuk_maks) buyuk_maks = $rtoi(buyukluk);
                if ($rtoi(buyukluk) < buyuk_min)  buyuk_min  = $rtoi(buyukluk);
            end
        end
    end

    task kos(input [FAZ_BIT-1:0] gf, input [FAZ_BIT-1:0] nf,
             input [200*8-1:0] ad);
        begin
            rst = 1; adc_gecerli = 0; izle = 0;
            gir_artis = gf; nco_artis = nf;
            #200; @(posedge clk); #1; rst = 0;
            adc_gecerli = 1;
            ornek_sayisi = 0; buyuk_maks = 0; buyuk_min = 1<<30;
            izle = 1;
            for (n = 0; n < 60000; n = n + 1) @(posedge clk);
            izle = 0;
            $display("  %0s", ad);
            $display("     |I+jQ| araligi %0d .. %0d   (%0d ornek)",
                     buyuk_min, buyuk_maks, ornek_sayisi);
        end
    endtask

    // artis = f / 80e6 * 2^32
    localparam [FAZ_BIT-1:0] A_7M1  = 32'd381120000;   // 7.100 MHz
    localparam [FAZ_BIT-1:0] A_7M101= 32'd381173687;   // 7.101 MHz (+1 kHz)
    // BANT DISI FREKANS R'YE BAGLI.
    // R=64'te cikis 1.25 MSPS, Nyquist 625 kHz. Once 400 kHz'i
    // "bant disi" saymistim — bandin ICINDE. Olctugum sey bastirma
    // degil CIC'in sin(x)/x egimiydi (6 dB), ve o egim tam da
    // cic_telafi'nin duzeltecegi sey.
    localparam [FAZ_BIT-1:0] A_9M1  = 32'd488460000;   // +2.0 MHz, gercekten disarda
    localparam [FAZ_BIT-1:0] A_7M4  = 32'd397230000;   // +300 kHz, bant kenari

    initial begin
        $display("DDC zincir testi (R=%0d, cikis hizi %0.1f kSPS)",
                 R, F_SAAT/R/1000.0);
        kos(A_7M1,   A_7M1,  "tam uzerinde: cikis DC olmali, genlik sabit");
        kos(A_7M101, A_7M1,  "1 kHz yanda: genlik ayni, faz donuyor");
        kos(A_7M4,   A_7M1,  "300 kHz yanda: bant kenari, CIC egimi gorunur");
        kos(A_9M1,   A_7M1,  "2 MHz yanda: BANT DISI, bastirilmali");
        $display("DDC zincir testi bitti");
        $finish;
    end

endmodule

`default_nettype wire
