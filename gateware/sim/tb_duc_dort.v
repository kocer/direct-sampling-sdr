// duc_dort testi — huzme yonlendirmenin ta kendisi olculuyor.
//
// Bu modulun tek isi dort kanalda AYNI genlikte, PROGRAMLANAN faz
// farkiyla tasiyici uretmek. O yuzden test tam bunu olcuyor:
//
//   1 GENLIK ESITLIGI. Dort kanalin tepe genligi bire bir tutmali.
//     Kanal 0 duc.v'nin ic karistiricisindan, 1-3 buradaki
//     karistiricilardan cikiyor; olcekleme ya da yuvarlama farki
//     olursa dort antenin biri farkli guc verir ve huzme sekli
//     bozulur — FAZLAR DOGRU OLSA BILE. Bu hata sahada ancak
//     antenle olcerek gorulur.
//
//   2 FAZ FARKI. Programlanan ofset ne ise kanallar arasi faz farki
//     o olmali. Yanlissa huzme baska yone bakar ve bunu anlamanin
//     tek yolu alan olcumu.
//
// Faz, sifir gecislerinin kanal 0'a gore kaymasindan olculuyor;
// genlik tepe degerinden.

`timescale 1ns/1ps
`default_nettype none

module tb_duc_dort;

    localparam DAC_BIT = 14;
    localparam real F_SAAT = 80.0e6;

    reg clk = 1'b0;
    always #6.25 clk = ~clk;
    reg rst = 1'b1;

    reg signed [15:0] i_g = 0, q_g = 0;
    reg               gv = 0;
    reg [11:0]        oran = 12'd16;
    // 5 MHz tasiyici: 5e6/80e6 * 2^32
    reg [31:0]        artis = 32'd268435456;
    reg [31:0]        ofs1 = 0, ofs2 = 0, ofs3 = 0;
    reg               yukle = 0;
    // IZIN — gercekte tx zinciri iki cevrimde bir ilerliyor (40 MSPS).
    // Testlerin cogu tam hizda kosuyor (izin=1) cunku modul hiza
    // duyarli degil; sonda ayri bir bolum izni gercek desende surup
    // faz iliskisinin korundugunu dogruluyor.
    reg               izin;
    // Uc bolumde izin surekli 1; son bolumde iki cevrimde bir.
    reg               izin_ac = 1'b0;
    reg               evre2 = 1'b0;
    always @(posedge clk) evre2 <= ~evre2;
    always @(*) izin = izin_ac ? evre2 : 1'b1;

    wire signed [DAC_BIT-1:0] d0, d1, d2, d3;
    wire dv, hazir;

    duc_dort dut (
        .clk(clk), .rst(rst),
        .i_giris(i_g), .q_giris(q_g),
        .giris_gecerli(gv), .giris_hazir(hazir),
        .artir_orani(oran), .faz_artis(artis),
        .faz_ofset1(ofs1), .faz_ofset2(ofs2), .faz_ofset3(ofs3),
        .faz_yukle(yukle), .izin(izin),
        .dac0(d0), .dac1(d1), .dac2(d2), .dac3(d3),
        .dac_gecerli(dv));

    integer n, hata = 0;
    integer tepe [0:3];
    integer gecis_t [0:3];        // ilk yukselen sifir gecisi zamani
    reg [3:0] gecis_bulundu;
    reg signed [DAC_BIT-1:0] onceki [0:3];

    task olc(input integer cevrim);
        integer k;
        begin
            for (k = 0; k < 4; k = k + 1) begin
                tepe[k] = 0; gecis_t[k] = 0; onceki[k] = 0;
            end
            gecis_bulundu = 4'd0;
            for (n = 0; n < cevrim; n = n + 1) begin
                @(posedge clk);
                if (n > 3000) begin
                    if (d0 > tepe[0]) tepe[0] = d0;
                    if (d1 > tepe[1]) tepe[1] = d1;
                    if (d2 > tepe[2]) tepe[2] = d2;
                    if (d3 > tepe[3]) tepe[3] = d3;
                    // ilk yukselen sifir gecisleri
                    if (!gecis_bulundu[0] && onceki[0] < 0 && d0 >= 0)
                        begin gecis_t[0] = n; gecis_bulundu[0] = 1; end
                    if (gecis_bulundu[0]) begin
                        if (!gecis_bulundu[1] && onceki[1] < 0 && d1 >= 0)
                            begin gecis_t[1] = n; gecis_bulundu[1] = 1; end
                        if (!gecis_bulundu[2] && onceki[2] < 0 && d2 >= 0)
                            begin gecis_t[2] = n; gecis_bulundu[2] = 1; end
                        if (!gecis_bulundu[3] && onceki[3] < 0 && d3 >= 0)
                            begin gecis_t[3] = n; gecis_bulundu[3] = 1; end
                    end
                end
                onceki[0] = d0; onceki[1] = d1; onceki[2] = d2; onceki[3] = d3;
            end
        end
    endtask

    // 5 MHz'te bir periyot = 16 cevrim (80/5)
    localparam integer PERIYOT = 16;
    // Izin iki cevrimde bir verilince ornek hizi yariya iniyor ve
    // ayni tasiyici iki kat cevrim suruyor.
    localparam integer PERIYOT_G = 32;

    // Beklenen faz DERECE olarak veriliyor, "k'nin 90 kati" olarak
    // degil. Once oyleydi ve ucuncu bolum ayni 90/180/270 desenini
    // tekrar kullanmak zorunda kaliyordu — o yuzden de kaybolan bir
    // faz yuklemesini goremiyordu: ofsetler zaten yuklu oldugu icin
    // ikinci yukleme hic olmasa da sonuc dogru cikiyordu.
    integer derece [1:3];
    task faz_denetle(input integer periyot);
        integer k, bekl, olcu, sapma;
        begin
            for (k = 1; k < 4; k = k + 1) begin
                // Faz ILERI kaydirilinca sifir gecisi ERKEN olur.
                bekl = (periyot * (360 - derece[k])) / 360;
                olcu = gecis_t[k] - gecis_t[0];
                while (olcu < 0) olcu = olcu + periyot;
                olcu = olcu % periyot;
                sapma = olcu - bekl;
                if (sapma > periyot/2)  sapma = sapma - periyot;
                if (sapma < -periyot/2) sapma = sapma + periyot;
                if (sapma < 0) sapma = -sapma;
                if (sapma > 1) begin
                    $display("  HATA: kanal %0d fazi %0d cevrim, beklenen %0d",
                             k, olcu, bekl);
                    hata = hata + 1;
                end else
                    $display("  kanal %0d faz farki dogru (%0d derece, %0d cevrim)",
                             k, derece[k], olcu);
            end
        end
    endtask

    initial begin
        $display("duc_dort testi (dort kanalli veris)");
        #200; @(posedge clk); #1; rst = 0;
        i_g = 16'sd8000; q_g = 0; gv = 1;

        // ---- 1. hepsi ayni fazda: genlikler esit, fazlar ayni ----
        ofs1 = 0; ofs2 = 0; ofs3 = 0;
        @(posedge clk); #1; yukle = 1; @(posedge clk); #1; yukle = 0;
        olc(40000);
        $display("  ayni faz: tepe %0d %0d %0d %0d",
                 tepe[0], tepe[1], tepe[2], tepe[3]);
        begin : genlik
            integer k, enb, enk;
            enb = tepe[0]; enk = tepe[0];
            for (k = 1; k < 4; k = k + 1) begin
                if (tepe[k] > enb) enb = tepe[k];
                if (tepe[k] < enk) enk = tepe[k];
            end
            // Dort kanal ayni olcekten geciyor; bir LSB'den fazla
            // fark sistematik bir olcekleme hatasi demektir.
            if (enb - enk > 1) begin
                $display("  HATA: genlik yayilimi %0d LSB, en fazla 1 olmali",
                         enb - enk);
                hata = hata + 1;
            end else $display("  genlikler esit (yayilim %0d LSB)", enb - enk);
        end

        // ---- 2. ceyrek periyot faz ofseti ----
        // 2^32 / 4 = 90 derece
        ofs1 = 32'h4000_0000;   //  90
        ofs2 = 32'h8000_0000;   // 180
        ofs3 = 32'hC000_0000;   // 270
        derece[1] = 90; derece[2] = 180; derece[3] = 270;
        @(posedge clk); #1; yukle = 1; @(posedge clk); #1; yukle = 0;
        olc(40000);
        $display("  faz ofsetli: tepe %0d %0d %0d %0d",
                 tepe[0], tepe[1], tepe[2], tepe[3]);
        $display("  sifir gecisi cevrimi: %0d %0d %0d %0d",
                 gecis_t[0], gecis_t[1], gecis_t[2], gecis_t[3]);
        faz_denetle(PERIYOT);
        // genlik faz ofsetinden ETKILENMEMELI
        begin : genlik2
            integer k, enb, enk;
            enb = tepe[0]; enk = tepe[0];
            for (k = 1; k < 4; k = k + 1) begin
                if (tepe[k] > enb) enb = tepe[k];
                if (tepe[k] < enk) enk = tepe[k];
            end
            if (enb - enk > 1) begin
                $display("  HATA: faz ofsetliyken genlik yayilimi %0d LSB",
                         enb - enk);
                hata = hata + 1;
            end else $display("  faz ofsetliyken de genlikler esit");
        end

        // ---- 3. GERCEK IZIN DESENI: 40 MSPS ----
        //
        // BURASI TASARIMIN GERCEK CALISMA NOKTASI. Yukaridaki iki
        // bolum izin=1 ile, yani 80 MSPS'te kosuyor; kart ise dort
        // kanali 40 MSPS'te suruyor (U31 cogullanmis, dac_cogullu.v).
        //
        // Izni eklerken en buyuk risk faz iliskisinin bozulmasiydi:
        // dort NCO ayni izinle ilerlemezse ya da yukleme darbesi
        // izin dusukken gelip kaybolursa kanallar arasi faz kayar ve
        // HUZME YANLIS YONE BAKAR. Cikis dalga bicimi yine kusursuz
        // gorunur — sahada anten olcmeden anlasilmaz.
        izin_ac = 1'b1;
        // OFSETLER 2. BOLUMDEN FARKLI. Ayni degerler kullanilsaydi
        // yukleme darbesi tamamen kaybolsa bile kanallar onceki
        // yuklemenin fazinda kalir ve test gecerdi.
        ofs1 = 32'h2000_0000;   //  45
        ofs2 = 32'h6000_0000;   // 135
        ofs3 = 32'hA000_0000;   // 225
        derece[1] = 45; derece[2] = 135; derece[3] = 225;
        // YUKLEME DARBESINI KASTEN IZINSIZ CEVRIME DENK GETIR.
        //
        // Ilk yazdigimda darbeyi rastgele biraktim ve test gecti —
        // ama nco.v'de yuklemeyi izne bagli hale getirip (bozuk
        // surum) tekrar kostugumda YINE gecti. Yani test hicbir sey
        // dogrulamiyordu: darbe o kosuda tesadufen izinli cevrime
        // dusmustu. Gercekte host ne zaman yazarsa o zaman dusuyor,
        // yani yazi tura. Sessizce kaybolan bir faz yuklemesi =
        // huzme yanlis yonde, ve her acilista baska bir yonde.
        //
        // Burada darbe MUTLAKA izin dusukken orneklenecek sekilde
        // hizalaniyor. Boylece test, yuklemenin izinden bagimsiz
        // olmasini gercekten sart kosuyor.
        @(posedge clk); #1;
        if (izin) begin @(posedge clk); #1; end
        yukle = 1; @(posedge clk); #1; yukle = 0;
        olc(80000);
        $display("  izinli (40 MSPS): tepe %0d %0d %0d %0d",
                 tepe[0], tepe[1], tepe[2], tepe[3]);
        faz_denetle(PERIYOT_G);
        begin : genlik3
            integer k, enb, enk;
            enb = tepe[0]; enk = tepe[0];
            for (k = 1; k < 4; k = k + 1) begin
                if (tepe[k] > enb) enb = tepe[k];
                if (tepe[k] < enk) enk = tepe[k];
            end
            if (enb - enk > 1) begin
                $display("  HATA: izinliyken genlik yayilimi %0d LSB", enb - enk);
                hata = hata + 1;
            end else $display("  izinliyken de genlikler esit");
        end

        if (hata == 0) $display("duc_dort testi GECTI");
        else           $display("duc_dort testi KALDI: %0d hata", hata);
        $finish;
    end

    initial begin
        #20_000_000;
        $display("duc_dort testi KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
