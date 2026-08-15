// MDIO ana birimi — PHY yonetim arayuzu (IEEE 802.3 madde 22).
//
// NEDEN VAR. RTL8211F strap dirençleriyle acilip kendi kendine
// otomatik anlasma yapiyor, yani teoride MDIO'suz da link kalkar.
// Ama kalkmazsa NEDENINI OGRENMENIN BASKA YOLU YOK: hiz mi
// anlasilamadi, kablo mi kopuk, PHY mi resette, RGMII gecikmesi mi
// yanlis — hepsi disaridan ayni gorunuyor, "veri gelmiyor".
//
// Bir de: RGMII'nin ic gecikmesi (RXD0/RXD1 strap'leri) ve LED
// davranisi kayitlardan degistirilebiliyor. Strap'i lehimle
// degistirmek yerine okuyup dogrulamak, kart geldiginde saatler
// kazandiriyor.
//
// CERCEVE (madde 22):
//   32 bit onsoz (hepsi 1)
//    2 bit ST   = 01
//    2 bit OP   = 10 okuma, 01 yazma
//    5 bit PHY adresi
//    5 bit kayit adresi
//    2 bit TA   = yazmada 10, okumada ana birim hatti BIRAKIR
//   16 bit veri
//
// MDC HIZI. Standart 2.5 MHz ust sinir; 80 MHz'i 32'ye boluyoruz.
// Daha hizli surmek cogu PHY'de calisir ama kart uzerindeki uzun
// hat ve pull-up ile kenar yavaslar; burada hiz kazanmanin degeri
// yok, yilda birkac kez okunan bir arayuz.
//
// MDIO CIFT YONLU. Okumada TA evresinde hatti BIRAKIYORUZ ve PHY
// devraliyor. Birakmayi gec yaparsak iki surucu carpisir; erken
// yaparsak PHY'nin ilk bitini kaciririz. Kenar sayisi ile
// yapiliyor, karsi tarafin ne yaptigini tahmin ederek degil.

`default_nettype none

module mdio #(
    parameter BOLEN = 32          // clk / (2*MDC); 80 MHz -> 1.25 MHz
) (
    input  wire        clk,
    input  wire        rst,

    input  wire [4:0]  phy_adr,
    input  wire [4:0]  kayit_adr,
    input  wire [15:0] yaz_veri,
    input  wire        yaz,        // 1 = yazma, 0 = okuma
    input  wire        basla,      // tek cevrimlik darbe
    output reg  [15:0] oku_veri,
    output wire        mesgul,

    output reg         mdc,
    output wire        mdio_o,
    output reg         mdio_yon,   // 1 = ana birim suruyor
    input  wire        mdio_i
);

    localparam D_BOS   = 2'd0;
    localparam D_BIT   = 2'd1;
    localparam D_SONRA = 2'd2;

    reg [1:0]  durum;
    reg [6:0]  kalan;        // kac kenar cifti kaldi (64'e kadar)
    reg [63:0] kaydir;
    reg        yarim;
    reg [15:0] say;
    reg        okuma;

    assign mesgul = (durum != D_BOS);
    assign mdio_o = kaydir[63];

    wire tik = (say == BOLEN - 1);

    // Toplam 64 bit: 32 onsoz + 2 ST + 2 OP + 5 PHY + 5 REG + 2 TA + 16 veri
    localparam [6:0] TOPLAM = 7'd64;
    // Veri evresinin basladigi kalan degeri
    localparam [6:0] VERI_BAS = 7'd16;
    // TA evresi: veriden hemen once iki bit
    localparam [6:0] TA_BAS   = 7'd18;

    always @(posedge clk) begin
        if (rst) begin
            durum    <= D_BOS;
            mdc      <= 1'b0;
            mdio_yon <= 1'b0;
            say      <= 16'd0;
            yarim    <= 1'b0;
        end else begin
            case (durum)
            D_BOS: begin
                mdc      <= 1'b0;
                mdio_yon <= 1'b0;
                if (basla) begin
                    kaydir <= {32'hFFFF_FFFF,      // onsoz
                               2'b01,              // ST
                               yaz ? 2'b01 : 2'b10,
                               phy_adr, kayit_adr,
                               2'b10,              // TA (yazmada)
                               yaz_veri};
                    kalan    <= TOPLAM;
                    okuma    <= ~yaz;
                    oku_veri <= 16'd0;
                    mdio_yon <= 1'b1;
                    say      <= 16'd0;
                    yarim    <= 1'b0;
                    durum    <= D_BIT;
                end
            end

            D_BIT: if (tik) begin
                say <= 16'd0;
                if (!yarim) begin
                    // MDC yukselen kenari: karsi taraf ornekliyor,
                    // okumada biz de burada orneklyoruz.
                    mdc   <= 1'b1;
                    yarim <= 1'b1;
                    if (okuma && kalan <= VERI_BAS)
                        oku_veri <= {oku_veri[14:0], mdio_i};
                end else begin
                    mdc    <= 1'b0;
                    yarim  <= 1'b0;
                    kaydir <= {kaydir[62:0], 1'b0};
                    kalan  <= kalan - 1'b1;
                    // OKUMADA TA'DAN ONCE HATTI BIRAK.
                    // TA'nin ilk biti PHY'ye ait; ana birim orada
                    // yuksek empedansa gecmis olmali.
                    if (okuma && kalan == TA_BAS + 1)
                        mdio_yon <= 1'b0;
                    if (kalan == 7'd1) durum <= D_SONRA;
                end
            end else say <= say + 1'b1;

            D_SONRA: if (tik) begin
                say      <= 16'd0;
                mdio_yon <= 1'b0;
                durum    <= D_BOS;
            end else say <= say + 1'b1;

            default: durum <= D_BOS;
            endcase
        end
    end

endmodule

`default_nettype wire
