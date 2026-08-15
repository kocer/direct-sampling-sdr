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
//   0x0B  zincir_gonder  yazinca zinciri sur
//   0x10..0x1F  zincir tamponu (bayt basina bir kayit)
//   0x20  durum        SADECE OKUMA: kilit, tasma, saat
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
    output reg  [4:0]  zincir_uzun,
    output reg         zincir_gonder,
    output reg  [7:0]  zincir_veri,
    output reg  [4:0]  zincir_adr,
    output reg         zincir_yaz
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
    localparam A_DURUM   = 8'h20;

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
            zincir_uzun   <= 5'd8;
            zincir_gonder <= 1'b0;
            zincir_yaz    <= 1'b0;
            tasma_kilit   <= 1'b0;
        end else begin
            // TEK CEVRIMLIK DARBELER. Bunlar yazma ile birlikte
            // bir cevrim yuksek kaliyor ve kendiliginden dusuyor.
            // Ana bilgisayarin geri yazmasi gerekseydi, arada
            // baglanti koparsa sistem o durumda kilitlenirdi.
            nco_yukle     <= 1'b0;
            zincir_gonder <= 1'b0;
            zincir_yaz    <= 1'b0;
            yazilim_rst   <= 1'b0;

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
                A_ZIN_UZ:  zincir_uzun <= veri[4:0];
                A_ZIN_GON: zincir_gonder <= 1'b1;
                default: begin
                    if (adr >= 8'h10 && adr <= 8'h1F) begin
                        zincir_adr  <= adr[4:0] - 5'd16;
                        zincir_veri <= veri[7:0];
                        zincir_yaz  <= 1'b1;
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
        A_ZIN_UZ:  oku_veri <= {27'd0, zincir_uzun};
        A_DURUM:   oku_veri <= {29'd0, tasma_kilit, adc_hizali, pll_kilit};
        default:   oku_veri <= 32'd0;
        endcase
    end

endmodule

`default_nettype wire
