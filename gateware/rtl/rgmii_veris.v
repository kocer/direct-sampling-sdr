// RGMII veris — bayt akisindan ethernet cercevesine.
//
// RTL8211F ile 1000BASE-T. RGMII 4 bit veri yolu ve DDR kullaniyor:
// saatin yukselen kenarinda alt nibble, dusen kenarinda ust nibble.
// 125 MHz x 4 bit x 2 kenar = 1 Gbit/s.
//
// CERCEVE YAPISI:
//   7 bayt   0x55  onsoz
//   1 bayt   0xD5  cerceve baslangici
//   14 bayt  ethernet basligi (hedef MAC, kaynak MAC, tur)
//   20 bayt  IPv4 basligi
//   8 bayt   UDP basligi
//   N bayt   veri
//   4 bayt   FCS (CRC-32)
//   12 bayt  cerceveler arasi bosluk
//
// CRC-32 NEDEN BURADA: PHY hesaplamiyor, MAC hesapliyor. Yanlis CRC
// ile gonderilen cerceveyi karsi taraf sessizce atar — kartta hicbir
// hata gorunmez, ana bilgisayarda veri gelmez, ve sebebi aramak
// gunler alir.
//
// IP VE UDP SAGLAMA TOPLAMI: IP basliginin saglamasi ZORUNLU.
// UDP'ninki IPv4'te istege bagli ve sifir birakilabilir; boylece
// veri uzunlugu degistikce yeniden hesaplamak gerekmiyor. Sifir
// birakmak "saglama yok" demek ve alici kabul ediyor.

`default_nettype none

module rgmii_veris #(
    parameter [47:0] KAYNAK_MAC = 48'h02_00_00_00_00_01,
    parameter [47:0] HEDEF_MAC  = 48'hFF_FF_FF_FF_FF_FF,
    parameter [31:0] KAYNAK_IP  = {8'd192, 8'd168, 8'd10, 8'd10},
    parameter [31:0] HEDEF_IP   = {8'd192, 8'd168, 8'd10, 8'd1},
    parameter [15:0] KAYNAK_PORT= 16'd50000,
    parameter [15:0] HEDEF_PORT = 16'd50000
) (
    input  wire        clk,          // 125 MHz
    input  wire        rst,

    // veri girisi
    input  wire [7:0]  veri,
    input  wire        veri_gecerli,
    input  wire        veri_son,
    output wire        veri_hazir,
    input  wire [15:0] yuk_uzunluk,  // veri bayt sayisi

    // RGMII
    output reg  [3:0]  rgmii_td,
    output reg         rgmii_tctl,
    output wire        rgmii_tclk
);

    assign rgmii_tclk = clk;

    localparam D_BOS    = 4'd0;
    localparam D_ONSOZ  = 4'd1;
    localparam D_ETH    = 4'd2;
    localparam D_IP     = 4'd3;
    localparam D_UDP    = 4'd4;
    localparam D_VERI   = 4'd5;
    localparam D_FCS    = 4'd6;
    localparam D_BOSLUK = 4'd7;

    reg [3:0]  durum;
    reg [5:0]  sayac;
    reg [15:0] veri_sayaci;
    reg [7:0]  cikis_bayt;
    reg        cikis_gecerli;
    reg        nibble;        // 0 = alt, 1 = ust

    wire [15:0] ip_uzunluk  = 16'd28 + yuk_uzunluk;   // IP + UDP + veri
    wire [15:0] udp_uzunluk = 16'd8  + yuk_uzunluk;

    // ---------------------------------------------------------------
    // IP baslik saglama toplami.
    //
    // Onceden hesaplaniyor: baslik alanlari sabit ya da uzunluga
    // bagli, yani cerceve basinda bir kez cikarilabiliyor. Akis
    // sirasinda hesaplamaya calismak baslik yazilirken sonucu
    // gerektirirdi — tavuk yumurta.
    // ---------------------------------------------------------------
    function [15:0] saglama;
        input [15:0] uzunluk;
        reg [31:0] t;
        begin
            t = 32'h4500 + uzunluk + 32'h0000 + 32'h4000 +
                32'h4011 +
                KAYNAK_IP[31:16] + KAYNAK_IP[15:0] +
                HEDEF_IP[31:16]  + HEDEF_IP[15:0];
            t = (t & 32'hFFFF) + (t >> 16);
            t = (t & 32'hFFFF) + (t >> 16);
            saglama = ~t[15:0];
        end
    endfunction

    wire [15:0] ip_saglama = saglama(ip_uzunluk);

    // ---------------------------------------------------------------
    // CRC-32, ethernet cok terimlisi 0x04C11DB7, ters bit sirasi.
    // Bayt bayt guncelleniyor.
    // ---------------------------------------------------------------
    reg [31:0] crc;

    function [31:0] crc_bayt;
        input [31:0] c;
        input [7:0]  d;
        integer i;
        reg [31:0] t;
        begin
            t = c ^ {24'd0, d};
            for (i = 0; i < 8; i = i + 1)
                t = t[0] ? ((t >> 1) ^ 32'hEDB88320) : (t >> 1);
            crc_bayt = t;
        end
    endfunction

    wire [31:0] fcs = ~crc;

    assign veri_hazir = (durum == D_VERI) && nibble;

    // ---------------------------------------------------------------
    // SONRAKI BAYT TEK YERDE HESAPLANIYOR.
    //
    // Once her durumda "cikis_bayt <= X; crc <= crc_bayt(crc,
    // cikis_bayt)" yaziyordum. Bloklamayan atama yuzunden CRC,
    // cikis_bayt'in ESKI degerini kullaniyordu: ilk ETH baytinda
    // onsozun 0xD5'i CRC'ye giriyor, son bayt hic girmiyordu.
    //
    // Cerceve yapisi kusursuz gorunuyor — onsoz, MAC, IP saglamasi,
    // hepsi dogru — ama CRC yanlis, ve karsi taraf cerceveyi
    // SESSIZCE atiyor. Kartta hicbir belirti yok, ana bilgisayarda
    // veri yok.
    //
    // Cozum: bayti birlesimsel olarak uret, hem cikisa hem CRC'ye
    // ayni degeri ver.
    // ---------------------------------------------------------------
    reg [7:0] sonraki;

    always @(*) begin
        sonraki = 8'd0;
        case (durum)
        D_ONSOZ: sonraki = (sayac == 6'd7) ? 8'hD5 : 8'h55;
        D_ETH: case (sayac)
            6'd0:  sonraki = HEDEF_MAC[47:40];
            6'd1:  sonraki = HEDEF_MAC[39:32];
            6'd2:  sonraki = HEDEF_MAC[31:24];
            6'd3:  sonraki = HEDEF_MAC[23:16];
            6'd4:  sonraki = HEDEF_MAC[15:8];
            6'd5:  sonraki = HEDEF_MAC[7:0];
            6'd6:  sonraki = KAYNAK_MAC[47:40];
            6'd7:  sonraki = KAYNAK_MAC[39:32];
            6'd8:  sonraki = KAYNAK_MAC[31:24];
            6'd9:  sonraki = KAYNAK_MAC[23:16];
            6'd10: sonraki = KAYNAK_MAC[15:8];
            6'd11: sonraki = KAYNAK_MAC[7:0];
            6'd12: sonraki = 8'h08;
            6'd13: sonraki = 8'h00;
            default: sonraki = 8'd0;
        endcase
        D_IP: case (sayac)
            6'd0:  sonraki = 8'h45;
            6'd1:  sonraki = 8'h00;
            6'd2:  sonraki = ip_uzunluk[15:8];
            6'd3:  sonraki = ip_uzunluk[7:0];
            6'd4:  sonraki = 8'h00;
            6'd5:  sonraki = 8'h00;
            6'd6:  sonraki = 8'h40;
            6'd7:  sonraki = 8'h00;
            6'd8:  sonraki = 8'h40;
            6'd9:  sonraki = 8'h11;
            6'd10: sonraki = ip_saglama[15:8];
            6'd11: sonraki = ip_saglama[7:0];
            6'd12: sonraki = KAYNAK_IP[31:24];
            6'd13: sonraki = KAYNAK_IP[23:16];
            6'd14: sonraki = KAYNAK_IP[15:8];
            6'd15: sonraki = KAYNAK_IP[7:0];
            6'd16: sonraki = HEDEF_IP[31:24];
            6'd17: sonraki = HEDEF_IP[23:16];
            6'd18: sonraki = HEDEF_IP[15:8];
            6'd19: sonraki = HEDEF_IP[7:0];
            default: sonraki = 8'd0;
        endcase
        D_UDP: case (sayac)
            6'd0: sonraki = KAYNAK_PORT[15:8];
            6'd1: sonraki = KAYNAK_PORT[7:0];
            6'd2: sonraki = HEDEF_PORT[15:8];
            6'd3: sonraki = HEDEF_PORT[7:0];
            6'd4: sonraki = udp_uzunluk[15:8];
            6'd5: sonraki = udp_uzunluk[7:0];
            // UDP saglamasi sifir = "hesaplanmadi", IPv4'te izinli.
            // Hesaplasaydik butun yuku gormeden baslik yazamazdik.
            6'd6: sonraki = 8'h00;
            6'd7: sonraki = 8'h00;
            default: sonraki = 8'd0;
        endcase
        D_VERI: sonraki = veri;
        D_FCS: case (sayac)
            6'd0: sonraki = fcs[7:0];
            6'd1: sonraki = fcs[15:8];
            6'd2: sonraki = fcs[23:16];
            6'd3: sonraki = fcs[31:24];
            default: sonraki = 8'd0;
        endcase
        default: sonraki = 8'd0;
        endcase
    end

    // CRC onsozu ve FCS'nin kendisini KAPSAMAZ.
    wire crc_al = (durum == D_ETH) || (durum == D_IP) ||
                  (durum == D_UDP) || (durum == D_VERI);

    always @(posedge clk) begin
        if (rst) begin
            durum         <= D_BOS;
            sayac         <= 6'd0;
            veri_sayaci   <= 16'd0;
            cikis_gecerli <= 1'b0;
            nibble        <= 1'b0;
            crc           <= 32'hFFFFFFFF;
            rgmii_tctl    <= 1'b0;
            rgmii_td      <= 4'd0;
            cikis_bayt    <= 8'd0;
        end else begin
            // NIBBLE SIRASI: ONCE ALT. RGMII'de yukselen kenarda alt,
            // dusen kenarda ust nibble gidiyor. Ters yazarsan cerceve
            // bozulur ama sinyal "var" gorunur.
            if (cikis_gecerli) begin
                rgmii_td   <= nibble ? cikis_bayt[7:4] : cikis_bayt[3:0];
                rgmii_tctl <= 1'b1;
            end else begin
                rgmii_td   <= 4'd0;
                rgmii_tctl <= 1'b0;
            end

            nibble <= ~nibble;

            if (nibble) begin
                cikis_bayt <= sonraki;
                if (crc_al)
                    crc <= crc_bayt(crc, sonraki);

                case (durum)
                D_BOS: begin
                    cikis_gecerli <= 1'b0;
                    crc           <= 32'hFFFFFFFF;
                    if (veri_gecerli) begin
                        durum <= D_ONSOZ;
                        sayac <= 6'd0;
                    end
                end
                D_ONSOZ: begin
                    cikis_gecerli <= 1'b1;
                    if (sayac == 6'd7) begin durum <= D_ETH; sayac <= 6'd0; end
                    else sayac <= sayac + 1'b1;
                end
                D_ETH: begin
                    if (sayac == 6'd13) begin durum <= D_IP; sayac <= 6'd0; end
                    else sayac <= sayac + 1'b1;
                end
                D_IP: begin
                    if (sayac == 6'd19) begin durum <= D_UDP; sayac <= 6'd0; end
                    else sayac <= sayac + 1'b1;
                end
                D_UDP: begin
                    if (sayac == 6'd7) begin
                        durum <= D_VERI; veri_sayaci <= 16'd0;
                    end else sayac <= sayac + 1'b1;
                end
                D_VERI: begin
                    if (veri_sayaci == yuk_uzunluk - 1) begin
                        durum <= D_FCS; sayac <= 6'd0;
                    end else veri_sayaci <= veri_sayaci + 1'b1;
                end
                D_FCS: begin
                    if (sayac == 6'd3) begin durum <= D_BOSLUK; sayac <= 6'd0; end
                    else sayac <= sayac + 1'b1;
                end
                D_BOSLUK: begin
                    cikis_gecerli <= 1'b0;
                    if (sayac == 6'd11) begin durum <= D_BOS; sayac <= 6'd0; end
                    else sayac <= sayac + 1'b1;
                end
                default: durum <= D_BOS;
                endcase
            end
        end
    end

endmodule

`default_nettype wire
