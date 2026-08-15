// Kontrol zinciri — roleler, zayiflaticilar, bias DAC'lari.
//
// Uc ayri yol var ve ucu de bu modulden cikiyor:
//
// 1 KAYDIRMALI YAZMAC ZINCIRI (RLY_SER, RLY_SRCLK, RLY_RCLK)
//   C kartinda 7 x 74HC595, D kartinda 1 tane, her ek PA'da 1 tane.
//   Roleler ve karta ozel secme sinyalleri buradan. Zincir
//   A -> C -> D1 -> D2 ... diye uzuyor; ek kart FPGA'da pin
//   harcamiyor.
//
// 2 SPI (ATT_DATA, ATT_CLK, ATT*_LE)
//   PE4312 zayiflaticilar. Veri ortak, LE karta ozel.
//
// 3 DOGRUDAN HAT (PA_INHIBIT)
//   Zincire GIRMIYOR. Guvenlik hatti bir yazmacin arkasinda duramaz:
//   yazmac bozulursa ya da saat durursa kesme calismaz.
//
// ZINCIR UZUNLUGU CALISMA ANINDA AYARLANIYOR. Kac PA karti takili
// oldugunu gateware bilmiyor; kayit dosyasindan geliyor. Fazla bit
// surmek zararsiz (zincirin sonundan dusuyor), eksik surmek son
// karti guncellemiyor.

`default_nettype none

module kontrol_zinciri #(
    parameter MAKS_BAYT = 16      // zincirde en fazla bu kadar 595
) (
    input  wire        clk,
    input  wire        rst,

    // kayit arayuzu
    input  wire [7:0]  yaz_veri,
    input  wire [4:0]  yaz_adr,
    input  wire        yaz_darbe,
    input  wire [4:0]  zincir_bayt,     // kac 595 var
    input  wire        gonder,          // zinciri sur

    // kaydirmali yazmac zinciri
    output reg         rly_ser,
    output reg         rly_srclk,
    output reg         rly_rclk,

    output wire        mesgul
);

    // ---------------------------------------------------------------
    // Zincir tamponu. Her bayt bir 595.
    // ---------------------------------------------------------------
    reg [7:0] tampon [0:MAKS_BAYT-1];

    integer i;
    always @(posedge clk) begin
        if (rst) begin
            for (i = 0; i < MAKS_BAYT; i = i + 1)
                tampon[i] <= 8'd0;
        end else if (yaz_darbe && yaz_adr < MAKS_BAYT) begin
            tampon[yaz_adr] <= yaz_veri;
        end
    end

    // ---------------------------------------------------------------
    // Surucu durum makinesi
    //
    // 595 zincirinde EN SON yazmac ILK surulen bayti alir. Yani
    // tamponu sondan basa gonderiyoruz. Ters gonderirsek roleler
    // dogru sayida ama yanlis kartta calisir — ve bu hata ancak
    // yanlis anten secildiginde fark edilir.
    // ---------------------------------------------------------------
    localparam D_BOS   = 2'd0;
    localparam D_SUR   = 2'd1;
    localparam D_KILIT = 2'd2;

    reg [1:0]  durum;
    reg [4:0]  bayt_no;      // sondan basa
    reg [3:0]  bit_no;
    reg [7:0]  kaydir;
    reg [3:0]  kilit_sayaci;

    assign mesgul = (durum != D_BOS);

    // SRCLK bolucusu: 595'in azami saat hizi 20 MHz (5 V'ta daha
    // dusuk). 80 MHz'i dorde boluyoruz -> 10 MHz kaydirma. Bu
    // hizda 16 bayt zincir 13 mikrosaniyede doluyor; role
    // anahtarlamasi milisaniye mertebesinde, yani sorun yok.
    reg [1:0] bolucu;

    always @(posedge clk) begin
        if (rst) begin
            durum        <= D_BOS;
            rly_ser      <= 1'b0;
            rly_srclk    <= 1'b0;
            rly_rclk     <= 1'b0;
            bolucu       <= 2'd0;
            bayt_no      <= 5'd0;
            bit_no       <= 4'd0;
            kilit_sayaci <= 4'd0;
        end else begin
            bolucu <= bolucu + 1'b1;

            case (durum)
            D_BOS: begin
                rly_srclk <= 1'b0;
                rly_rclk  <= 1'b0;
                if (gonder && zincir_bayt != 5'd0) begin
                    durum   <= D_SUR;
                    bayt_no <= zincir_bayt - 1'b1;   // sondan basla
                    bit_no  <= 4'd7;                 // MSB once
                    kaydir  <= tampon[zincir_bayt - 1'b1];
                    bolucu  <= 2'd0;
                end
            end

            D_SUR: begin
                case (bolucu)
                2'd0: begin
                    rly_ser   <= kaydir[7];
                    rly_srclk <= 1'b0;
                end
                2'd2: begin
                    rly_srclk <= 1'b1;      // yukselen kenarda yakalanir
                end
                2'd3: begin
                    rly_srclk <= 1'b0;
                    kaydir    <= {kaydir[6:0], 1'b0};
                    if (bit_no == 4'd0) begin
                        if (bayt_no == 5'd0) begin
                            durum        <= D_KILIT;
                            kilit_sayaci <= 4'd0;
                        end else begin
                            bayt_no <= bayt_no - 1'b1;
                            bit_no  <= 4'd7;
                            kaydir  <= tampon[bayt_no - 1'b1];
                        end
                    end else begin
                        bit_no <= bit_no - 1'b1;
                    end
                end
                default: ;
                endcase
            end

            // RCLK: butun bitler kaydiktan SONRA tek darbe.
            // Kaydirirken kilitlemek roleleri ara durumlarda
            // anahtarlar — bir bant filtresinin yanlis anda devreye
            // girmesi verirken PA'yi acik yuke sokabilir.
            D_KILIT: begin
                kilit_sayaci <= kilit_sayaci + 1'b1;
                if (kilit_sayaci == 4'd2)
                    rly_rclk <= 1'b1;
                else if (kilit_sayaci >= 4'd6) begin
                    rly_rclk <= 1'b0;
                    durum    <= D_BOS;
                end
            end

            default: durum <= D_BOS;
            endcase
        end
    end

endmodule

`default_nettype wire
