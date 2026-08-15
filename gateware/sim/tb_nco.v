// NCO test tezgahi — frekans dogrulugu ve spektral saflik.
//
// Iki sey olculuyor:
//
// 1 FREKANS. Faz artisindan beklenen frekans:
//       f = f_saat * artis / 2^32
//   Cikisin sifir gecislerini sayip karsilastiriyoruz. Tutmuyorsa
//   ya biriktirici genisligi ya tablo adresi yanlis.
//
// 2 GENLIK. sin^2 + cos^2 sabit olmali. Degisiyorsa tablonun ceyrek
//   dalga katlamasi yanlis — bu hata dinlerken duyulmaz ama
//   spektrumda yan bant olarak cikar ve zayif sinyali gomer.

`timescale 1ns/1ps
`default_nettype none

module tb_nco;

    localparam FAZ_BIT = 32;
    localparam CIK_BIT = 16;
    localparam real F_SAAT = 80.0e6;

    reg clk = 0;
    reg rst = 1;
    reg [FAZ_BIT-1:0] artis = 0;
    wire signed [CIK_BIT-1:0] sin_c, cos_c;

    always #6.25 clk = ~clk;      // 80 MHz

    nco #(.FAZ_BIT(FAZ_BIT), .CIK_BIT(CIK_BIT)) dut (
        .clk(clk), .rst(rst),
        .faz_artis(artis), .faz_ofset({FAZ_BIT{1'b0}}),
        .yukle_ofset(1'b0), .izin(1'b1),
        .sin_cik(sin_c), .cos_cik(cos_c)
    );

    integer gecis;
    integer n;
    real    beklenen, olculen, hata;
    reg signed [CIK_BIT-1:0] onceki;
    integer buyukluk_min, buyukluk_maks;
    integer buyukluk;

    task olc(input [FAZ_BIT-1:0] a, input real f_hedef);
        begin
            artis = a;
            rst = 1; #50; @(posedge clk); #1; rst = 0;
            gecis = 0;
            buyukluk_maks = 0;
            buyukluk_min = 1 << 30;
            onceki = 0;
            for (n = 0; n < 200000; n = n + 1) begin
                @(posedge clk);
                // sifir gecisi (asagidan yukari)
                if (onceki < 0 && sin_c >= 0) gecis = gecis + 1;
                onceki = sin_c;
                // genlik: sin^2 + cos^2
                buyukluk = (sin_c * sin_c + cos_c * cos_c) >>> 20;
                if (n > 100) begin
                    if (buyukluk > buyukluk_maks) buyukluk_maks = buyukluk;
                    if (buyukluk < buyukluk_min)  buyukluk_min  = buyukluk;
                end
            end
            olculen = gecis * F_SAAT / 200000.0;
            hata = (olculen - f_hedef) / f_hedef * 100.0;
            $display("  artis %10d -> beklenen %9.1f Hz  olculen %9.1f Hz  hata %6.3f %%",
                     a, f_hedef, olculen, hata);
            if (hata > 0.5 || hata < -0.5) begin
                $display("  HATA: frekans tutmuyor");
                $fatal;
            end
            $display("     genlik degisimi: %0d .. %0d  (%0d %%)",
                     buyukluk_min, buyukluk_maks,
                     (buyukluk_maks - buyukluk_min) * 100 / buyukluk_maks);
            if ((buyukluk_maks - buyukluk_min) * 100 > buyukluk_maks * 5) begin
                $display("  HATA: genlik %%5'ten fazla degisiyor — tablo katlamasi bozuk");
                $fatal;
            end
        end
    endtask

    initial begin
        $display("NCO testi");
        // 7.1 MHz: 40 m bandi
        olc(32'd381120000 / 1, 7.1e6);
        // 14.2 MHz: 20 m
        olc(32'd762240000, 14.2e6);
        // 1.85 MHz: 160 m
        olc(32'd99320000, 1.85e6);
        $display("NCO testi GECTI");
        $finish;
    end

endmodule

`default_nettype wire
