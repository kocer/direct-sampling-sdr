// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// ECP5 SIMULASYON MODELLERININ KENDI TESTI.
//
// Sistem testi bu modellerin uzerinde duruyor. Model yanlissa sistem
// testi gecer ve hicbir sey kanitlamaz — en kotu test turu budur,
// cunku guven verir.
//
// Uc modelin de davranisi ust.v'nin ONLARDAN BEKLEDIGI seyle
// karsilastiriliyor, veri sayfasi ezberiyle degil.

`timescale 1ns/1ps
`default_nettype none

module tb_ecp5_sim;

    integer hata = 0;

    // ---------------------------------------------------------------
    reg sclk = 1'b0;
    always #4 sclk = ~sclk;           // 125 MHz
    reg rst = 1'b1;

    // ---- ODDRX1F: saat uretimi (D0=1, D1=0)
    wire q_saat;
    ODDRX1F u_saat (.SCLK(sclk), .RST(rst), .D0(1'b1), .D1(1'b0),
                    .Q(q_saat));

    // ---- ODDRX1F: dusen kenarda yukselen darbe (D0=0, D1=1)
    wire q_wrt;
    ODDRX1F u_wrt (.SCLK(sclk), .RST(rst), .D0(1'b0), .D1(1'b1),
                   .Q(q_wrt));

    // ---- IDDRX1F: iki kenardan ornekleme
    reg  d_in = 1'b0;
    wire q0, q1;
    IDDRX1F u_iddr (.SCLK(sclk), .RST(rst), .D(d_in), .Q0(q0), .Q1(q1));

    // ---- EHXPLLL: 80 -> 125 MHz
    reg clk80 = 1'b0;
    always #6.25 clk80 = ~clk80;      // 80 MHz
    wire clk_pll, kilit;
    EHXPLLL #(.CLKI_DIV(16), .CLKFB_DIV(25), .CLKOP_DIV(5),
              .FEEDBK_PATH("CLKOP"))
      u_pll (.CLKI(clk80), .CLKFB(clk_pll), .RST(1'b0), .STDBY(1'b0),
             .PHASESEL0(1'b0), .PHASESEL1(1'b0), .PHASEDIR(1'b0),
             .PHASESTEP(1'b0), .PHASELOADREG(1'b0),
             .PLLWAKESYNC(1'b0), .ENCLKOP(1'b0),
             .CLKOP(clk_pll), .LOCK(kilit));

    real t_pll_kenar = 0.0, t_pll_periyot = 0.0;
    always @(posedge clk_pll) begin
        if (t_pll_kenar > 0.0) t_pll_periyot = $realtime - t_pll_kenar;
        t_pll_kenar = $realtime;
    end

    // ---------------------------------------------------------------
    initial begin
        $display("ECP5 model testi");
        repeat (4) @(posedge sclk); #1 rst = 1'b0;
        repeat (2) @(posedge sclk);

        // ---- 1. ODDR saat uretimi: Q, SCLK ile ayni fazda olmali
        begin : saat
            integer yanlis;
            yanlis = 0;
            repeat (8) begin
                @(posedge sclk); #1;
                if (q_saat !== 1'b1) yanlis = yanlis + 1;
                @(negedge sclk); #1;
                if (q_saat !== 1'b0) yanlis = yanlis + 1;
            end
            if (yanlis) begin
                $display("  HATA: ODDR(1,0) saat uretmiyor (%0d kacak)",
                         yanlis);
                hata = hata + 1;
            end else
                $display("  ODDR(1,0) = SCLK ile ayni fazda saat");
        end

        // ---- 2. ODDR yazma darbesi: DUSEN kenarda yukselmeli
        //      dac_cogullu.v'nin kurulum suresi hesabi buna dayaniyor.
        begin : wrt
            integer yanlis;
            yanlis = 0;
            repeat (8) begin
                @(posedge sclk); #1;
                if (q_wrt !== 1'b0) yanlis = yanlis + 1;
                @(negedge sclk); #1;
                if (q_wrt !== 1'b1) yanlis = yanlis + 1;
            end
            if (yanlis) begin
                $display("  HATA: ODDR(0,1) dusen kenarda yukselmiyor");
                $display("        dac_cogullu'nun 6.25 ns kurulum payi");
                $display("        bu davranisa dayaniyor");
                hata = hata + 1;
            end else
                $display("  ODDR(0,1) = dusen kenarda yukselen darbe");
        end

        // ---- 3. IDDR: bir bit periyodunun IKI YARISI ayni cevrimde
        //
        // IKI KEZ YANLIS YAZDIM, ikisi de ogreticiydi:
        //
        //   Once veriyi kenarin tam uzerinde degistiriyordum — yaris.
        //   Sonra suren ve dinleyen bloklar ayni dongu degiskenini
        //   paylasti ve test kendi kendini bozdu ("bit 4" diye olmayan
        //   bir indis raporladi).
        //
        // Ayrica GECIKMEYI VARSAYMAK da yanlisti. Modelin kac cevrim
        // gecikme yaptigi test edilecek seyin bir parcasi degil; onemli
        // olan Q0 ile Q1'in AYNI bit periyoduna ait olmasi. O yuzden
        // test once butun cikisi topluyor, sonra hangi kaymada
        // tuttugunu ARIYOR ve bulunan kaymayi raporluyor.
        //
        // Bu, rgmii_alis.v'nin varsayimi: rd_yuk ve rd_dus tek bayta
        // birlestiriliyor.
        begin : iddr
            reg [7:0] gonder_r, gonder_f;
            reg [7:0] alinan_0, alinan_1;
            integer   n, k, kayma, eslesme, uyan;
            gonder_r = 8'b1010_0110;
            gonder_f = 8'b1100_1001;
            alinan_0 = 8'h00; alinan_1 = 8'h00;
            fork
                begin : suren
                    integer si;
                    for (si = 0; si < 8; si = si + 1) begin
                        @(negedge sclk); #1 d_in = gonder_r[si];
                        @(posedge sclk); #1 d_in = gonder_f[si];
                    end
                end
                begin : dinleyen
                    integer di;
                    for (di = 0; di < 8; di = di + 1) begin
                        @(posedge sclk); #2;
                        alinan_0[di] = q0;
                        alinan_1[di] = q1;
                    end
                end
            join
            // hangi kaymada tutuyor
            uyan = -1;
            for (kayma = 0; kayma < 4; kayma = kayma + 1) begin
                eslesme = 1;
                for (k = 0; k + kayma < 8 && k < 4; k = k + 1)
                    if (alinan_0[k + kayma] !== gonder_r[k] ||
                        alinan_1[k + kayma] !== gonder_f[k])
                        eslesme = 0;
                if (eslesme && uyan < 0) uyan = kayma;
            end
            if (uyan < 0) begin
                $display("  HATA: IDDR cikisi hicbir kaymada tutmuyor");
                $display("        gonderilen R=%b F=%b", gonder_r, gonder_f);
                $display("        alinan    0=%b 1=%b", alinan_0, alinan_1);
                $display("        Q0 ve Q1 ayni bit periyoduna ait degil;");
                $display("        kartta belirtisi 'her cerceve CRC hatasi'");
                $display("        olurdu ve insan CRC'de hata arardi.");
                hata = hata + 1;
            end else
                $display("  IDDR: iki yarim hizali (gecikme %0d cevrim)",
                         uyan);
        end

        // ---- 4. PLL: 80 MHz -> 125 MHz, ve LOCK bastan 0
        if (!kilit) begin
            $display("  HATA: PLL bu noktada kilitlenmis olmaliydi");
            hata = hata + 1;
        end
        #200;
        if (t_pll_periyot < 7.9 || t_pll_periyot > 8.1) begin
            $display("  HATA: PLL periyodu %.3f ns, 8.000 bekleniyordu",
                     t_pll_periyot);
            $display("        (80/16*25 = 125 MHz)");
            hata = hata + 1;
        end else
            $display("  PLL 80 -> %.1f MHz", 1000.0 / t_pll_periyot);

        if (hata == 0) $display("ECP5 model testi GECTI");
        else           $display("ECP5 model testi KALDI: %0d hata", hata);
        $finish;
    end

    // LOCK baslangicta dusuk olmali — ust.v reseti buna bagli
    initial begin
        #1;
        if (kilit !== 1'b0) begin
            $display("  HATA: LOCK baslangicta 1; resetin calisip");
            $display("        calismadigi hic test edilemezdi");
            hata = hata + 1;
        end
    end

    initial begin
        #100_000;
        $display("ECP5 model testi KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
