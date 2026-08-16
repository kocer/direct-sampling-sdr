# Gateware mimarisi

Hedef: Lattice ECP5 LFE5U-25F, BG256. Açık kaynak zincir — yosys,
nextpnr-ecp5, prjtrellis. Tescilli araç yok.

## Neden bu bölünme

Kartın tek işi örneği almak ve göndermek. Bütün radyo işi burada.
Analogda yapılan her şey sıcaklıkla, gerilimle, parça toleransıyla
değişir; burada yapılan hiçbir şey değişmez. O yüzden sınırı olabildiğince
öne çekiyoruz: ADC'den sonrası tamamen sayısal.

## Saat alanları

| alan | frekans | kaynak | ne koşuyor |
|---|---|---|---|
| `clk_adc` | 80 MHz | ADC'nin DCO'su | ADC arayüzü, DDC ön ucu |
| `clk_sys` | 80 MHz | VCXO → PLL | DDC arkası, SDRAM, kontrol |
| `clk_eth` | 125 MHz | RGMII RXC | Ethernet MAC |
| `clk_dac` | 80 MHz | `clk_sys` | DAC arayüzü |

**Dört ADC kanalı aynı saat alanında.** Faz uyumunun tek şartı bu.
Kanal başına ayrı PLL kullanılmayacak — PLL'ler arasındaki faz
belirsizliği kalibre edilemez.

`clk_adc` ile `clk_sys` aynı frekansta ama **ayrı kaynaklardan**.
Aralarındaki geçiş asenkron sayılıyor: FIFO ile, elle senkronlayıcıyla
değil.

## Blok zinciri, alış

```
ADC LVDS  ->  ddr_giris  ->  [4 kanal]
                                |
                          nco + karistirici       (bant seçimi)
                                |
                          cic_azalt (R=1..2048)   (kaba azaltma)
                                |
                          cic_telafi (FIR)        (CIC'in eğimini düzelt)
                                |
                          fir_azalt (yarım bant)  (son azaltma)
                                |
                          paketleyici  ->  LiteEth  ->  ana bilgisayar
```

### Neden CIC + FIR, tek FIR değil

80 MSPS'ten 48 kSPS'e inmek 1666 kat azaltma demek. Tek FIR ile bu,
binlerce çarpanlı bir filtre olurdu; ECP5-25F'te 28 çarpan var.

CIC'in çarpanı yok — sadece toplayıcı ve fark alıcı. Kaba azaltmayı o
yapıyor. Bedeli geçirme bandındaki eğim (`sin(x)/x`), onu da sabit
katsayılı küçük bir FIR düzeltiyor. Son azaltma yarım bant filtreyle:
katsayılarının yarısı sıfır, yani çarpanın yarısı bedava.

## Blok zinciri, veriş

```
ana bilgisayar -> LiteEth -> tampon -> fir_artir -> nco + karistirici
                                                          |
                                                    dpd_onduzeltme
                                                          |
                                                      DAC arayuzu
```

`dpd_onduzeltme` başlangıçta birim kazanç. Kuplörden gelen örnekle
katsayılar sonradan öğreniliyor; donanım hazır, algoritma sonraya.

## Kontrol

Tek bir SPI ana birimi ve kaydırmalı yazmaç zinciri hepsini sürüyor:

- C kartındaki 4 PE4312 zayıflatıcı
- D kartındaki PE4312, bias DAC'ları, güç ADC'si
- Bant röleleri (28 adet, C kartı)
- T/R röleleri (4 adet)
- LPF röleleri (7 adet, D kartı)

Zincir `A -> C -> D1 -> D2 -> D3 -> D4` diye uzuyor. Ek PA kartı FPGA'da
pin harcamıyor.

**`PA_INHIBIT` zincirde değil, doğrudan pin.** Güvenlik hattı bir
yazmacın arkasında duramaz.

## Test edilebilirlik

Her blok kendi test tezgahıyla geliyor ve karta ihtiyaç duymuyor.
Zincirin tamamı `sim/` altında koşuyor: sentetik ADC örneği giriyor,
paket çıkıyor, beklenen sonuçla karşılaştırılıyor.

Kart gelmeden önce şunları doğrulayabiliyoruz:

- DDC'nin frekans cevabı ve azaltma oranı
- Dört kanalın faz farkının sıfır kaldığı
- Paket biçimi ve ethernet akışı
- Kontrol zincirinin doğru biti doğru röleye gönderdiği
- Aşırı yükte kırpma davranışı

Doğrulayamadıklarımız: gerçek gürültü tabanı, saat jitter'ının etkisi,
analog ön ucun gerçek cevabı, EMC.

## Yapılış sırası

1. `adc_giris` + test tezgahı — örnek gerçekten geliyor mu
2. `nco` + `karistirici` — bant seçimi
3. `cic_azalt` + telafi — asıl azaltma
4. `paketleyici` + LiteEth — ana bilgisayara akış
5. Kontrol zinciri — röleler ve zayıflatıcılar
6. Veriş yolu
7. DPD

Her adım bir öncekinin üstüne biniyor ve her adımın kendi testi var.
