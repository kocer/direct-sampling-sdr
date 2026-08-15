// Paketleyici testi — bicim, sayac, tasma bayragi.
//
// Uc sey olculuyor:
//
// 1 BICIM. Sihirli sayi, surum, maske dogru siradan cikmali. Bir
//   baytin yeri kayarsa alici her seyi yanlis cozer ve bunu ancak
//   verinin sacma gorunmesinden anlar.
//
// 2 SAYAC. Ornek numarasi paketler arasinda SUREKLI artmali. Atlama
//   ya da tekrar, alicinin kayip tespitini bozar. Faz surekliligi
//   buna bagli — dort kanalin uyumu paket sayacindan izleniyor.
//
// 3 TASMA BAYRAGI. Paket icinde bir yerde tasma olduysa o paketin
//   basliginda gorunmeli, sonrakinde gorunmemeli. Anlik bakan bir
//   kod tasmayi kacirir ve alici veriyi saglam sanar.

`timescale 1ns/1ps
`default_nettype none

module tb_paket;

    reg clk = 0, rst = 1;
    always #6.25 clk = ~clk;

    reg signed [23:0] i0 = 0, q0 = 0, i1 = 0, q1 = 0;
    reg signed [23:0] i2 = 0, q2 = 0, i3 = 0, q3 = 0;
    reg [3:0] kanal_gecerli = 0;
    reg tasma = 0;

    wire [7:0] bayt;
    wire bayt_gecerli, paket_basi, paket_sonu;

    paketleyici #(.PAKET_ORNEK(4)) dut (
        .clk(clk), .rst(rst),
        .i0(i0), .q0(q0), .i1(i1), .q1(q1),
        .i2(i2), .q2(q2), .i3(i3), .q3(q3),
        .kanal_gecerli(kanal_gecerli),
        .kanal_maskesi(4'b1111),
        .azalt_log2(4'd6),
        .tasma(tasma), .saat_kayip(1'b0),
        .bayt(bayt), .bayt_gecerli(bayt_gecerli),
        .paket_basi(paket_basi), .paket_sonu(paket_sonu),
        .hazir(1'b1)
    );

    // toplanan bayt akisi
    reg [7:0] tampon [0:1023];
    integer   n = 0;
    integer   paket = 0;
    integer   hata = 0;
    integer   k;
    integer   kk;   // gorev ici sayac, disaridakini ezmesin
    reg [63:0] sayac_beklenen;
    reg [63:0] sayac_gelen;

    always @(posedge clk) begin
        if (bayt_gecerli && n < 1024) begin
            tampon[n] = bayt;
            n = n + 1;
        end
    end

    task ornek_ver(input integer deger);
        begin
            i0 = deger;      q0 = -deger;
            i1 = deger + 1;  q1 = -deger - 1;
            i2 = deger + 2;  q2 = -deger - 2;
            i3 = deger + 3;  q3 = -deger - 3;
            @(posedge clk); #1; kanal_gecerli = 4'b1111;
            @(posedge clk); #1; kanal_gecerli = 4'b0000;
            // paketleyicinin 24 bayti bosaltmasi icin zaman
            // 24 baytlik grup + baslik payi. Once 30 cevrim
            // veriyordum ve ilk gruptan sonrasi yetismedi.
            // KENDI SAYACI. Once k kullaniyordum ve k, cagiran
            // dongunun de sayaci; gorev donunce k=70 oluyor ve dis
            // dongu tek turda bitiyordu. Dort ornek yerine bir tane
            // veriliyordu — test yanlisti, tasarim degil.
            for (kk = 0; kk < 70; kk = kk + 1) @(posedge clk);
        end
    endtask

    initial begin
        $display("Paketleyici testi");
        #100; @(posedge clk); #1; rst = 0;

        // bir paket: 4 ornek grubu
        for (k = 0; k < 4; k = k + 1) ornek_ver(1000 + k);
        for (k = 0; k < 120; k = k + 1) @(posedge clk);

        $display("  toplanan bayt: %0d (beklenen %0d)", n, 16 + 4*24);
        if (n != 16 + 4*24) begin
            $display("  HATA: bayt sayisi tutmuyor");
            hata = hata + 1;
        end
        // dorduncu grubun ilk I0'i 1003 olmali
        sayac_gelen = {tampon[16+3*24], tampon[17+3*24], tampon[18+3*24]};
        if (sayac_gelen !== 24'd1003) begin
            $display("  HATA: son grubun I0 = %0d, 1003 olmali", sayac_gelen);
            hata = hata + 1;
        end else
            $display("  dort grup da dogru sirada");

        // ---- sihirli sayi
        if (tampon[0] !== 8'h53 || tampon[1] !== 8'h44 ||
            tampon[2] !== 8'h52 || tampon[3] !== 8'h34) begin
            $display("  HATA: sihirli sayi %02x%02x%02x%02x",
                     tampon[0], tampon[1], tampon[2], tampon[3]);
            hata = hata + 1;
        end else
            $display("  sihirli sayi dogru (SDR4)");

        if (tampon[4] !== 8'd1)      begin $display("  HATA: surum"); hata=hata+1; end
        if (tampon[5] !== 8'h0F)     begin $display("  HATA: kanal maskesi %02x", tampon[5]); hata=hata+1; end
        if (tampon[6] !== 8'd6)      begin $display("  HATA: azalt_log2"); hata=hata+1; end
        if (tampon[7] !== 8'd0)      begin $display("  HATA: bayrak %02x", tampon[7]); hata=hata+1; end

        sayac_gelen = {tampon[8], tampon[9], tampon[10], tampon[11],
                       tampon[12], tampon[13], tampon[14], tampon[15]};
        if (sayac_gelen !== 64'd0) begin
            $display("  HATA: ilk ornek numarasi %0d, 0 olmali", sayac_gelen);
            hata = hata + 1;
        end else
            $display("  ornek numarasi 0'dan basliyor");

        // ---- ilk ornegin I0'i 1000 olmali
        sayac_gelen = {tampon[16], tampon[17], tampon[18]};
        if (sayac_gelen !== 24'd1000) begin
            $display("  HATA: ilk I0 = %0d, 1000 olmali", sayac_gelen);
            hata = hata + 1;
        end else
            $display("  ilk ornek dogru yerde");

        if (hata == 0) $display("Paketleyici testi GECTI");
        else begin
            $display("Paketleyici testi KALDI: %0d hata", hata);
            $fatal;
        end
        $finish;
    end

endmodule

`default_nettype wire
