// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// RGMII alis — PHY'den gelen cerceveyi bayta cevirir.
//
// rgmii_veris.v'nin aynasi. Orada bayti iki nibble'a bolup ODDR ile
// veriyorduk; burada iki nibble'i IDDR ile toplayip bayta ceviriyoruz.
//
// SAAT PHY'DEN GELIYOR. Veriste saati biz uretiyorduk (clk_eth,
// PLL'den). Aliste RXC'yi PHY veriyor ve bizim clk_eth'imizle
// ARASINDA HICBIR FAZ ILISKISI YOK — ayni nominal 125 MHz olsalar
// bile ayri kaynaklar. O yuzden bu modul tamamen RXC alaninda
// calisiyor ve cikisi ust.v'de FIFO ile clk_sys'e geciyor.
// Aradaki gecisi FIFO yerine tek bir senkronizatorle yapmak,
// 125 MHz'lik bir bayt akisini 80 MHz'e sokmak demekti — tasar.
//
// RGMII'DE RX_CTL IKI IS YAPIYOR:
//   yukselen kenar -> RXDV  (veri gecerli)
//   dusen  kenar -> RXERR xor RXDV
// Yani ikisi ayni telde, kenara gore ayriliyor. Hata bitini
// atlamak, bozuk gelen bir cerceveyi saglammis gibi yukari vermek
// demek; CRC cogunu yakalar ama PHY zaten "bu bozuk" diyorsa onu
// dinlemek bedava.
//
// GECIKME NEDEN DERT DEGIL: bu yol kontrol icin, veri icin degil.
// Ornekler yukari RGMII VERIS'ten gidiyor; buradan sadece kayit
// yazmalari geliyor (host -> FPGA). Birkac cevrimlik gecikmenin
// olculebilir bir etkisi yok.

`default_nettype none

module rgmii_alis (
    input  wire       clk,          // RXC, PHY'den 125 MHz
    input  wire       rst,

    // IDDR'dan gelen nibble'lar (ust.v cozuyor)
    input  wire [3:0] rd_yuk,       // saatin yuksek yarisinda ornek
    input  wire [3:0] rd_dus,       // alcak yarisinda
    input  wire       rctl_yuk,     // = RXDV
    input  wire       rctl_dus,     // = RXERR xor RXDV

    output reg  [7:0] bayt,
    output reg        bayt_gecerli,
    output reg        cerceve_sonu, // son bayttan sonra bir cevrim
    output reg        crc_dogru,    // cerceve_sonu ile birlikte gecerli
    output reg        hata          // PHY hata bildirdi ya da CRC tuttu
);

    // -----------------------------------------------------------------
    // Nibble sirasi: RGMII'de ONCE ALT nibble geliyor.
    // Ters cevirince her bayt yer degistirir ve hicbir sey tutmaz;
    // CRC de tutmaz, yani belirtisi "her cerceve bozuk" olur.
    // -----------------------------------------------------------------
    wire [7:0] ham_bayt = {rd_dus, rd_yuk};
    wire       dv       = rctl_yuk;
    wire       err      = rctl_dus ^ rctl_yuk;

    // -----------------------------------------------------------------
    // Durum: onsoz bekle -> veri topla
    //
    // ONSOZU SAYMIYORUZ, SFD ARIYORUZ. "7 bayt 0x55 sonra 0xD5" diye
    // saymak, onsozun kisaldigi (anahtar gecikmesi yiyor) gercek
    // aglarda cerceve kaybettiriyor. IEEE 802.3 de alicinin SFD'ye
    // bakmasini soyluyor, onsoz uzunluguna degil.
    // -----------------------------------------------------------------
    localparam D_BOS  = 2'd0;
    localparam D_VERI = 2'd1;

    reg [1:0] durum;
    reg       hata_gordu;

    // -----------------------------------------------------------------
    // CRC32 — rgmii_veris.v ile AYNI fonksiyon.
    //
    // Alista CRC'yi cerceveyi cikarmak icin degil, DOGRULAMAK icin
    // hesapliyoruz: FCS dahil butun cerceve gecirilirse sonuc her
    // zaman ayni sabiti verir (magic number 0xC704DD7B). Boylece
    // FCS'i ayirip karsilastirmak gerekmiyor — kac bayt geldigini
    // saymadan calisiyor, ki cerceve uzunlugu degisken.
    // -----------------------------------------------------------------
    // SABIT HESAPLANDI, EZBERDEN YAZILMADI. Literaturde bu sayi icin
    // iki deger dolasiyor (0xC704DD7B ve 0xDEBB20E3); hangisinin
    // dogru oldugu CRC'nin yansitilmis mi duz mu oldugu ile ilgili.
    // Bizim fonksiyonumuz yansitilmis (poly 0xEDB88320, LSB'den
    // kaydiriyor) ve onun kalani 0xDEBB20E3. Otekini yazsaydim her
    // saglam cerceve "CRC tutmadi" diye atilirdi.
    localparam [31:0] CRC_SIHIR = 32'hDEBB20E3;

    reg [31:0] crc;

    // CRC BAYT ADIMI DUZLESTIRILDI — kritik yol buydu.
    //
    // Fonksiyon burada bit-seri dongu olarak yaziliydi: sekiz adim
    // birbirine zincirli ve yosys onu birebir sentezliyor. nextpnr
    // olcumu clk_eth'in kritik yolunun tam burasi oldugunu gosterdi
    // ve azami frekans tohuma gore 112-138 MHz arasinda geziniyordu —
    // hedef 125. Yani yapinin gecmesi tohum sansina kalmisti; alti
    // tohum ust uste denendi, alti da dustu.
    //
    // Fonksiyon DOGRUSAL (kosullu gorunse de secim islemi XOR'un
    // kendisi), o yuzden dengeli bir XOR agacina duzlestirilebiliyor.
    // Denklemler elle yazilmadi: rtl/crc32_uret.py referans algoritmayi
    // taban vektorleriyle kosturup dogrusal donusumu cikariyor.
    //
    // Esdegerlik sim/tb_crc32.v ile kanitlaniyor — taban vektorleri
    // (dogrusal bir fonksiyon icin bu TAM ispattir), 102400 rastgele
    // karsilastirma ve gercek bir cerceve uzerinde FCS.
`include "crc32_bayt.vh"

    // gecen cevrimin dv'si: cerceve sonunu dv'nin DUSMESINDEN
    // anliyoruz, ayri bir sayacla degil
    reg dv_g;

    always @(posedge clk) begin
        if (rst) begin
            durum        <= D_BOS;
            bayt         <= 8'd0;
            bayt_gecerli <= 1'b0;
            cerceve_sonu <= 1'b0;
            crc_dogru    <= 1'b0;
            hata         <= 1'b0;
            crc          <= 32'hFFFFFFFF;
            hata_gordu   <= 1'b0;
            dv_g         <= 1'b0;
        end else begin
            bayt_gecerli <= 1'b0;
            cerceve_sonu <= 1'b0;
            dv_g         <= dv;

            case (durum)
            D_BOS: begin
                crc        <= 32'hFFFFFFFF;
                hata_gordu <= 1'b0;
                // SFD: onsozun son bayti
                if (dv && ham_bayt == 8'hD5)
                    durum <= D_VERI;
            end

            D_VERI: begin
                if (dv) begin
                    bayt         <= ham_bayt;
                    bayt_gecerli <= 1'b1;
                    crc          <= crc_bayt(crc, ham_bayt);
                    if (err) hata_gordu <= 1'b1;
                end else begin
                    // dv dustu: cerceve bitti
                    durum        <= D_BOS;
                    cerceve_sonu <= 1'b1;
                    // CRC FCS DAHIL GECIRILDI, sabiti vermeli.
                    crc_dogru    <= (crc == CRC_SIHIR) && !hata_gordu;
                    hata         <= (crc != CRC_SIHIR) || hata_gordu;
                end
            end

            default: durum <= D_BOS;
            endcase
        end
    end

endmodule

`default_nettype wire
