// Kayit dosyasi — gateware'in butun ayarlari tek yerden.
//
// Ana bilgisayar UDP ile yaziyor, gateware buradan okuyor. Basit bir
// adres/veri arayuzu; SPI ya da JTAG degil, cunku zaten ethernet var
// ve ayri bir hata ayiklama yolu tutmak iki kat bakim demek.
//
// ADRES HARITASI (32 bit kayitlar):
//
//   0x00  kontrol      bit0 alis ac, bit1 veris ac, bit2 sifirla
//   0x01  kanal_maske  hangi alis kanallari aktif
//   0x02  azalt_orani  CIC R degeri
//   0x03  nco_artis    dort kanal ortak taban frekans
//   0x04  nco_ofset0   kanal 0 faz ofseti
//   0x05  nco_ofset1
//   0x06  nco_ofset2
//   0x07  nco_ofset3
//   0x08  tx_artis     veris tasiyici frekansi
//   0x09  tx_oran      veris artirma orani
//   0x0A  zincir_uzun  kac 595 var
//   0x0B  zincir_gonder  YAZINCA zinciri sur.
//                      bit1     darbe kipi (kilitlenen role dizisi)
//                      bit15:8  darbe suresi, ms
//   0x0C  adc_desen    bit13:0 kanal A deseni, bit29:16 kanal B,
//                      bit31 denetimi ac
//   0x0D  spi_veri     yollanacak bitler (MSB once, uzunluga hizali)
//   0x0E  spi_komut    YAZINCA BASLAR: bit31 yol (0=ADC, 1=cevre),
//                      bit26:24 cihaz, bit13:8 okuma biti, bit5:0 uzunluk
//   0x0F  yardimci     bit0 adc_sync, bit1 phy reset zorla,
//                      bit2 PA bekci kopegini besle
//   0x10..0x1F  zincir tamponu (bayt basina bir kayit)
//               bit8 = 1 ise TUTMA MASKESINE yazar, 0 ise veriye.
//               Maskede 1 olan bitler darbe sonrasi da surulu kalir
//               (T/R roleleri gibi kilitlenmeyenler icin).
//   0x20  durum        SADECE OKUMA: kilit, tasma, saat, ADC takas, SPI mesgul
//   0x21  spi_okunan   SADECE OKUMA
//   0x22  mdio_komut   YAZINCA BASLAR: bit31 yazma/okuma,
//                      bit28:24 PHY adresi, bit20:16 kayit adresi,
//                      bit15:0 yazilacak veri
//   0x23  mdio_okunan  SADECE OKUMA
//   0x24  tx_ofset1    veris kanal 1 faz ofseti
//   0x25  tx_ofset2    veris kanal 2 faz ofseti
//   0x26  tx_ofset3    veris kanal 3 faz ofseti — YAZINCA UCU DE UYGULANIR
//   0x27  tx_yardim    bit0 iqsel_ters (U31'de kanal 3/4 sirasi)
//
// FAZ OFSETI NEDEN AYRI KAYITTA: huzme yonlendirme kanallar arasi
// fazi degistirerek yapiliyor. Tek bir kayit olsaydi dort kanali
// ayni anda kaydiramazdik ve gecis sirasinda huzme saga sola
// atlardi.
//
// SIFIRLAMA BITI KENDINI TEMIZLIYOR: yazip birakmak yetiyor. Ana
// bilgisayarin ikinci bir yazma yapmasi gerekseydi, arada baglanti
// koparsa gateware sonsuza kadar sifirda kalirdi.

`default_nettype none

module kayit (
    input  wire        clk,
    input  wire        rst,

    // yazma arayuzu (ethernet'ten)
    input  wire [7:0]  adr,
    input  wire [31:0] veri,
    input  wire        yaz,

    // okuma
    output reg  [31:0] oku_veri,
    input  wire [7:0]  oku_adr,

    // durum girisleri
    input  wire        pll_kilit,
    input  wire        adc_hizali,
    input  wire        tasma,

    // ayarlar
    output reg         alis_ac,
    output reg         veris_ac,
    output reg         yazilim_rst,
    output reg  [3:0]  kanal_maske,
    output reg  [11:0] azalt_orani,
    output reg  [31:0] nco_artis,
    output reg  [31:0] nco_ofset0,
    output reg  [31:0] nco_ofset1,
    output reg  [31:0] nco_ofset2,
    output reg  [31:0] nco_ofset3,
    output reg         nco_yukle,
    output reg  [31:0] tx_artis,
    output reg  [11:0] tx_oran,
    // VERIS FAZ OFSETLERI — ALIS TARAFINDAN AYRI.
    // Ilk hali alis ofsetlerini (nco_ofset*) veris NCO'suna da
    // veriyordu. Yanlis: alis ve veris huzmeleri ayni yone bakmak
    // ZORUNDA degil (ornegin ayri anten dizisine calisirken), ve
    // dinlerken huzmeyi cevirmek vericinin fazini da kaydirirdi.
    output reg  [31:0] tx_ofset1,
    output reg  [31:0] tx_ofset2,
    output reg  [31:0] tx_ofset3,
    output reg         tx_yukle,
    output reg         tx_iqsel_ters,
    output reg  [4:0]  zincir_uzun,
    output reg         zincir_gonder,
    output reg  [7:0]  zincir_veri,
    output reg  [4:0]  zincir_adr,
    output reg         zincir_yaz,
    output reg         zincir_darbe_kip,
    output reg  [7:0]  zincir_darbe_ms,
    output reg         zincir_maske_bank,

    // ADC test deseni
    output reg  [13:0] adc_desen_a,
    output reg  [13:0] adc_desen_b,
    output reg         adc_desen_dene,
    input  wire [1:0]  adc_takas,

    // SPI
    output reg  [31:0] spi_veri,
    output reg  [5:0]  spi_uzunluk,
    output reg  [5:0]  spi_oku_bit,
    output reg  [2:0]  spi_cihaz,
    output reg         spi_yol,        // 0 = ADC yolu, 1 = cevre yolu
    output reg         spi_basla,
    input  wire [31:0] spi_okunan,
    input  wire        spi_mesgul,

    // yardimci cikislar
    output reg         adc_sync,
    output reg         phy_rst_zorla,
    output reg         pa_besle,      // tek cevrimlik, bekci kopegi

    // MDIO
    output reg  [4:0]  mdio_phy,
    output reg  [4:0]  mdio_kayit,
    output reg  [15:0] mdio_veri,
    output reg         mdio_yaz,
    output reg         mdio_basla,
    input  wire [15:0] mdio_okunan,
    input  wire        mdio_mesgul
);

    localparam A_KONTROL = 8'h00;
    localparam A_MASKE   = 8'h01;
    localparam A_AZALT   = 8'h02;
    localparam A_ARTIS   = 8'h03;
    localparam A_OFS0    = 8'h04;
    localparam A_OFS1    = 8'h05;
    localparam A_OFS2    = 8'h06;
    localparam A_OFS3    = 8'h07;
    localparam A_TX_ART  = 8'h08;
    localparam A_TX_ORAN = 8'h09;
    localparam A_ZIN_UZ  = 8'h0A;
    localparam A_ZIN_GON = 8'h0B;
    // ADC TEST DESENI TEK KAYITTA. Iki desen ve denetim biti ayri
    // adreslerde olsaydi, arada bir cevrim desen A yeni desen B eski
    // olurdu ve modul o cevrimde eslesmeyi kaybederdi — sayac sifira
    // doner, hizalama hic tamamlanmaz.
    localparam A_DESEN   = 8'h0C;
    localparam A_SPI_VER = 8'h0D;
    localparam A_SPI_KOM = 8'h0E;
    localparam A_YARDIM  = 8'h0F;
    localparam A_SPI_OKU = 8'h21;
    localparam A_MDIO    = 8'h22;
    localparam A_MDIO_OK = 8'h23;
    localparam A_DURUM   = 8'h20;
    localparam A_TX_OFS1 = 8'h24;
    localparam A_TX_OFS2 = 8'h25;
    localparam A_TX_OFS3 = 8'h26;
    localparam A_TX_YAR  = 8'h27;

    // tasma kilidi: bir kez olunca okunana kadar duruyor
    reg tasma_kilit;

    always @(posedge clk) begin
        if (rst) begin
            alis_ac       <= 1'b0;
            veris_ac      <= 1'b0;
            yazilim_rst   <= 1'b0;
            kanal_maske   <= 4'b1111;
            azalt_orani   <= 12'd64;
            nco_artis     <= 32'd0;
            nco_ofset0    <= 32'd0;
            nco_ofset1    <= 32'd0;
            nco_ofset2    <= 32'd0;
            nco_ofset3    <= 32'd0;
            nco_yukle     <= 1'b0;
            tx_artis      <= 32'd0;
            tx_oran       <= 12'd64;
            tx_ofset1     <= 32'd0;
            tx_ofset2     <= 32'd0;
            tx_ofset3     <= 32'd0;
            tx_yukle      <= 1'b0;
            tx_iqsel_ters <= 1'b0;
            zincir_uzun   <= 5'd8;
            zincir_gonder <= 1'b0;
            zincir_yaz    <= 1'b0;
            // VARSAYILAN DARBE KIPI ACIK, 30 ms.
            // Guvenli taraf bu: darbe kipi kapali unutulursa bobin
            // yanar, acik unutulursa sadece tutulmasi gereken bir
            // role birakilir ve o hemen fark edilir.
            zincir_darbe_kip  <= 1'b1;
            zincir_darbe_ms   <= 8'd30;
            zincir_maske_bank <= 1'b0;
            tasma_kilit   <= 1'b0;
            adc_desen_a    <= 14'h1555;
            adc_desen_b    <= 14'h2AAA;
            adc_desen_dene <= 1'b0;
            spi_veri      <= 32'd0;
            spi_uzunluk   <= 6'd0;
            spi_oku_bit   <= 6'd0;
            spi_cihaz     <= 3'd0;
            spi_yol       <= 1'b0;
            spi_basla     <= 1'b0;
            pa_besle      <= 1'b0;
            mdio_basla    <= 1'b0;
            adc_sync      <= 1'b0;
            phy_rst_zorla <= 1'b0;
            pa_besle      <= 1'b0;
        end else begin
            // TEK CEVRIMLIK DARBELER. Bunlar yazma ile birlikte
            // bir cevrim yuksek kaliyor ve kendiliginden dusuyor.
            // Ana bilgisayarin geri yazmasi gerekseydi, arada
            // baglanti koparsa sistem o durumda kilitlenirdi.
            nco_yukle     <= 1'b0;
            tx_yukle      <= 1'b0;
            zincir_gonder <= 1'b0;
            zincir_yaz    <= 1'b0;
            yazilim_rst   <= 1'b0;
            spi_basla     <= 1'b0;

            if (tasma)
                tasma_kilit <= 1'b1;

            if (yaz) begin
                case (adr)
                A_KONTROL: begin
                    alis_ac     <= veri[0];
                    veris_ac    <= veri[1];
                    yazilim_rst <= veri[2];
                end
                A_MASKE:   kanal_maske <= veri[3:0];
                A_AZALT:   azalt_orani <= veri[11:0];
                A_ARTIS:   nco_artis   <= veri;
                // DORT OFSET AYRI YAZILIYOR AMA BIRLIKTE YUKLENIYOR.
                // Huzme yonlendirmede dort kanalin fazi ayni anda
                // degismeli; tek tek yuklenirse gecis sirasinda
                // huzme saga sola atliyor.
                A_OFS0:    nco_ofset0  <= veri;
                A_OFS1:    nco_ofset1  <= veri;
                A_OFS2:    nco_ofset2  <= veri;
                A_OFS3:    begin
                    nco_ofset3 <= veri;
                    nco_yukle  <= 1'b1;      // dorduncu yazinca uygula
                end
                A_TX_ART:  tx_artis    <= veri;
                A_TX_ORAN: tx_oran     <= veri[11:0];
                // UC OFSET AYRI YAZILIYOR, UCUNCUDE BIRLIKTE UYGULANIYOR
                // — alis tarafiyla ayni gerekce. Kanal 0 referans
                // oldugu icin onun ofseti yok.
                A_TX_OFS1: tx_ofset1 <= veri;
                A_TX_OFS2: tx_ofset2 <= veri;
                A_TX_OFS3: begin
                    tx_ofset3 <= veri;
                    tx_yukle  <= 1'b1;
                end
                A_TX_YAR:  tx_iqsel_ters <= veri[0];
                A_ZIN_UZ:  zincir_uzun <= veri[4:0];
                A_ZIN_GON: begin
                    zincir_gonder    <= 1'b1;
                    zincir_darbe_kip <= veri[1];
                    if (veri[15:8] != 8'd0) zincir_darbe_ms <= veri[15:8];
                end
                // SPI KOMUTU YAZILINCA BASLIYOR, AYRI BIR "BASLA"
                // BITI YOK. Ayri bit olsaydi host once komutu sonra
                // basla'yi yazacakti; arada baglanti koparsa yarim
                // yapilandirilmis bir cihaz kalirdi.
                A_SPI_VER: spi_veri <= veri;
                A_SPI_KOM: if (!spi_mesgul) begin
                    spi_uzunluk <= veri[5:0];
                    spi_oku_bit <= veri[13:8];
                    spi_cihaz   <= veri[26:24];
                    spi_yol     <= veri[31];
                    spi_basla   <= 1'b1;
                end
                A_MDIO: if (!mdio_mesgul) begin
                    mdio_veri  <= veri[15:0];
                    mdio_kayit <= veri[20:16];
                    mdio_phy   <= veri[28:24];
                    mdio_yaz   <= veri[31];
                    mdio_basla <= 1'b1;
                end
                A_YARDIM: begin
                    adc_sync      <= veri[0];
                    phy_rst_zorla <= veri[1];
                    pa_besle      <= veri[2];
                end
                A_DESEN: begin
                    adc_desen_a    <= veri[13:0];
                    adc_desen_b    <= veri[29:16];
                    adc_desen_dene <= veri[31];
                end
                default: begin
                    if (adr >= 8'h10 && adr <= 8'h1F) begin
                        zincir_adr        <= adr[4:0] - 5'd16;
                        zincir_veri       <= veri[7:0];
                        zincir_maske_bank <= veri[8];
                        zincir_yaz        <= 1'b1;
                    end
                end
                endcase
            end

            // durum okununca tasma kilidi temizlensin
            if (oku_adr == A_DURUM)
                tasma_kilit <= tasma;
        end
    end

    always @(posedge clk) begin
        case (oku_adr)
        A_KONTROL: oku_veri <= {29'd0, yazilim_rst, veris_ac, alis_ac};
        A_MASKE:   oku_veri <= {28'd0, kanal_maske};
        A_AZALT:   oku_veri <= {20'd0, azalt_orani};
        A_ARTIS:   oku_veri <= nco_artis;
        A_OFS0:    oku_veri <= nco_ofset0;
        A_OFS1:    oku_veri <= nco_ofset1;
        A_OFS2:    oku_veri <= nco_ofset2;
        A_OFS3:    oku_veri <= nco_ofset3;
        A_TX_ART:  oku_veri <= tx_artis;
        A_TX_ORAN: oku_veri <= {20'd0, tx_oran};
        A_TX_OFS1: oku_veri <= tx_ofset1;
        A_TX_OFS2: oku_veri <= tx_ofset2;
        A_TX_OFS3: oku_veri <= tx_ofset3;
        A_TX_YAR:  oku_veri <= {31'd0, tx_iqsel_ters};
        A_ZIN_UZ:  oku_veri <= {27'd0, zincir_uzun};
        A_DESEN:   oku_veri <= {adc_desen_dene, 1'b0, adc_desen_b,
                                2'd0, adc_desen_a};
        A_SPI_OKU: oku_veri <= spi_okunan;
        A_MDIO_OK: oku_veri <= {15'd0, mdio_mesgul, mdio_okunan};
        A_DURUM:   oku_veri <= {24'd0, spi_mesgul, adc_takas,
                                2'd0, tasma_kilit, adc_hizali, pll_kilit};
        default:   oku_veri <= 32'd0;
        endcase
    end

endmodule

`default_nettype wire
