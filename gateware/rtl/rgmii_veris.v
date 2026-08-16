// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
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

    // RGMII, IKI YARIM KELIME.
    //
    // BU MODUL BIR NIBBLE/CEVRIM URETIYORDU — YANI SDR.
    // 4 bit x 125 MHz = 500 Mbit/s, ve RGMII'de PHY IKI kenari da
    // orneklediginden her nibble'i iki kez okurdu. Cerceve bozulur
    // ama hatlarda sinyal "var" gorunur; osiloskopta saglam, karsi
    // tarafta hicbir sey.
    //
    // Dogrusu: cevrim basina BIR BAYT. Alt nibble yukselen, ust
    // nibble dusen kenarda. Kenarlara ayirma isini ODDR ilkelleri
    // yapiyor ve onlar ust modulde; bu modul saf RTL kaliyor ki
    // test tezgahi satici ilkeli olmadan kosabilsin.
    //
    // TXCTL'IN DUSEN KENARI TXEN DEGIL. RGMII v2.0'da yukselen
    // kenarda TXEN, dusen kenarda TXEN xor TXERR gidiyor. Ikisine
    // de TXEN koymak hata bildirimini imkansiz kilar.
    output reg  [3:0]  rgmii_td_yuk,   // alt nibble  -> yukselen kenar
    output reg  [3:0]  rgmii_td_dus,   // ust nibble  -> dusen kenar
    output reg         rgmii_tctl_yuk, // TXEN
    output reg         rgmii_tctl_dus  // TXEN xor TXERR
);

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
    // GERIYE SAYIYORUZ, ILERI DEGIL.
    //
    // Once "veri_sayaci == yuk_uzunluk - 1" diye karsilastiriliyordu:
    // 16 bitlik bir buyukluk karsilastirmasi, ve yuk_uzunluk ust
    // modulden gelen genis bir sabit ag. O ifade hem FIFO okuma
    // izniini hem durum gecisini suruyordu, yani iki modul arasinda
    // uzun bir birlesimsel yol olusuyordu — ethernet alani 108 MHz'e
    // dustu.
    //
    // Geri sayinca karsilastirma SABITLE oluyor ("== 1"), yani bir
    // kac kapiya iniyor ve yuk_uzunluk sadece yukleme aninda
    // kullaniliyor.
    reg [15:0] veri_kalan;

    // "SON BAYT" BAYRAGI YAZMACTA.
    //
    // "veri_kalan == 1" ifadesi 16 bitlik bir karsilastirma ve
    // FIFO'nun tuketim yolunu suruyordu: rgmii'nin yazmaci ->
    // karsilastirma -> veri_cek -> FIFO'nun isaretci cogullayicisi.
    // Iki modul boyunca 38 mantik kademesi, ve clk_eth kapanmasi
    // TOHUMA BAGLI kaldi (117 / 125 / 129 MHz).
    //
    // Sayac ne zaman degistigini biliyoruz, o yuzden bayragi bir
    // cevrim ONCEDEN kurabiliyoruz: 2'ye dusen sayac, sonraki
    // cevrimde 1 olacak. Karsilastirma kritik yoldan tamamen cikiyor.
    reg veri_son_bayt;
    reg [7:0]  cikis_bayt;
    reg        cikis_gecerli;

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

    // CRC BAYT BAYT.
    //
    // Bir ara nibble nibble bolunmustu, cunku bayt iki cevrimde
    // gidiyordu. Bayt artik TEK cevrimde gittigine gore boyle bir
    // bolme yok: bolseydik cevrim basina yarim bayt islenirdi ve
    // CRC akisin gerisinde kalirdi.
    // Olculdu, tahmin degil.
    //
    // Dongu sentezde aciliyor: sonuc sabit bir XOR agi, ardisik
    // sekiz adim degil. Derinligi olcup karar veriyoruz, tahminle
    // bolmuyoruz.
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

    // FCS, SON BAYT ISLENDIKTEN SONRAKI CRC'DEN.
    // "~crc" yazinca son veri baytinin CRC'si henuz islenmemis
    // oluyordu: FCS yuklenirken crc o baytin oncesindeki degeri
    // tutuyor. Son baytin sonucunu birlesimsel hesaplayip ondan
    // aliyoruz — o an yuklenen FCS butun cerceveyi kapsiyor.
    // FCS BIR KEZ YAKALANIP DONDURULUYOR.
    // Dogrudan ~crc kullanmak yetmedi: D_FCS'e gecerken crc_al bir
    // bayt daha acik kaliyor ve CRC guncellenmeye devam ediyor, yani
    // dort FCS bayti dort FARKLI degerden okunuyordu. Cercevede ilk
    // bayt dogru cikip gerisi kayiyordu — f7 8c 84 f3 yerine
    // f7 d0 4f 38 olmaliydi.
    wire [31:0] crc_tamam = crc_bayt(crc, cikis_bayt);
    reg  [31:0] fcs;

    // SON VERI BAYTI DA BAYTLA BIRLIKTE ILERLIYOR.
    // veri_kalan durumla beraber sayiyor ama cikis_bayt bir bayt
    // geride; "veri_kalan == 1" anina bakinca elde SONDAN BIR
    // ONCEKI bayt oluyor ve FCS o degerden donduruluyordu.
    wire son_veri_ham = (durum == D_VERI) && veri_son_bayt;
    reg  son_veri;

    // ILK FCS BAYTI YAZMACI BEKLEYEMEZ. cikis_bayt ile fcs ayni
    // kenarda yazildigi icin ilk bayt eski (sifir) degeri aliyordu:
    // 00 d0 4f 38 cikti, f7 d0 4f 38 olmaliydi. Son veri baytinin
    // uzerindeyken tamamlanmis degeri dogrudan kullan.
    wire [31:0] fcs_simdi = son_veri ? ~crc_tamam : fcs;

    // ---------------------------------------------------------------
    // FIFO'DAN BIR CEVRIM ONDEN OKUNUYOR.
    //
    // Bayt blok RAM'den cikip DOGRUDAN "sonraki" cogullayicisina
    // giriyordu. DP16KD'nin kendi saat-cikis gecikmesi 5.83 ns; ustune
    // mux'in 3.6 ns'i binince yol 9.4 ns oldu ve ethernet alani
    // 106 MHz'de kaldi — 1000BASE-T 125 istiyor.
    //
    // Cozum bellegi hizlandirmak degil, ARDINA YAZMAC KOYMAK: FIFO bir
    // cevrim once okunuyor, gelen bayt veri_r'ye giriyor, mux artik
    // duz bir flip-flop cikisi goruyor. Blok RAM'in gecikmesi tek
    // basina bir cevrime rahat siginiyor.
    //
    // Sayim degismiyor: D_UDP'nin son cevriminde bir bayt, sonra
    // D_VERI boyunca N-1 bayt = toplam N.
    wire veri_cek = (durum == D_UDP  && sayac == 6'd7) ||
                    (durum == D_VERI && !veri_son_bayt);
    assign veri_hazir = veri_cek;

    reg [7:0] veri_r;
    always @(posedge clk)
        if (rst) veri_r <= 8'd0;
        else     veri_r <= veri;

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
        D_VERI: sonraki = veri_r;
        D_FCS: case (sayac)
            6'd0: sonraki = fcs_simdi[7:0];
            6'd1: sonraki = fcs_simdi[15:8];
            6'd2: sonraki = fcs_simdi[23:16];
            6'd3: sonraki = fcs_simdi[31:24];
            default: sonraki = 8'd0;
        endcase
        default: sonraki = 8'd0;
        endcase
    end

    // CRC onsozu ve FCS'nin kendisini KAPSAMAZ.
    wire crc_al_ham = (durum == D_ETH) || (durum == D_IP) ||
                      (durum == D_UDP) || (durum == D_VERI);

    // BAYRAK BAYTLA BIRLIKTE ILERLEMELI.
    // durum, cikis_bayt'tan bir bayt ONDE: bayt yuklenirken durum
    // zaten sonraki kademeye gecmis oluyor. Bayrak dogrudan durumdan
    // alininca onsozun 0xD5'i CRC'ye giriyordu (izlendi: durum=D_ETH
    // iken cikis_bayt hala 0xD5). Bayragi bayt ile ayni anda
    // yakaliyoruz.
    reg crc_al;


    always @(posedge clk) begin
        if (rst) begin
            durum         <= D_BOS;
            sayac         <= 6'd0;
            veri_kalan    <= 16'd0;
            veri_son_bayt <= 1'b0;
            cikis_gecerli <= 1'b0;
            crc           <= 32'hFFFFFFFF;
            rgmii_tctl_yuk <= 1'b0;
            rgmii_tctl_dus <= 1'b0;
            rgmii_td_yuk   <= 4'd0;
            rgmii_td_dus   <= 4'd0;
            cikis_bayt    <= 8'd0;
            crc_al        <= 1'b0;
            son_veri      <= 1'b0;
            fcs           <= 32'd0;
        end else begin
            // NIBBLE SIRASI: ONCE ALT. RGMII'de yukselen kenarda alt,
            // dusen kenarda ust nibble gidiyor. Ters yazarsan cerceve
            // bozulur ama sinyal "var" gorunur.
            if (cikis_gecerli) begin
                rgmii_td_yuk   <= cikis_bayt[3:0];
                rgmii_td_dus   <= cikis_bayt[7:4];
                rgmii_tctl_yuk <= 1'b1;
                rgmii_tctl_dus <= 1'b1;   // TXEN xor TXERR, hata yok
            end else begin
                rgmii_td_yuk   <= 4'd0;
                rgmii_td_dus   <= 4'd0;
                rgmii_tctl_yuk <= 1'b0;
                rgmii_tctl_dus <= 1'b0;
            end

            if (crc_al)
                crc <= crc_tamam;

            begin
                cikis_bayt <= sonraki;
                crc_al     <= crc_al_ham;
                son_veri   <= son_veri_ham;
                // elde son veri bayti varsa ve simdi bitiyorsa,
                // tamamlanmis CRC'yi dondur
                if (son_veri)
                    fcs <= ~crc_tamam;

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
                        durum         <= D_VERI;
                        veri_kalan    <= yuk_uzunluk;
                        veri_son_bayt <= (yuk_uzunluk == 16'd1);
                    end else sayac <= sayac + 1'b1;
                end
                D_VERI: begin
                    if (veri_son_bayt) begin
                        durum <= D_FCS; sayac <= 6'd0;
                    end else begin
                        veri_kalan    <= veri_kalan - 1'b1;
                        // bir sonraki cevrimde 1 olacak mi
                        veri_son_bayt <= (veri_kalan == 16'd2);
                    end
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
