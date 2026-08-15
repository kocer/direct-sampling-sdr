// Veris zinciri testi.
//
// Ikisi olculuyor:
//
// 1 TASIYICI. Taban banda DC (sabit I, Q=0) verince cikis, NCO
//   frekansinda saf bir sinus olmali. Sifir gecislerini sayip
//   frekansi dogruluyoruz.
//
// 2 GIRIS DOYURMASI. Tam olcegin ustunde bir giris CIC'i sarmamali.
//
//   ARALIGA BAKMAK YETMIYOR. Sarma zaten cikisi DAC araliginin
//   icinde tutuyor — cunku sarma tam da bitleri kesip atmak demek.
//   Yani "arali asilmadi" testi sarmayi ASLA yakalayamaz; onceki
//   hali tam bu yuzden hatayi gormeden geciyordu.
//
//   Sarmanin gercek imzasi ANI ISARET DONMESI: tepede +tam olcek
//   olmasi gereken ornek -tam olcege atliyor. Ornekten ornege
//   siçramayi olcuyoruz.
//
//   NOT: bu denetim su anki olceklemede TETIKLENMIYOR — olctum,
//   |ci| en fazla 29490'a cikiyor (sinir 32767). Yani test simdi
//   bir hatayi yakalamiyor, bir OZELLIGI koruyor: olcekleme
//   degisirse burasi duser. 7.1 MHz tasiyicida 80 MSPS ile bir
//   periyot ~11 ornek, yani ardisik iki ornek arasindaki en buyuk
//   dogal fark tepe genligin ~%57'si. Bunun cok ustu = sarma.
`timescale 1ns/1ps
`default_nettype none
module tb_duc;
    localparam real F_SAAT = 80.0e6;
    reg clk=0, rst=1; always #6.25 clk=~clk;
    reg signed [15:0] i_g=0, q_g=0; reg gv=0;
    reg [11:0] oran = 12'd16;
    reg [31:0] artis = 32'd381120000;   // 7.1 MHz
    wire signed [13:0] dac; wire dv, hazir;

    duc dut(.clk(clk),.rst(rst),.i_giris(i_g),.q_giris(q_g),
            .giris_gecerli(gv),.giris_hazir(hazir),
            .artir_orani(oran),.faz_artis(artis),.faz_ofset(32'd0),.faz_yukle(1'b0),.izin(1'b1),
            .dac(dac),.dac_gecerli(dv));

    integer n, gecis, hata=0;
    integer dmin, dmaks, en_sicrama;
    reg signed [13:0] onceki;
    real olculen;

    task kos(input signed [15:0] deger, input [200*8-1:0] ad);
        begin
            rst=1; gv=0; #200; @(posedge clk); #1; rst=0;
            i_g=deger; q_g=0; gv=1;
            gecis=0; dmin=1<<20; dmaks=-(1<<20); onceki=0; en_sicrama=0;
            for (n=0; n<160000; n=n+1) begin
                @(posedge clk);
                if (n>2000) begin
                    if (onceki<0 && dac>=0) gecis=gecis+1;
                    if (dac>dmaks) dmaks=dac;
                    if (dac<dmin)  dmin=dac;
                    if ((dac-onceki) > en_sicrama)  en_sicrama = dac-onceki;
                    if ((onceki-dac) > en_sicrama)  en_sicrama = onceki-dac;
                end
                onceki=dac;
            end
            olculen = gecis*F_SAAT/158000.0;
            $display("  %0s", ad);
            $display("     cikis %0d..%0d, frekans %0.2f MHz, en buyuk sicrama %0d",
                     dmin, dmaks, olculen/1e6, en_sicrama);
        end
    endtask

    initial begin
        $display("Veris zinciri testi");
        kos(16'sd8000, "normal giris: 7.1 MHz tasiyici bekleniyor");
        if (olculen < 6.9e6 || olculen > 7.3e6) begin
            $display("  HATA: tasiyici frekansi tutmuyor");
            hata=hata+1;
        end
        kos(16'sd32000, "tam olcek ustu: doyurma calismali");
        if (dmaks > 8191 || dmin < -8192) begin
            $display("  HATA: DAC araligi asildi");
            hata=hata+1;
        end
        // SARMA DENETIMI. Tepeden tepeye genligin %70'inden buyuk bir
        // ornek-ornek sicrama, 7.1 MHz'lik bir tasiyicida dogal
        // olarak olusamaz; isaret donmesi demektir.
        if (en_sicrama > ((dmaks - dmin) * 70) / 100) begin
            $display("  HATA: %0d'lik sicrama, tepeden tepeye %0d — CIC sariyor",
                     en_sicrama, dmaks - dmin);
            hata=hata+1;
        end else
            $display("     sarma yok (sicrama %0d, sinir %0d)",
                     en_sicrama, ((dmaks - dmin) * 70) / 100);
        if (olculen < 6.9e6 || olculen > 7.3e6) begin
            $display("  HATA: doyurma altinda tasiyici frekansi bozuldu");
            hata=hata+1;
        end
        if (hata==0) $display("Veris zinciri testi GECTI");
        else begin $display("Veris zinciri testi KALDI: %0d hata", hata); $fatal; end
        $finish;
    end
endmodule
`default_nettype wire
