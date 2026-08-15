// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// UART alici + verici — hata ayiklama arayuzu.
//
// NEDEN VAR: kayit dosyasini yazacak HICBIR YOL YOKTU. ust.v'de
// kayit_adr/kayit_veri/kayit_yaz ust duzey portlardi ve kartta
// karsilik gelen pin yok; ethernet ALIS yolu da henuz yazilmadi.
// Yani bitstream yuklense bile NCO frekansi, azaltma orani, kanal
// maskesi hicbiri ayarlanamazdi — sentezci de sabit girisleri gorup
// DDC'nin buyuk kismini atardi. Kart geldiginde elde calisan bir
// alici degil, sessiz bir FPGA olurdu.
//
// Kartta DBG_RX/DBG_TX pinleri zaten cekili. UART ethernet'ten cok
// daha basit ve ethernet alis yolu yazilana kadar TEK kontrol yolu;
// yazildiktan sonra da kalir, cunku ethernet bozuldugunda hata
// ayiklamak icin bagimsiz bir yol gerekiyor.
//
// 8N1. Ornekleme bit ortasinda: baslangic bitinin dusen kenarindan
// yarim bit sonra baslayip her bit suresinde bir orneklemek, kenar
// yakininda ornekleyip saat farkindan bit kaydirmaktan guvenli.

`default_nettype none

module uart_al #(
    parameter BOLEN = 80          // saat / baud (80 MHz / 1 Mbaud)
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,
    output reg  [7:0] bayt,
    output reg        gecerli
);

    localparam YARIM = BOLEN / 2;

    // GIRIS SENKRONLANIYOR. rx baska bir saat alanindan (aslinda
    // hicbirinden) geliyor; dogrudan mantiga sokmak yarikararlilik
    // demek ve o hata ancak nadiren, uzun kosularda gorunur.
    reg rx_s1, rx_s2;
    always @(posedge clk) begin
        rx_s1 <= rx;
        rx_s2 <= rx_s1;
    end

    reg [1:0]  durum;
    reg [15:0] say;
    reg [3:0]  bit_no;
    reg [7:0]  kaydir;

    localparam D_BEKLE = 2'd0, D_BASLA = 2'd1, D_VERI = 2'd2, D_DUR = 2'd3;

    always @(posedge clk) begin
        if (rst) begin
            durum   <= D_BEKLE;
            gecerli <= 1'b0;
            say     <= 16'd0;
            bit_no  <= 4'd0;
        end else begin
            gecerli <= 1'b0;
            case (durum)
            D_BEKLE: if (!rx_s2) begin      // baslangic biti
                durum <= D_BASLA;
                say   <= 16'd0;
            end
            D_BASLA: if (say == YARIM - 1) begin
                // ortada hala dusukse gercek baslangic; degilse gurultu
                if (!rx_s2) begin
                    durum  <= D_VERI;
                    say    <= 16'd0;
                    bit_no <= 4'd0;
                end else durum <= D_BEKLE;
            end else say <= say + 1'b1;
            D_VERI: if (say == BOLEN - 1) begin
                say    <= 16'd0;
                kaydir <= {rx_s2, kaydir[7:1]};   // LSB once
                if (bit_no == 4'd7) durum <= D_DUR;
                else bit_no <= bit_no + 1'b1;
            end else say <= say + 1'b1;
            D_DUR: if (say == BOLEN - 1) begin
                // DUR BITI DENETLENIYOR. Yuksek degilse cerceve
                // kaymistir; bayti kabul etmek sessizce yanlis
                // kayit yazmak demek.
                if (rx_s2) begin
                    bayt    <= kaydir;
                    gecerli <= 1'b1;
                end
                durum <= D_BEKLE;
                say   <= 16'd0;
            end else say <= say + 1'b1;
            endcase
        end
    end

endmodule


module uart_ver #(
    parameter BOLEN = 80
) (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] bayt,
    input  wire       gonder,
    output reg        tx,
    output wire       mesgul
);

    reg [9:0]  kaydir;      // dur, veri[7:0], baslangic
    reg [3:0]  kalan;
    reg [15:0] say;

    assign mesgul = (kalan != 4'd0);

    always @(posedge clk) begin
        if (rst) begin
            tx    <= 1'b1;
            kalan <= 4'd0;
            say   <= 16'd0;
        end else if (kalan == 4'd0) begin
            tx <= 1'b1;
            if (gonder) begin
                kaydir <= {1'b1, bayt, 1'b0};
                kalan  <= 4'd10;
                say    <= 16'd0;
                tx     <= 1'b0;
            end
        end else if (say == BOLEN - 1) begin
            say    <= 16'd0;
            tx     <= kaydir[1];
            kaydir <= {1'b1, kaydir[9:1]};
            kalan  <= kalan - 1'b1;
        end else say <= say + 1'b1;
    end

endmodule

`default_nettype wire
