// Ethernet/IPv4/UDP ayikla — yuku host_arayuz'e ver.
//
// Alis yolunun ikinci yarisi: rgmii_alis cerceveyi bayta cevirdi,
// burada basliklar soyuluyor ve UDP yuku cikiyor. Yuk, UART'takiyle
// AYNI cerceve bicimini tasiyor (A5 adr d3 d2 d1 d0 xor), yani
// host_arayuz oldugu gibi yeniden kullaniliyor — ethernet ve UART
// icin iki ayri cozumleyici yazmak iki kat bakim demekti.
//
// ---------------------------------------------------------------------
// SAKLA-VE-ILET, GECISTIRME DEGIL.
//
// CRC ancak cerceve BITTIGINDE biliniyor. Yuku geldigi gibi yukari
// verirsek, bozuk bir cerceveden gelen kayit yazmasi CRC hatasi
// anlasilmadan ONCE uygulanmis olur. Bu kartta kayit yazmak zararsiz
// bir sey degil: PA iznini, verici frekansini ve role zincirini ayni
// arayuz suruyor. Bozuk bir pakete bakip 100 W'lik katin gate
// biasini degistirmek, tek bir bit hatasinin donanim oldurmesi
// demek.
//
// O yuzden yuk once tampona yaziliyor, CRC dogruysa disari
// veriliyor. Bedeli 256 bayt blok RAM ve bir cerceve gecikmesi.
// Kontrol yolu icin ikisi de bedava; bu yoldan ornek akmiyor.
// ---------------------------------------------------------------------
//
// NEDEN IPv4 + UDP, HAM ETHERNET DEGIL. Ham cerceve daha basit olurdu
// (baslik yok) ama host tarafinda AF_PACKET ve root gerektirir. UDP
// ile herhangi bir kullanici programi sıradan bir soketten yazar;
// okuldaki bilgisayarlarda root yok.
//
// SECENEKLI IP BASLIGI KABUL EDILMIYOR. IHL != 5 olan paket ATILIYOR.
// Destekliyormus gibi yapip ofseti yanlis hesaplamak, yuku bir yerden
// baslatir ve cozumleyici sacmalar; acikca atmak, host tarafinda
// "paket gitmiyor" diye hemen gorunur. Yerel agda secenekli IPv4
// basligi zaten pratikte cikmiyor.

`default_nettype none

module udp_ayikla #(
    // Dinlenen UDP portu. Kayit yazmalari buraya geliyor.
    parameter [15:0] PORT      = 16'd5001,
    parameter        TAMPON_BIT = 8          // 256 bayt
) (
    input  wire       clk,
    input  wire       rst,

    // rgmii_alis'ten
    input  wire [7:0] bayt,
    input  wire       bayt_gecerli,
    input  wire       cerceve_sonu,
    input  wire       crc_dogru,

    // host_arayuz'e
    output reg  [7:0] yuk_bayt,
    output reg        yuk_gecerli
);

    // -----------------------------------------------------------------
    // Cerceve icindeki konum. SFD'den sonraki ilk bayt = 0.
    // -----------------------------------------------------------------
    reg [10:0] sayac;

    // Baslik alanlarindan tutulacaklar
    reg [15:0] tip;          // EtherType
    reg [7:0]  ihl4;         // IP baslik uzunlugu, bayt
    reg [7:0]  protokol;
    reg [15:0] port_hedef;
    reg [15:0] udp_uzun;

    // Bu cerceve bize mi?
    reg uygun;               // simdiye kadar butun sinamalar gecti

    // Yuk tamponu
    reg [7:0] tampon [0:(1<<TAMPON_BIT)-1];
    reg [TAMPON_BIT-1:0] yaz_p;
    reg [TAMPON_BIT-1:0] uzunluk;

    // Yuk nerede basliyor: 14 (ethernet) + ihl4 + 8 (udp)
    wire [10:0] yuk_bas = 11'd14 + {3'd0, ihl4} + 11'd8;

    // -----------------------------------------------------------------
    // Bosaltma: cerceve saglamsa tamponu disari akit
    // -----------------------------------------------------------------
    localparam D_TOPLA  = 1'b0;
    localparam D_BOSALT = 1'b1;

    reg                  durum;
    reg [TAMPON_BIT-1:0] oku_p;

    always @(posedge clk) begin
        if (rst) begin
            sayac       <= 11'd0;
            uygun       <= 1'b0;
            yaz_p       <= {TAMPON_BIT{1'b0}};
            uzunluk     <= {TAMPON_BIT{1'b0}};
            durum       <= D_TOPLA;
            oku_p       <= {TAMPON_BIT{1'b0}};
            yuk_gecerli <= 1'b0;
            yuk_bayt    <= 8'd0;
            tip         <= 16'd0;
            ihl4        <= 8'd20;
            protokol    <= 8'd0;
            port_hedef  <= 16'd0;
            udp_uzun    <= 16'd0;
        end else begin
            yuk_gecerli <= 1'b0;

            case (durum)
            D_TOPLA: begin
                if (bayt_gecerli) begin
                    sayac <= sayac + 1'b1;
                    case (sayac)
                    11'd0:  begin uygun <= 1'b1; yaz_p <= {TAMPON_BIT{1'b0}}; end
                    11'd12: tip[15:8] <= bayt;
                    11'd13: begin
                        tip[7:0] <= bayt;
                        // IPv4 degilse gerisiyle ilgilenmiyoruz
                        if ({tip[15:8], bayt} != 16'h0800) uygun <= 1'b0;
                    end
                    11'd14: begin
                        // surum 4 ve IHL 5 (secenek yok) sart
                        if (bayt != 8'h45) uygun <= 1'b0;
                        ihl4 <= 8'd20;
                    end
                    11'd23: begin
                        protokol <= bayt;
                        if (bayt != 8'd17) uygun <= 1'b0;   // UDP
                    end
                    // UDP basligi 34'te basliyor (14 + 20)
                    11'd36: port_hedef[15:8] <= bayt;
                    11'd37: begin
                        port_hedef[7:0] <= bayt;
                        if ({port_hedef[15:8], bayt} != PORT) uygun <= 1'b0;
                    end
                    11'd38: udp_uzun[15:8] <= bayt;
                    11'd39: udp_uzun[7:0]  <= bayt;
                    default: ;
                    endcase

                    // yuk baslamissa tampona yaz
                    if (uygun && sayac >= yuk_bas &&
                        yaz_p != {TAMPON_BIT{1'b1}}) begin
                        tampon[yaz_p] <= bayt;
                        yaz_p <= yaz_p + 1'b1;
                    end
                end

                if (cerceve_sonu) begin
                    sayac <= 11'd0;
                    // SON DORT BAYT FCS — YUKUN PARCASI DEGIL.
                    // rgmii_alis FCS'i de veriyor (CRC'yi onunla
                    // dogruluyor). Tampona da girdiler; buradan
                    // dusulmezse host dort cop bayt gorur ve
                    // cozumleyici cerceve sinirini kaybeder.
                    if (uygun && crc_dogru && yaz_p > 4) begin
                        uzunluk <= yaz_p - 3'd4;
                        oku_p   <= {TAMPON_BIT{1'b0}};
                        durum   <= D_BOSALT;
                    end
                    uygun <= 1'b0;
                end
            end

            D_BOSALT: begin
                if (oku_p < uzunluk) begin
                    yuk_bayt    <= tampon[oku_p];
                    yuk_gecerli <= 1'b1;
                    oku_p       <= oku_p + 1'b1;
                end else begin
                    durum <= D_TOPLA;
                end
            end
            endcase
        end
    end

endmodule

`default_nettype wire
