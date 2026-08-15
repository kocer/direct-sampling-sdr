// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// Paketleyici — DDC cikisini ethernet cercevesine hazirlar.
//
// Dort kanalin I ve Q'sunu tek akista topluyor. Her paket bir
// BASLIK ve ardindan N ornek grubu tasiyor.
//
// BASLIK NEDEN VAR: alici tarafta paket kaybi ve siralama sorunu
// olacak. Ethernet sirayi garanti etmiyor, ve UDP paketi
// kaybolabiliyor. Ornek sayaci olmadan kaybi fark edemezsin — ve
// fark edilmeyen bir kayip faz surekliligini bozar, yani dort kanalin
// faz uyumu sessizce cop olur. Bu kartin butun degeri o uyum.
//
// PAKET BICIMI (ag sirasi, big-endian):
//
//   0   sihir      4 bayt  0x53445234 ("SDR4")
//   4   surum      1
//   5   kanal_maskesi 1    hangi kanallar aktif
//   6   azalt_log2 1       R'nin log2'si
//   7   bayrak     1       bit0 tasma, bit1 saat kaybi
//   8   ornek_no   8 bayt  ilk ornegin mutlak numarasi
//  16   ornek...           kanal basina I,Q; 24 bit isaretli, 3'er bayt
//
// 24 BIT, 32 DEGIL: ornek 24 bit ve dolgu koymuyoruz. 32 bit
// hizalama kodu kolaylastirirdi ama bant genisligini ucte bir
// artirirdi. Dort kanal x 1.25 MSPS x 6 bayt = 30 MB/s; gigabit
// ethernet kaldirir ama iki kartlik yer birakmak istiyoruz.
//
// ORNEK NUMARASI 64 BIT: 80 MHz'te 32 bit sayac 54 saniyede sariyor.
// Sarma anini dogru islemek ekstra kod ve ekstra hata kaynagi; 64 bit
// 7000 yil dayaniyor.

`default_nettype none

module paketleyici #(
    parameter ORNEK_BIT   = 24,
    // PAKET BOYU MTU'YA VE CERCEVEYE GORE SECILIYOR.
    //
    // 128 yaziyordu: paket = 16 baslik + 128*24 = 3088 bayt.
    // Iki ayri sorun vardi:
    //   1 Standart MTU 1500; 3088 bayt zaten sigmiyordu.
    //   2 ust.v RGMII'ye 1024 baytlik cerceve soyluyordu. Cerceve
    //     1024'te kesiliyor, akis devam ediyordu — ikinci cerceve
    //     paketin ORTASINDAN basliyor, SIHIR sayisi rastgele ofsette
    //     goruluyor ve alici hicbir paketi cozemiyor.
    //
    // UDP yuku en fazla 1500 - 20 (IP) - 8 (UDP) = 1472 bayt.
    //   16 + N*24 <= 1472  ->  N <= 60.6  ->  N = 60
    //   paket = 16 + 1440 = 1456 bayt
    // ust.v'deki yuk_uzunluk BU sayiyla ayni olmali; ikisi ayri
    // yerde durdugu icin ust.v oradan turetiyor.
    parameter PAKET_ORNEK = 60      // paket basina kanal-ornek grubu
) (
    input  wire        clk,
    input  wire        rst,

    input  wire signed [ORNEK_BIT-1:0] i0, q0, i1, q1, i2, q2, i3, q3,
    input  wire [3:0]  kanal_gecerli,
    input  wire [3:0]  kanal_maskesi,
    input  wire [3:0]  azalt_log2,
    input  wire        tasma,
    input  wire        saat_kayip,

    // bayt akisi
    output reg  [7:0]  bayt,
    output reg         bayt_gecerli,
    output reg         paket_basi,
    output reg         paket_sonu,
    input  wire        hazir
);

    localparam SIHIR = 32'h53445234;

    localparam D_BOS   = 3'd0;
    localparam D_BASLIK= 3'd1;
    localparam D_ORNEK = 3'd2;

    reg [2:0]  durum;
    reg [4:0]  baslik_no;
    reg [63:0] ornek_no;
    reg [15:0] grup_sayaci;
    reg [4:0]  bayt_no;       // ornek grubu icinde
    reg        tasma_kilit;

    // ---------------------------------------------------------------
    // TUTUCU YAZMAC. Ornek darbesi tek cevrim; baslik yazilirken
    // gelip gecerse durum makinesi onu kaciriyor ve yeni darbe
    // bekleyerek takiliyordu (test 16 bayt basliktan sonra hic ornek
    // gormedi). Darbe geldigi anda sekiz degeri yakalayip bayrak
    // kaldiriyoruz; paketleyici tutucudan okuyor.
    //
    // Tek girisli tutucu yetiyor: ornekler 1.25 MSPS'te, yani 64
    // cevrimde bir geliyor, 24 baytlik grup 24 cevrimde bosaliyor.
    // ---------------------------------------------------------------
    reg signed [ORNEK_BIT-1:0] t_i [0:3];
    reg signed [ORNEK_BIT-1:0] t_q [0:3];
    reg                        tutucu_dolu;

    wire darbe = |(kanal_gecerli & kanal_maskesi);

    always @(posedge clk) begin
        if (rst) begin
            tutucu_dolu <= 1'b0;
        end else begin
            if (darbe) begin
                t_i[0] <= i0; t_q[0] <= q0;
                t_i[1] <= i1; t_q[1] <= q1;
                t_i[2] <= i2; t_q[2] <= q2;
                t_i[3] <= i3; t_q[3] <= q3;
                tutucu_dolu <= 1'b1;
            end else if (durum == D_ORNEK && bayt_no == 5'd23 && hazir) begin
                tutucu_dolu <= 1'b0;
            end
        end
    end

    wire kanal_hazir = tutucu_dolu;

    // ---------------------------------------------------------------
    // TASMA KILITLENIYOR, ANLIK DEGIL.
    // Tasma bir ornekte olur ve gecer; paket basligi ise paketin
    // basinda yaziliyor. Anlik bakarsak tasmayi kaciririz ve alici
    // "veri saglam" saniyor. Kilit paket basinda temizleniyor.
    // ---------------------------------------------------------------
    always @(posedge clk) begin
        if (rst)
            tasma_kilit <= 1'b0;
        else if (durum == D_BASLIK && baslik_no == 5'd0)
            tasma_kilit <= 1'b0;
        else if (tasma)
            tasma_kilit <= 1'b1;
    end

    integer c;
    always @(posedge clk) begin
        if (rst) begin
            durum        <= D_BOS;
            baslik_no    <= 5'd0;
            ornek_no     <= 64'd0;
            grup_sayaci  <= 16'd0;
            bayt_no      <= 5'd0;
            bayt_gecerli <= 1'b0;
            paket_basi   <= 1'b0;
            paket_sonu   <= 1'b0;
        end else begin
            bayt_gecerli <= 1'b0;
            paket_basi   <= 1'b0;
            paket_sonu   <= 1'b0;

            case (durum)
            // ------------------------------------------------ bos
            D_BOS: begin
                if (kanal_hazir && hazir) begin
                    durum       <= D_BASLIK;
                    baslik_no   <= 5'd0;
                    grup_sayaci <= 16'd0;
                    paket_basi  <= 1'b1;
                end
            end

            // ------------------------------------------------ baslik
            D_BASLIK: if (hazir) begin
                bayt_gecerli <= 1'b1;
                case (baslik_no)
                5'd0:  bayt <= SIHIR[31:24];
                5'd1:  bayt <= SIHIR[23:16];
                5'd2:  bayt <= SIHIR[15:8];
                5'd3:  bayt <= SIHIR[7:0];
                5'd4:  bayt <= 8'd1;                      // surum
                5'd5:  bayt <= {4'd0, kanal_maskesi};
                5'd6:  bayt <= {4'd0, azalt_log2};
                5'd7:  bayt <= {6'd0, saat_kayip, tasma_kilit};
                5'd8:  bayt <= ornek_no[63:56];
                5'd9:  bayt <= ornek_no[55:48];
                5'd10: bayt <= ornek_no[47:40];
                5'd11: bayt <= ornek_no[39:32];
                5'd12: bayt <= ornek_no[31:24];
                5'd13: bayt <= ornek_no[23:16];
                5'd14: bayt <= ornek_no[15:8];
                5'd15: bayt <= ornek_no[7:0];
                default: bayt <= 8'd0;
                endcase
                if (baslik_no == 5'd15) begin
                    durum   <= D_ORNEK;
                    bayt_no <= 5'd0;
                end else begin
                    baslik_no <= baslik_no + 1'b1;
                end
            end

            // ------------------------------------------------ ornek
            D_ORNEK: begin
                if (bayt_no == 5'd0 && !kanal_hazir) begin
                    // yeni ornek bekleniyor
                end else if (hazir) begin
                    bayt_gecerli <= 1'b1;
                    // 4 kanal x 2 yol x 3 bayt = 24 bayt
                    case (bayt_no[4:0])
                    5'd0:  bayt <= t_i[0][23:16]; 5'd1: bayt <= t_i[0][15:8];
                    5'd2:  bayt <= t_i[0][7:0];
                    5'd3:  bayt <= t_q[0][23:16]; 5'd4: bayt <= t_q[0][15:8];
                    5'd5:  bayt <= t_q[0][7:0];
                    5'd6:  bayt <= t_i[1][23:16]; 5'd7: bayt <= t_i[1][15:8];
                    5'd8:  bayt <= t_i[1][7:0];
                    5'd9:  bayt <= t_q[1][23:16]; 5'd10: bayt <= t_q[1][15:8];
                    5'd11: bayt <= t_q[1][7:0];
                    5'd12: bayt <= t_i[2][23:16]; 5'd13: bayt <= t_i[2][15:8];
                    5'd14: bayt <= t_i[2][7:0];
                    5'd15: bayt <= t_q[2][23:16]; 5'd16: bayt <= t_q[2][15:8];
                    5'd17: bayt <= t_q[2][7:0];
                    5'd18: bayt <= t_i[3][23:16]; 5'd19: bayt <= t_i[3][15:8];
                    5'd20: bayt <= t_i[3][7:0];
                    5'd21: bayt <= t_q[3][23:16]; 5'd22: bayt <= t_q[3][15:8];
                    5'd23: bayt <= t_q[3][7:0];
                    default: bayt <= 8'd0;
                    endcase

                    if (bayt_no == 5'd23) begin
                        bayt_no  <= 5'd0;
                        ornek_no <= ornek_no + 1'b1;
                        if (grup_sayaci == PAKET_ORNEK - 1) begin
                            durum      <= D_BOS;
                            paket_sonu <= 1'b1;
                        end else begin
                            grup_sayaci <= grup_sayaci + 1'b1;
                        end
                    end else begin
                        bayt_no <= bayt_no + 1'b1;
                    end
                end
            end

            default: durum <= D_BOS;
            endcase
        end
    end

endmodule

`default_nettype wire
