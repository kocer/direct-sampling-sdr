// Host arayuzu — UART baytlarindan kayit yazma/okuma.
//
// CERCEVE:
//   yazma  A5 adr d3 d2 d1 d0 xor      -> yanit 06 (kabul) / 15 (ret)
//   okuma  A6 adr xor                  -> yanit d3 d2 d1 d0
//   xor = adr ile veri baytlarinin XOR'u
//
// XOR NEDEN VAR: hatali bir bayt sessizce YANLIS KAYIT yazar. NCO
// artisina bozuk bir deger girerse alici yanlis frekansi dinler ve
// bu, "anten mi bozuk, filtre mi" diye gunlerce aranir. Bir baytlik
// denetim bunu ucuza kesiyor.
//
// ZAMAN ASIMI ILE HIZALANMA: veri baytlari 0xA5 olabilir, yani
// baslangic baytini beklemek tek basina hizalanma saglamaz. Cerceve
// ortasinda bayt akisi durursa (~1 ms) ayrisimciyi basa aliyoruz.
// Boylece bozulan bir baglantidan sonra sistem KENDILIGINDEN
// toparliyor; elle sifirlama gerekmiyor.

`default_nettype none

module host_arayuz #(
    parameter ZAMAN_ASIMI = 80000     // 1 ms @ 80 MHz
) (
    input  wire        clk,
    input  wire        rst,

    // UART
    input  wire [7:0]  al_bayt,
    input  wire        al_gecerli,
    output reg  [7:0]  ver_bayt,
    output reg         ver_gonder,
    input  wire        ver_mesgul,

    // kayit dosyasi
    output reg  [7:0]  kayit_adr,
    output reg  [31:0] kayit_veri,
    output reg         kayit_yaz,
    input  wire [31:0] kayit_oku
);

    localparam BAS_YAZ = 8'hA5;
    localparam BAS_OKU = 8'hA6;
    localparam KABUL   = 8'h06;
    localparam RET     = 8'h15;

    localparam D_BAS   = 3'd0;
    localparam D_ADR   = 3'd1;
    localparam D_VERI  = 3'd2;
    localparam D_XOR   = 3'd3;
    localparam D_OKUXR = 3'd4;
    localparam D_YANIT = 3'd5;

    reg [2:0]  durum;
    reg [1:0]  bayt_no;
    reg [7:0]  denet;
    reg [31:0] tampon;
    reg [1:0]  yanit_no;
    reg [31:0] yanit_veri;
    reg        yanit_uzun;      // 1 = dort bayt oku yaniti

    reg [16:0] asim;

    always @(posedge clk) begin
        if (rst) begin
            durum      <= D_BAS;
            kayit_yaz  <= 1'b0;
            ver_gonder <= 1'b0;
            asim       <= 17'd0;
        end else begin
            kayit_yaz  <= 1'b0;
            ver_gonder <= 1'b0;

            // ---- zaman asimi ----
            if (durum == D_BAS) begin
                asim <= 17'd0;
            end else if (al_gecerli) begin
                asim <= 17'd0;
            end else if (asim != ZAMAN_ASIMI[16:0]) begin
                asim <= asim + 1'b1;
            end else if (durum != D_YANIT) begin
                // cerceve ortasinda akis durdu, basa don
                durum <= D_BAS;
            end

            case (durum)
            D_BAS: if (al_gecerli) begin
                if (al_bayt == BAS_YAZ) begin
                    durum <= D_ADR; yanit_uzun <= 1'b0;
                end else if (al_bayt == BAS_OKU) begin
                    durum <= D_ADR; yanit_uzun <= 1'b1;
                end
            end

            D_ADR: if (al_gecerli) begin
                kayit_adr <= al_bayt;
                denet     <= al_bayt;
                bayt_no   <= 2'd0;
                durum     <= yanit_uzun ? D_OKUXR : D_VERI;
            end

            // VERI BAYTLARI BUYUK-UCLU. Insan okuyacak: elle
            // gonderilen bir komutta d3 d2 d1 d0 sirasi kayitla
            // ayni gorunsun diye.
            D_VERI: if (al_gecerli) begin
                tampon  <= {tampon[23:0], al_bayt};
                denet   <= denet ^ al_bayt;
                bayt_no <= bayt_no + 1'b1;
                if (bayt_no == 2'd3) durum <= D_XOR;
            end

            D_XOR: if (al_gecerli) begin
                if (al_bayt == denet) begin
                    kayit_veri <= tampon;
                    kayit_yaz  <= 1'b1;
                    ver_bayt   <= KABUL;
                end else begin
                    ver_bayt   <= RET;
                end
                ver_gonder <= 1'b1;
                durum      <= D_BAS;
            end

            D_OKUXR: if (al_gecerli) begin
                if (al_bayt == denet) begin
                    // KAYIT CIKISI BIR CEVRIM GECIKMELI.
                    // kayit.v okumayi yazmacliyor; adres burada bir
                    // cevrim once yazildi, yani kayit_oku artik
                    // gecerli.
                    yanit_veri <= kayit_oku;
                    yanit_no   <= 2'd0;
                    durum      <= D_YANIT;
                end else begin
                    ver_bayt   <= RET;
                    ver_gonder <= 1'b1;
                    durum      <= D_BAS;
                end
            end

            D_YANIT: if (!ver_mesgul && !ver_gonder) begin
                ver_bayt   <= yanit_veri[31:24];
                yanit_veri <= {yanit_veri[23:0], 8'd0};
                ver_gonder <= 1'b1;
                if (yanit_no == 2'd3) durum <= D_BAS;
                else yanit_no <= yanit_no + 1'b1;
            end

            default: durum <= D_BAS;
            endcase
        end
    end

endmodule

`default_nettype wire
