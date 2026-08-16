# Teknik gerekçe — üç karar

Bu belge tasarımın üç ana kararını ve sebebini anlatıyor. Uzun hâli ve
sayısal karnesi depo kökündeki `TASARIM.md` içinde; buradaki her
gerekçe oradan ve şema üreteçlerinin (`kicad/*/gen_*.py`) içindeki
yorumlardan derlendi.

---

## 1. Neden doğrudan örnekleme

Bu projenin öncülü Tayloe dedektörlü doğrudan dönüşüm alıcısıydı
(`pi-telsiz/TASARIM.md`). İyi bir alıcıydı ve üç tavana çarptı:

| Sorun | Tayloe'da | Doğrudan örneklemede |
|---|---|---|
| Anlık pencere | 96 kHz — ses kodeğinin sınırı | **40 MHz**, bütün HF aynı anda |
| Faz gürültüsü | LO'nun (Si5351) kirliliği doğrudan sinyale karışıyor | **LO yok** |
| Veriş temizliği | yazılım I/Q kalibrasyonu, −25…−50 dBc | **analog modülatör yok** |

Karıştırıcıyı kaldırınca kaldırdığın şey sadece bir parça değil: LO'nun
faz gürültüsü, karıştırıcının IMD'si, I/Q dengesizliği ve ayna
frekansı bir arada gidiyor. Geriye kalan hata kaynağı iki tane:
örnekleme saatinin jitter'i ve ADC'nin kendi doğrusallığı. İkisi de
**ölçülebilir ve veri sayfasında yazılı** büyüklükler, kalibrasyonla
kovalanan büyüklükler değil.

**Bedeli dürüstçe:** bütün HF aynı anda çipe giriyor. 6 MHz'deki
megavatlık yayın istasyonu, sen 14 MHz dinlerken ADC'nin tepesini
yiyor — IC-7300'ün gerçek dünyadaki zayıflığı bit sayısı değil bu.

**Çözüm, ve sıkışmadan:** klasik cevap ön seçici koymak, ama ön seçici
bandı bir bütün görme yeteneğini öldürüyor. AD9251 **çift** ADC olduğu
için ikisini birden yapıyoruz:

```
ana anten ─► koruma ─┬── ADC-1A ── ön seçici YOK ──────► PANORAMA + ham IQ
                     └── ADC-1B ── anahtarlamalı BPF ──► CİDDİ ALICI
```

Tek çip, tek saat; kanallar arası crosstalk veri sayfasına göre
−110 dBc. Geniş yol dar yolu kirletmiyor. C kartının varlık sebebi bu
anahtarlamalı BPF bankası: 4 kanal × 7 bant.

---

## 2. Neden dört kanal — huzme yönlendirme ve gürültü iptali

İkinci AD9251 kanal sayısını dörde çıkarıyor. Dördü de **aynı
VCXO'dan** besleniyor, yani faz uyumlu. Ayrı ayrı iki alıcıyla
yapılamayan üç şey burada başlıyor:

**Gürültü iptali.** İstasyon bir okul kampüsünde: anahtarlamalı güç
kaynağı, LED aydınlatma, şarj cihazı dolu. Ayrı bir antenle gürültüyü
örnekleyip ana kanaldan uyarlamalı olarak çıkarmak gerçek dünyada
10–20 dB kazandırabilir. Karnede IC-7300'ün 2 dB önümüzde olduğu
düşünülürse belirleyici olan bu.

**Yön bulma.** İki anten, faz farkı, geliş açısı. Radiosonde kovalama,
parazit avı, meteor izinin geliş yönü.

**Işın şekillendirme.** İki dikey anten = yönlendirilebilir sıfır.
İstemediğin yöndeki istasyonu söndürürsün.

Üçü de faz uyumuna bağlı ve faz uyumu **ortak saatten** geliyor.
Bunun bedeli yeni bir zorluk: tek VCXO iki ADC'yi doğrudan süremiyor,
düşük eklemeli jitter'li bir tampon gerekiyor (ADCLK846).

```
√(100² + 50²) = 112 fs        VCXO 100 fs + tampon 50 fs
```

100 fs'ten 112 fs'e — ihmal edilebilir. Ama tampon **eklemeli jitter
spec'i yazan** bir parça olmak zorunda, yoksa bütün saat bütçesi
çöpe gider.

Faz uyumu veriş tarafında da korunuyor: dört TX kanalı da aynı saatten,
yani veriş huzmesi de yönlendirilebilir. C kartındaki dört zayıflatıcı
bu yüzden var — şartnamede iki taneydi; faz uyumu zincirlerin **özdeş**
olmasını şart koşuyor, iki kanal zayıflatılıp ikisi zayıflatılmadan
bırakılamaz.

---

## 3. Neden ECP5 (LFE5U-25F)

**Tamamen açık kaynak araç zinciri.** Yosys + nextpnr-ecp5 + Project
Trellis ile sentezden bitstream'e kadar üretici yazılımı gerekmiyor.
Bir okul kulübü için bu lisans meselesi değil, süreklilik meselesi:
öğrenci mezun olduğunda araç zinciri hâlâ kurulabilir olmalı ve
bir hesabın arkasında kilitli olmamalı. Bu depoda gateware gerçekten
bu zincirle sentezleniyor (`gateware/sentez/ust.bit`).

**Varyant seçimi zorunluluktan.** LFE5U-45F pratikte tedarik edilemiyor
(bulunan varyantların stoğu 1–2 adet). LFE5U-25F ise $8.91 ve 510
adet stokta, üstelik `-7BG256I` sonundaki **I** endüstriyel sıcaklık
aralığı (−40…+100 °C) demek — uçurumda, güneş altında, IP65 kutuda
duracak bir alet için ticari sınıftan önemli. Hız derecesi −7, yani
−6'dan hızlı ve daha ucuz.

**ECP5-25 kısıtı mimariyi belirledi, ve zaten o mimari seçilmişti.**
Naif yaklaşım — sekiz kanalın her biri tam hızda karıştırıcı — DSP
dilimlerini aşıyor: 8 × 4 çarpma × 80 MHz = 32 çarpıcı gerekir, elde
28 var. İki kademeli DDC bunu çözüyor:

```
ADC → ORTAK ilk decimator (CIC, çarpıcısız)  80 MHz → 10 MHz
        ├─ kanal 1..8: NCO + karıştırıcı + FIR → 50 kHz
        │  (aynı çarpıcı seti, zaman paylaşımlı)
        └─ geniş yol: ham IQ çıkışı
```

FIR yükü 8 × 50 kHz × 100 tap = 40 M MAC/s; 80 MHz saatte ~0.5 çarpıcı.
Darboğaz DSP değil, tam hızda CIC'in zamanlama kapanışı — ve mevcut
durumda gerçekten orada duruyoruz (`README.md` §3, zamanlama açık
maddesi).

Ölçülen kullanım: LUT4 %44 (10771/24288), DSP %78 (22/28), blok RAM
%21 (12/56). Yani mantık tarafında yer var, çarpıcı tarafında yok —
tasarımın çarpıcı bütçesine göre kurulduğunun kanıtı.

**Neden BGA-256 göze alındı.** caBGA-256, 0.8 mm adım. Küçük paketler
(TQFP-144) yeterli I/O vermiyor: iki ADC (28 veri hattı), iki DAC
(31), SDRAM (39), iki gigabit PHY (24), kontrol yolu ve kart arası
bağlantılar toplamda bankaları dolduruyor — banka 1 şu an 32/32,
marj yok. 0.8 mm adım BGA, 6 katmanlı bir kartta ve JLCPCB'nin
standart süreçlerinde üretilebilir bir sınır.

---

## 4. Neden A sınıfı güç katı (D kartı)

Doğrudan örnekleme veriş tarafında analog modülatör kullanmıyor; DAC'ın
çıkışı zaten temiz. O temizliği bozacak tek yer güç katı. AB sınıfı bir
final geçiş bozulması üretir ve doğrudan örneklemenin kazandırdığı
spektral temizliği geri verir.

A sınıfı bunu üretmez; bedeli verimdir (100 W çıkış için ~233 W ısı) ve
o bedel bir okul istasyonunda ödenebilir: sabit kurulum, şebeke
beslemesi, uygun soğutucu. Karşılığında ölçülebilir bir IMD3 rakamı ve
DPD gerektirmeyen bir spektrum.

Bunun kartta yarattığı zorunluluklar: cihaz başına bias servosu
(INA240 akım ölçümü → LM358 integratörü → geçit), flanş sıcaklığı
ölçümü ve aşırı sıcaklıkta kesme, yönlü kuplörle ileri/yansıyan güç
ölçümü ve SWR koruması. D kartının parça sayısının büyük kısmı bu
koruma ve geri besleme zinciridir; çıkış katının kendisi dört
IRFP250N'den ibaret.
