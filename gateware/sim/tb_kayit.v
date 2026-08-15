// Kayit dosyasi testi.
//
// 1 YAZ-OKU. Yazilan deger geri okunmali. Tutmuyorsa adres
//   cozumlemesi yanlis ve ana bilgisayar hicbir ayari
//   dogrulayamaz.
//
// 2 DARBELER TEK CEVRIM. nco_yukle ve zincir_gonder yazma ile
//   birlikte bir cevrim yuksek kalip dusmeli. Yuksek kalirlarsa
//   NCO surekli sifirlanir ve alis hic calismaz.
//
// 3 DORT OFSET BIRLIKTE UYGULANIYOR. Ilk uc ofset yaziliyor ama
//   yukleme darbesi ancak dorduncude geliyor — huzme yonlendirmede
//   dort kanalin fazi ayni anda degismeli.
`timescale 1ns/1ps
`default_nettype none
module tb_kayit;
    reg clk=0, rst=1; always #6.25 clk=~clk;
    reg [7:0] adr=0, oku_adr=0; reg [31:0] veri=0; reg yaz=0;
    wire [31:0] oku;
    wire alis, veris, srst, nyuk, zgon, zyaz;
    wire [3:0] maske; wire [11:0] azalt, txoran;
    wire [31:0] artis, o0,o1,o2,o3, txart;
    wire [4:0] zuz, zadr; wire [7:0] zveri;

    kayit dut(.clk(clk),.rst(rst),.adr(adr),.veri(veri),.yaz(yaz),
        .oku_veri(oku),.oku_adr(oku_adr),
        .pll_kilit(1'b1),.adc_hizali(1'b1),.tasma(1'b0),
        .alis_ac(alis),.veris_ac(veris),.yazilim_rst(srst),
        .kanal_maske(maske),.azalt_orani(azalt),.nco_artis(artis),
        .nco_ofset0(o0),.nco_ofset1(o1),.nco_ofset2(o2),.nco_ofset3(o3),
        .nco_yukle(nyuk),.tx_artis(txart),.tx_oran(txoran),
        .zincir_uzun(zuz),.zincir_gonder(zgon),.zincir_veri(zveri),
        .zincir_adr(zadr),.zincir_yaz(zyaz));

    integer hata=0, k;
    reg gordu;

    task y(input [7:0] a, input [31:0] d);
        begin @(posedge clk); #1; adr=a; veri=d; yaz=1;
              @(posedge clk); #1; yaz=0; end
    endtask

    initial begin
        $display("Kayit dosyasi testi");
        #100; @(posedge clk); #1; rst=0;

        y(8'h03, 32'h12345678);
        oku_adr = 8'h03; @(posedge clk); @(posedge clk); #1;
        if (oku !== 32'h12345678) begin
            $display("  HATA: nco_artis geri okunmadi (%08x)", oku); hata=hata+1;
        end else $display("  yaz-oku dogru");

        // darbe: dorduncu ofset yazilinca nco_yukle bir cevrim
        gordu = 0;
        y(8'h04, 32'd100); y(8'h05, 32'd200); y(8'h06, 32'd300);
        if (nyuk) begin
            $display("  HATA: ilk uc ofsette yukleme darbesi geldi"); hata=hata+1;
        end
        @(posedge clk); #1; adr=8'h07; veri=32'd400; yaz=1;
        @(posedge clk); #1; yaz=0;
        if (!nyuk) begin
            $display("  HATA: dorduncu ofsette yukleme darbesi gelmedi"); hata=hata+1;
        end else $display("  dort ofset birlikte uygulaniyor");
        @(posedge clk); #1;
        if (nyuk) begin
            $display("  HATA: yukleme darbesi bir cevrimden uzun"); hata=hata+1;
        end else $display("  darbe tek cevrim");

        // zincir tamponu
        y(8'h12, 32'h000000AB);
        if (zadr !== 5'd2 || zveri !== 8'hAB) begin
            $display("  HATA: zincir tamponu adr=%0d veri=%02x", zadr, zveri);
            hata=hata+1;
        end else $display("  zincir tamponu dogru adreste");

        if (hata==0) $display("Kayit dosyasi testi GECTI");
        else begin $display("Kayit dosyasi testi KALDI: %0d hata", hata); $fatal; end
        $finish;
    end
endmodule
`default_nettype wire
