// AD9767 arayuzu — cift kanalli, 14 bit, paralel, CMOS.
//
// ADC'den farkli olarak DAC paralel ve saati BIZ veriyoruz. Iki port
// (P1, P2) ayri 14 bit veri yolu ve ayri WRT sinyali kullaniyor.
//
// WRT'NIN YUKSELEN KENARI ORNEGI YAKALIYOR. Veri o kenardan once
// kararli olmali (kurulum suresi) ve sonra bir sure daha durmali
// (tutma suresi). AD9767 veri sayfasi: kurulum 2.0 ns, tutma 1.5 ns.
// 80 MHz'te cevrim 12.5 ns, yani bol. Yine de veriyi ve WRT'yi AYNI
// kenarda degistirmiyoruz — veri bir cevrim once cikiyor, WRT
// sonraki cevrimde.
//
// NEDEN BU KADAR DIKKAT: kurulum ihlali sessiz. DAC yanlis degeri
// alir ve cikista genis bantli gurultu olarak gorunur; osiloskopta
// veri yolu temiz gorunur ve hatayi ancak spektrumda ararsin.
//
// IKI DAC, DORT KANAL: U30 (P1,P2) ve U31. Dordu ayni saatte, yani
// veriste de faz uyumu korunuyor.

`default_nettype none

module dac_cikis #(
    parameter BIT = 14
) (
    input  wire                   clk,
    input  wire                   rst,

    input  wire signed [BIT-1:0]  ornek_a,
    input  wire signed [BIT-1:0]  ornek_b,
    input  wire                   ornek_gecerli,

    output reg  [BIT-1:0]         dac_a,      // isaretsiz, ofset ikili
    output reg  [BIT-1:0]         dac_b,
    output reg                    wrt_a,
    output reg                    wrt_b,
    output reg                    dac_clk
);

    // ---------------------------------------------------------------
    // ISARETLIDEN OFSET IKILIYE.
    // DAC 0..16383 arasi isaretsiz bekliyor; bizim orneklerimiz
    // isaretli. En ust biti ters cevirmek ikisi arasinda gecisi
    // veriyor: -8192 -> 0, 0 -> 8192, +8191 -> 16383.
    //
    // Bunu unutmak, cikisi orta noktadan tam olcek kadar kaydirir ve
    // sinyal surekli kirpilir. Kolay hata, ve belirtisi "cikis cok
    // bozuk" — sebebi aramak zaman alir.
    // ---------------------------------------------------------------
    wire [BIT-1:0] ofset_a = {~ornek_a[BIT-1], ornek_a[BIT-2:0]};
    wire [BIT-1:0] ofset_b = {~ornek_b[BIT-1], ornek_b[BIT-2:0]};

    reg gecerli_g;

    always @(posedge clk) begin
        if (rst) begin
            dac_a     <= {BIT{1'b0}};
            dac_b     <= {BIT{1'b0}};
            wrt_a     <= 1'b0;
            wrt_b     <= 1'b0;
            gecerli_g <= 1'b0;
        end else begin
            // 1. cevrim: veriyi cikar
            if (ornek_gecerli) begin
                dac_a <= ofset_a;
                dac_b <= ofset_b;
            end
            gecerli_g <= ornek_gecerli;

            // 2. cevrim: WRT'yi kaldir — veri artik kararli
            wrt_a <= gecerli_g;
            wrt_b <= gecerli_g;
        end
    end

    // ---------------------------------------------------------------
    // DAC saati sistem saatinin yarisi.
    // AD9767'nin CLK girisi CMOS esikli ve 2.1 V lojik-1 istiyor;
    // FPGA'nin 3.3 V bankasi bunu karsiliyor. Bolme, kenar hizini
    // dusurmek icin degil — DAC'i ornekle ayni hizda surmek icin
    // WRT zaten yeterli, CLK ise ic mandallamayi suruyor.
    // ---------------------------------------------------------------
    always @(posedge clk) begin
        if (rst)
            dac_clk <= 1'b0;
        else
            dac_clk <= ~dac_clk;
    end

endmodule

`default_nettype wire
