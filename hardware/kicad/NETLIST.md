# A KARTI — NETLİST ŞARTNAMESİ

Şema bundan üretilecek. Amaç: bağlantıları **gözden geçirilebilir** hale
getirmek. 256 pinlik BGA'yı doğrudan `.kicad_sch`'e yazmak görsel olarak
doğrulanamaz; bu dosya doğrulanabilir.

> **Pin ataması BANKA bazında.** Tek tek BGA topu yazılmıyor. FPGA pinleri
> banka içinde takas edilebilir ve doğru atama layout sırasında, yol
> kesişmelerine göre kesinleşir. Şartname bankayı ve sayıyı sabitler.

---

## 0. ECP5 banka planı

`LFE5U-25F-7BG256I`, 184 kullanılabilir I/O + bank 8'de 13 konfig pini.

| Banka | Birim | I/O | VCCIO | İşlev | Kullanılan |
|---|---|---|---|---|---|
| 6 (sol) | 6 | 32 | **1.8 V** | ADC-1 + ADC-2 (çoğullamalı) | 30 |
| 7 (sol) | 7 | 32 | **3.3 V** | SDRAM (39'un 32'si) | 32 |
| 2 (sağ) | 4 | 32 | **3.3 V** | DAC-1 çift port | 32 |
| 3 (sağ) | 5 | 32 | **1.8 V** | PHY-1 + PHY-2 RGMII | 26 |
| 0 (üst) | 2 | 24 | **3.3 V** | SDRAM taşması 7 + kontrol 15 | 22 |
| 1 (üst) | 3 | 32 | **3.3 V** | DAC-2 interleaved 18 + GPS/VCXO/LED 14 | 32 |
| 8 (alt) | 8 | 13 | **3.3 V** | konfigürasyon + SPI flash | 6 |
| — | 1 | — | — | VCC/GND/VCCAUX | 35 pin |

**Toplam 180 / 197.** Banka 1 tam dolu, marj yok — oraya bir şey daha
eklenirse başka bankadan yer açılacak.

> **Şema çizilirken düzeltildi (08_control).** Banka 0'ın 24 I/O'su
> §7'deki listeye yetmedi: `RLY_RCLK` ve T/R kontrolün dört hattı
> banka 1'e kaydı. Banka 1 böylece 32/32 doldu ve durum LED'leri
> dışarıda kaldı — onlar röle kaydırmalı yazmacının boş çıkışlarından
> sürülecek, FPGA pini harcamayacak. Gerçek dağılım şemada.

> **HER ŞEY REV A'DA DOLDURULUYOR.** Ayak izi bırakıp sonra doldurma yok:
> iki ADC, iki DAC, iki PHY, SDRAM, GPSDO, harici referans girişi. Karar
> bilinçli — parça parça yapmak yerine tek seferde tam sürüm.

### Banka gerilimi neden böyle

```
ADC veri     1.8 V   DRVDD'yi 1.8'e alıyoruz — 3.3 V CMOS anahtarlama
                     gürültüsü aynı kartta analog girişe geri kuple oluyor
DAC veri     3.3 V   AD9767 lojik-1 eşiği 2.1 V @ DVDD 3.3 V
RGMII        1.8 V   RTL8211F 3.3/2.5/1.8/1.5 destekliyor; düşük EMI
konfig       3.3 V   W25Q128 3.3 V
```

---

## 1. GÜÇ AĞACI

Giriş 9–18 V DC, ters polarite korumalı (bkz §9).

```
VIN 9-18V ─► ters polarite (P-MOSFET) ─► TPS62130 ─► +3.3V  (ana ray)
                                                       │
   ┌───────────────────────────────────────────────────┤
   │                                                   │
   ├─► TPS62130 #2 ──► +1.1V   FPGA cekirdek           │
   ├─► TPS7A2033 ────► +1.8V   FPGA bank 6/7/3 VCCIO   │
   ├─► ADP150-2.5 ───► +2.5V   FPGA VCCAUX  (ZORUNLU)  │
   ├─► ADP150-1.8 ───► +1.8V_A ADC AVDD  (AYRI ADA)    │
   ├─► ADP150-1.8 ───► +1.8V_D ADC DRVDD               │
   ├─► ADP150-3.3 ───► +3.3V_CLK  VCXO   (AYRI ADA)    │
   └─► ADP150-3.3 ───► +3.3V_A    DAC AVDD             │
                                                        │
   PHY: DVDD33, AVDD33 ◄───────────────────────────────┘
        DVDD10, AVDD10 ◄── PHY dahili regülatör (REG_OUT + 2.2µH bobin)
```

> **+2.5 V atlanmıştı.** ECP5'in VCCAUX rayı 2.5 V ister (Cynthion'un
> güç şemasından doğrulandı). İlk güç ağacında yoktu; FPGA'yı çalıştırmayan
> türden bir eksik. `ADP150AUJZ-2.5-R7`, LCSC C144257, $1.00, 302 stok.

**Kritik ayrımlar:**
- `+3.3V_CLK` sadece VCXO'yu besler, kendi LDO'su, ferrit boncukla ayrılmış.
  Besleme gürültüsü doğrudan faz gürültüsüne dönüşüyor.
- `+1.8V_A` sadece ADC AVDD. Anahtarlamalı regülatörden **beslenmez**,
  3.3 V'tan LDO ile düşürülür.
- FPGA çekirdeği ve PHY anahtarlamalıdan beslenebilir, fiziksel olarak uzak.

### Güç sıralaması

ECP5: **VCCIO (3.3) → VCCAUX (2.5) → VCC (1.1)**. TPS62130'ların EN'leri
zincirlenir. ADC: AVDD ve DRVDD sırası serbest (datasheet kısıt koymuyor).

> **Bu satır önce ters yazılmıştı** ("VCC → VCCAUX → VCCIO"). Kart
> baştan beri doğrusunu yapıyor, yanlış olan belgeydi:
> U1 (VIN_PROT→+3V3) EN'i doğrudan girişte, hep açık; U8 (+3V3→+2V5);
> U2 (+3V3→+1V1) EN'i PG_3V3'ten, yani 3.3 V oturduktan sonra kalkıyor.
> Lattice'in kendi kılavuzu da bunu istiyor (ECP5 Hardware Checklist /
> sysIO Usage Guide): *"It is recommended that the I/O buffers be
> powered-up prior to the FPGA core fabric, which means VCCIO supplies
> should be powered before VCC and VCCAUX."*
> Ayrıca eski sıra topolojik olarak imkânsızdı: +1V1 buck'ı girişini
> +3V3'ten alıyor, çekirdek rayı önce kalkamaz.
> Yanlış belgeye bakıp "sırayı düzeltelim" diyen biri çalışan bir
> tasarımı bozardı; kaynak burada yazılı ki bir daha tartışılmasın.

### Ayrıştırma

| Nerede | Ne |
|---|---|
| Her ECP5 VCC/VCCIO topu | 100 nF, topa en yakın, viası doğrudan düzleme |
| ECP5 toplu | 4× 10 µF + 2× 47 µF |
| ADC AVDD ×8 | pin başına 100 nF + toplu 10 µF |
| ADC DRVDD ×4 | pin başına 100 nF |
| VCXO Vdd | 100 nF + 10 µF + **ferrit boncuk** |
| DAC AVDD/DVDD | 100 nF her pinde |
| PHY | datasheet önerisi, 10 µF X5R (Y5V KULLANMA — datasheet uyarıyor) |

---

## 2. SAAT DAĞITIMI

```
ABLNO-V-80.000MHZ
  pin 4 Vdd  ◄── +3.3V_CLK (ayrı LDO + ferrit)
  pin 2 GND
  pin 1 Vc   ◄── GPSDO kontrol (§7)
  pin 3 OUT  ──► saat tamponu ──┬─► ADC-1 CLK+/CLK−
                                ├─► ADC-2 CLK+/CLK−
                                ├─► DAC CLK1, CLK2
                                └─► FPGA PCLK girişi (bank 6 veya 7)
```

**Saat tamponu: ADCLK846BCPZ-REEL7** (LCSC C578957, $2.31, 1640 stok).
1:6 LVDS fanout, LFCSP-24 4×4, ADI saat dağıtım ailesi.

Neden bu: LMK1D1204'ten ucuz ve altı çıkışlı (dört yetmiyor). AD9251 saat
girişi PECL/LVDS/1.8 V CMOS kabul ediyor, LVDS doğrudan bağlanıyor.

```
çıkış 1 ──► ADC-1 CLK+/CLK−     LVDS, doğrudan
çıkış 2 ──► ADC-2 CLK+/CLK−     LVDS, doğrudan
çıkış 3 ──► FPGA PCLK           LVDS girişi
çıkış 4 ──► DAC saat yolu       ** çevirici gerekiyor, §10 **
çıkış 5 ──► test noktası
çıkış 6 ──► harici referans çıkışı (opsiyonel)
```

> **DAC saati sorunlu.** AD9767'nin CLK1/CLK2 girişi CMOS seviyesi
> (DVDD 3.3 V'ta lojik-1 eşiği 2.1 V), LVDS doğrudan süremiyor. İki yol:
> LVDS→CMOS çevirici, ya da saati FPGA'dan yeniden üret. İkincisi bedava
> ama FPGA çıkış jitter'ı (ps mertebesi) verilen sinyalin faz gürültüsüne
> giriyor. **Çevirici tercih edilmeli.** §10'a taşındı.

```
√(60² + 50²) = 78 fs      VCXO 60 fs + tampon 50 fs
```

ADC saat girişi diferansiyel (PECL/LVDS/1.8 V CMOS kabul ediyor). LVCMOS
tampondan tek uçlu sürülecekse CLK− uygun şekilde biaslanmalı; tercih
**diferansiyel tampon**, faz uyumu için de daha iyi.

> **FAZ UYUMU BURADAN GELİYOR.** Dört ADC kanalı ve iki DAC kanalı aynı
> saatten besleniyor. Tampon çıkışları arasındaki gecikme farkı sabit
> olmalı; eşit uzunlukta yol çek. Gürültü iptali, yön bulma ve ışın
> şekillendirme bu eşitliğe bağlı.

---

## 3. ADC — 2× AD9251

Her çip iki kanal. Toplam dört faz-uyumlu kanal.

### 3.1 Analog giriş (çip başına, iki kanal)

```
BNC ─► C kartı (koruma, zayıflatıcı, ön seçici) ─► ADT1-1WT+ ─┬─► VIN+
                                                              └─► VIN−
                                              VCM (pin 57) ───► trafo orta ucu
```

- Trafo ADT1-1WT+, 1:1. **Pinout (Rev.G s.2):** 3 PRI DOT · 1 PRI ·
  6 SEC DOT · 4 SEC · **2 SEC CT** · 5 kullanılmıyor
- **VCM (pin 57)** trafonun ikincil orta ucuna (pin 2) → ortak mod 0.9 V
- VIN çifti: eş boy, sıkı çift, kısa
- Giriş kapasitansı 6 pF, sürüş direnci ile birlikte kutup oluşturur

**Referans devre — AD9251 Şekil 42 + Tablo 9.** İlk çizimde bunların
üçü de eksikti; trafonun birincili açık devre görüyordu, yani 50 Ω hat
hiç sonlanmıyordu.

```
SMA ─┬─ 49.9Ω → GND          hattın sonlandığı yer
     └─ trafo PRI DOT (3),  PRI (1) → GND
        trafo SEC DOT (6) ─ Rs ─┬─ VIN+
        trafo SEC     (4) ─ Rs ─┴─ VIN−     C_dif VIN+ ↔ VIN−
        trafo SEC CT  (2) ─────── VCM
```

| Giriş frekansı | Rs (her biri) | C_dif |
|---|---|---|
| 0–70 MHz | 33 Ω | 22 pF |
| 70–200 MHz | 125 Ω | takılmıyor |

Tek değer ikisine birden uymuyor; alet hem tabanbant hem alt-örnekleme
yapıyor. Şemada 33 Ω + 22 pF çizili (HF/6 m). VHF/UHF alt-örneklemede
aynı ayak izine 125 Ω takılıp C sökülüyor — hepsi 0603, kart değişmiyor,
seçim montajda.

### 3.2 Referans ve bias

| Pin | Bağlantı |
|---|---|
| 55 VREF | 1 µF → AGND (dahili referans kullanılıyor) |
| 56 SENSE | **AGND'ye** → dahili 1.0 V referans seçilir |
| 57 VCM | 0.1 µF → AGND, ve trafo orta ucuna |
| 58 RBIAS | **10 kΩ %1** → AGND |

### 3.3 Dijital çıkış → FPGA

**Çoğullama KULLANILIYOR** (MUX açık). Karar değişti — önce reddetmiştim,
iki gerekçeyle geri alındı:

```
çoğullamasız   30 hat/çip, 80 MHz     → iki çip 60 pin, bütçe tutmuyor
çoğullamalı    15 hat/çip, 160 MHz    → iki çip 30 pin
```

1. ECP5 −7 hız derecesi pin başına 400+ Mbps DDR yapıyor. 160 MHz SDR
   agresif değil.
2. **Gürültü avantajı:** 30 yerine 15 anahtarlanan hat. Hassas analog ön
   ucun yanında daha az dijital gürültü. Bunu ilk seferde kaçırmıştım.

Çip başına 15 hat, iki çip **aynı bankada** (banka 6) — zamanlama eşleşmesi
ve faz uyumu için önemli:

| ADC pini | FPGA | Not |
|---|---|---|
| D0A…D13A (27,29-36,38-42) | banka 6 | çoğullanmış veri, A ve B dönüşümlü |
| DCOA (24) | banka 6, **saat-yetenekli pin** | 160 MHz veri saati |
| D0B…D13B | **kullanılmıyor** — çoğullama modunda boşta | |
| DCOB (23) | kullanılmıyor | |

Çoğullama SPI üzerinden açılıyor (bkz datasheet "Data Output Multiplex
Option"). Kanal sırası (önce A mı B mi) SPI'dan okunacak ve firmware'de
sabitlenecek.

ORA (43) / ORB (22) aralık-dışı bayrakları: bağlanabilir ama şart değil,
FPGA'da doygunluk zaten tespit edilebilir. **Bağla** — bedava ve ADC
doyduğunu bilmek panorama için değerli.

### 3.4 Kontrol

SPI, iki çip ortak yol, ayrı seçme:

| ADC pini | FPGA / bağlantı |
|---|---|
| 44 SDIO/DCS | bank 0, ortak (çift yönlü) |
| 45 SCLK/DFS | bank 0, ortak |
| 46 ~CSB | bank 0, **çip başına ayrı** (2 hat) |
| 47 ~OEB | AGND'ye (çıkışlar hep açık) |
| 48 PDWN | bank 0, çip başına ayrı, ya da GND |
| 3 SYNC | bank 0, **iki çipe ORTAK** ← faz uyumu için kritik |

> **SYNC iki çipe ortak ve eş uzunlukta gitmeli.** İki ADC'nin iç
> bölücülerini aynı anda sıfırlıyor. Faz uyumu buna bağlı.

### 3.5 Toprak

Pin 0 (exposed paddle) **çipin tek toprak bağlantısı.** Termal via dizisi
ile doğrudan toprak düzlemine. Datasheet: "must be soldered to PCB ground".

---

## 4. DAC — 2× AD9767

Çift port modu (**MODE pin 48 = HIGH**). Interleaved kullanılmıyor: veri
yolunu 160 MHz'e çıkarır, ADC'deki aynı gerekçe.

### 4.1 Dijital (çip başına 32 hat, bank 2)

| DAC pini | FPGA |
|---|---|
| DB0P1…DB13P1 (14…1) | bank 2, port 1 veri |
| DB0P2…DB13P2 (36…23) | bank 2, port 2 veri |
| 17 WRT1, 18 CLK1 | bank 2 |
| 20 WRT2, 19 CLK2 | bank 2 |

### 4.1b İkinci AD9767 — interleaved, bank 1 (KARAR VERİLDİ)

Bank 2'yi birinci DAC tam dolduruyor. İkinci çip için çift portta 32 pin
gerekiyor, boş banka yok.

**Karar: ikinci DAC interleaved modda (MODE = LOW), bank 1'e.**

```
interleaved pin sayısı   14 veri + IQWRT + IQCLK + IQRESET + IQSEL = 18
bank 1 boş pin           ~20
```

Bedeli: tek veri yolu iki kanalı taşıyor, yani yol 160 MHz'de sürülüyor.
ECP5-25 hız derecesi −7'de yapılabilir ama zamanlama sıkı.

> **Bu paragraf değişti.** Eskiden "rev A'da doldurulmuyor, yolları çizili
> duruyor" yazıyordu. Karar "tek seferde en iyisi" olduğu için ikinci
> AD9767 **rev A'da doldurulıyor** — BOM'da iki adet var, şemada (04_dac)
> tam çizili. Dolayısıyla 160 MHz zamanlama riski rev A'yı **etkiliyor**:
> ECP5 −7'de yapılabilir ama marj dar, bringup'ta ölçülecek. Tutmazsa
> rev B'de çift porta geçilir ve bank planı yeniden düzenlenir.

### 4.2 Analog çıkış

```
IOUTA1 (46) ─┬─► rekonstrüksiyon LPF 36 MHz ─► sürücü ─► BNC
IOUTB1 (45) ─┘   diferansiyel, trafo kuplaj, 50 Ω çift sonlandirmali
```
Datasheet: "differential transformer-coupled output, 50 Ω doubly terminated,
IOUTFS = 20 mA".

### 4.3 Referans

| Pin | Bağlantı |
|---|---|
| 43 REFIO | 0.1 µF → ACOM (dahili 1.2 V referans) |
| 44 FSADJ1 | R_set → ACOM, IOUTFS = 32 × (1.2 / R_set) |
| 41 FSADJ2 | aynı |
| 42 GAINCTRL | ACOM (master/slave modu, dahili referans) |
| 37 SLEEP | FPGA bank 0 (veya ACOM) |
| 48 MODE | **+3.3V** (çift port) |

20 mA için R_set = 32 × 1.2 / 0.020 = **1.92 kΩ**.

---

## 4b. SDRAM — W9825G6KH-6I

**W9825G6KH-6I**, LCSC C97572, $7.41, 7181 stok, TSOP-54, endüstriyel.
32 MB (256 Mbit), 16 bit veri, 166 MHz.

Neden var: patlama yakalama. ECP5'in dahili blok RAM'i 1008 kbit = 126 KB,
tam hızda **0.79 ms** eder. Meteor olayı 10 ms ile birkaç saniye arası,
yani dahili RAM olayın sadece ön kenarını yakalıyor.

```
32 MB / 160 MB/s = 200 ms tam hız yakalama     ← 250 kat
```

> **160 MB/s SDRAM'e yazılabiliyor mu — hesap yapıldı, sınırda.**
>
> ```
> 16 bit @ 166 MHz SDR   = 332 MB/s tepe
> refresh + satır açma payı ~%65-75 → 215-250 MB/s sürdürülebilir   ✓
>
> 16 bit @ 100 MHz SDR   = 200 MB/s tepe
> aynı pay              → 130-150 MB/s                              ✗
> ```
>
> Yani SDRAM'i **133 MHz'in altında koşturamayız.** "Rahat olsun" diye
> 100 MHz seçilirse tam hız yakalama tutmaz ve 200 ms rakamı düşer.
> W9825G6KH-**6I** zaten 166 MHz'lik parça, marj var ama yönlendirme
> buna göre yapılacak: CLK seri sonlandırmalı, DQ grubuyla eş boy.
>
> **Ayrıca: tam hızda yakalanan tek kanal.** Dört kanal aynı anda
> 4 × 160 = 640 MB/s eder, hiçbir şekilde olmaz. Dört kanallı yakalama
> için desimasyon şart (kanal başına ~20 MSPS). Meteor/girişim
> yakalamada tek kanal tam hız, yön bulmada dört kanal desimeli.

**DDR3 değil, SDR SDRAM.** Kasten: DDR3 yönlendirmesi (fly-by, ODT,
kalibrasyon) rev A'ya ağır yük. SDR SDRAM tek çip, düz yönlendirme,
LiteX'in `LiteDRAM`'i destekliyor.

| Sinyal | Adet | Banka |
|---|---|---|
| DQ0–15 | 16 | 7 |
| A0–A12 | 13 | 7 (9) + 0 (4) |
| BA0–BA1 | 2 | 0 |
| CLK, CKE, ~CS, ~RAS, ~CAS, ~WE | 6 | 7 |
| DQM0–1 | 2 | 0 |
| **toplam** | **39** | 32 + 7 |

Adres hatlarının bir kısmı banka 0'a taşıyor. Veri yolu (DQ) ve strobe
tek bankada kalıyor — zamanlama açısından önemli olan bu.

CLK hattı eş boy ve mümkünse seri sonlandırmalı. 166 MHz'de yol uzunluğu
farkı setup marjını yiyor.

---

## 5. ETHERNET — 2× RTL8211F

### 5.1 RGMII → FPGA bank 3 (1.8 V)

| PHY pini | FPGA | Yön |
|---|---|---|
| 20 TXC, 18 TXD0, 17 TXD1, 16 TXD2, 15 TXD3, 19 TXCTL | bank 3 | FPGA → PHY |
| 27 RXC, 25 RXD0, 24 RXD1, 23 RXD2, 22 RXD3, 26 RXCTL | bank 3 | PHY → FPGA |

**Uzunluk eşleme:** TXC ile TXD[3:0]/TXCTL grubu ±5 mm içinde; RXC ile
RXD grubu aynı. Gruplar arası eşleme gerekmez.

MDC (13) ve MDIO (14): **iki PHY ortak**, MDIO'ya 1.5 kΩ pull-up (1.8 V).
PHY adresleri strap ile ayrılır (aşağı).

### 5.2 Strap dirençleri — reset anında okunuyor

Pin 22/23/24/25/26/27 hem RGMII verisi hem strap. Reset sırasında
seviyeleri okunuyor, sonra normal işlev.

| Pin | Strap | PHY-1 | PHY-2 |
|---|---|---|---|
| 22 PHYAD0 | PHY adresi bit 0 | pull-down | **pull-up** |
| 27 PHYAD1 | bit 1 | pull-down | pull-down |
| 26 PHYAD2 | bit 2 | pull-down | pull-down |
| 24 TXDLY | TXC'ye 2 ns gecikme | **pull-up** | **pull-up** |
| 25 RXDLY | RXC'ye 2 ns gecikme | **pull-up** | **pull-up** |
| 23 PLLOFF | ALDPS'te PLL kapat | pull-down | pull-down |

TXDLY/RXDLY yukarı çekilerek RGMII'nin 2 ns iç gecikmesi PHY'da üretilir;
FPGA tarafında gecikme yaratmak gerekmez. Adres 0 ve 1 olur.

> Strap dirençleri **1 kΩ**, RGMII sinyal bütünlüğünü bozmayacak kadar
> yüksek, strap'i belirleyecek kadar düşük.

### 5.3 Saat

```
25 MHz kristal (X322525MOB4SI) ─► XTAL_IN (36) / XTAL_OUT (37)
yük kondansatörleri kristal spec'ine göre
```
İki PHY'a **ayrı kristal** (paylaşım denenmesin, PHY'ın kendi osilatörü var).
CLKOUT (35) boşta bırakılır.

### 5.4 MDI ve manyetik

```
MDIP0/N0 (1,2) ┐
MDIP1/N1 (4,5) ├─► HR911105A (dahili manyetik + RJ45)
MDIP2/N2 (6,7) │
MDIP3/N3 (9,10)┘
```
Çift içi eş boy, çiftler arası eşleme gerekmez. Bob Smith sonlandırma
manyetik tarafında.

### 5.5 Regülatör ve referans

| Pin | Bağlantı |
|---|---|
| 39 RSET | datasheet direnci → GND |
| 30 REG_OUT | **2.2 µH veya 4.7 µH bobin** → DVDD10/AVDD10 (anahtarlamalı reg) |
| 32/33/34 LED0-2 | LED + direnç → 3.3 V (ve strap görevi) |
| 12 ~PHYRSTB | FPGA bank 3, ≥10 ms low |
| 31 ~INTB | FPGA bank 3, 3.3 V pull-up |
| 28 DVDD_RG | **+1.8 V** (RGMII I/O gerilimi) |
| 32 CFG_EXT | **pull-up** → harici güç kaynağı modu (DVDD_RG'yi biz veriyoruz) |

> Datasheet uyarısı: REG_OUT bobini ve çıkış kondansatörü seçimi kritik,
> **Y5V seramik kullanma** (s.46-53 dalgalanma ölçümleri).

---

## 6. KONFİGÜRASYON — bank 8

```
W25Q128JVS ─► ECP5 master SPI modu
  CS   ◄── ~CSSPI / PB15A
  CLK  ◄── CCLK
  MOSI ◄── DOUT/~CSO / PB15B
  MISO ──► ~HOLD/DI/BUSY / PB15A grubu
```

| ECP5 | Bağlantı |
|---|---|
| CFG0/1/2 | master SPI modu için datasheet kombinasyonu |
| ~PROGRAMN | 10 kΩ pull-up + buton |
| INITN | 10 kΩ pull-up |
| DONE | 10 kΩ pull-up + LED |
| TCK/TMS/TDI/TDO | **JTAG başlığı** (2.54 mm, 6 pin) |

JTAG başlığı şart — bringup'ta flash boş olacak, JTAG'den yüklenecek.

---

## 7. KONTROL VE MUHTELİF — bank 0/1

| İşlev | Hat | Banka |
|---|---|---|
| ADC SPI (SDIO, SCLK) | 2 | 0 |
| ADC ~CSB ×2 | 2 | 0 |
| ADC SYNC (ortak) | 1 | 0 |
| DAC SLEEP | 1 | 0 |
| PE4312 #1 (Data, Clock, LE) | 3 | 0 |
| PE4312 #2 | 3 | 0 |
| C kartı röle kaydırmalı yazmaç (SER, SRCLK) | 2 | 0 |
| röle RCLK (banka 0'dan taştı) | 1 | **1** |
| T/R kontrol (banka 0'dan taştı) | 4 | **1** |
| **GPS 1PPS girişi** | 1 | 1, saat-yetenekli pin |
| GPS UART (RX/TX) | 2 | 1 |
| VCXO Vc → DAC (SPI: CS, CLK, DIN) | 3 | 1 |
| Durum LED'leri | 4 | 1 |
| Hata ayıklama UART | 2 | 1 |
| Harici 10 MHz ref girişi (opsiyonel) | 1 | 1, saat-yetenekli |

**GPS 1PPS saat-yetenekli pine bağlanmalı** — kenarı doğrudan sayaçla
yakalanacak, yumuşak I/O'da jitter olur.

---

## 8. KART ARASI — A ↔ C

| Sinyal | Adet | Not |
|---|---|---|
| RF anten girişi | 4 | koaks kuyruk ya da SMA kart-arası |
| RF veriş çıkışı | 2 | aynı |
| Röle kontrol (kaydırmalı yazmaç) | 3 | + güç ve toprak |
| T/R kontrol | 4 | port başına |
| PE4312 seri hat | 6 | iki zayıflatıcı |
| +3.3 V, +12 V, GND | 3 | röle bobinleri 12 V |

Konnektör: RF için koaks kuyruk (kart-arası SMA sinyal bütünlüğü için
daha iyi ama pahalı), dijital için 2.54 mm başlık.

---

## 9. GİRİŞ KORUMASI VE BESLEME

```
XT60 ─► P-MOSFET ters polarite ─► TVS (SMBJ20A) ─► sigorta 2 A ─► TPS62130
```
- P-MOSFET ters polarite: düşük düşüş, akü ucu ters takılınca kurtarır
- TVS 20 V: akü hattındaki geçici aşırı gerilim
- Sigorta 2 A: 2.8 W @ 9 V = 310 mA, 2 A bol marj

---

## 10. AÇIK KARARLAR — şema çizilmeden kapanacak

1. ~~İkinci AD9767'nin pinleri~~ **KAPANDI** — interleaved, bank 1. §4.1b
2. ~~Saat tamponu parçası~~ **KAPANDI** — ADCLK846. §2
2b. ~~ADCLK846 eklemeli jitter~~ **KAPANDI** — Rev.C Tablo 1:
   54 fs (12 kHz–20 MHz), 86 fs (10 Hz–100 MHz), 150 fs geniş bant.
   VCXO ile toplam **81 fs dar bant / 162 fs geniş bant.**
   SNR tavanı: 30 MHz'de 96 dB (ADC'nin kendi gürültüsü sınır),
   500 MHz'de 66–72 dB (**saat jitter'ı sınırlıyor**). UHF alt-örneklemede
   ~11 bit efektif; kabul edildi. Daha iyisi LMK04828 sınıfı, on kat pahalı.
2c. ~~DAC saati LVDS→CMOS çevirici~~ **KAPANDI** — `SN65LVDS2DBVR`,
   LCSC C38204, $0.36, 1244 stok, SOT-23-5. İki adet, DAC başına bir.
   ADCLK846'nın CMOS modu kullanılamadı: çıkışı 1.8 V CMOS olurdu,
   AD9767'nin lojik-1 eşiği 2.1 V.
2d. **ADCLK846 VS = 1.8 V, 3.3 V değil.** Veri sayfası başlığı. Güç
   ağacında saat bölümü baştan 3.3 V varsayılmıştı; tampona kendi
   `+1V8_CLK` rayı eklendi (01_power U9, ADP150-1.8, +2.5 V'tan
   besleniyor). Bu ray olmadan tampon hiç çalışmaz.
2e. **VCXO → tampon seviye uyumu.** VCXO çıkışı 3.3 V LVCMOS, ADCLK846
   girişinin azami seviyesi **1.8 V p-p**: "Larger voltage swings can turn
   on the protection diodes and can degrade jitter performance."
   Doğrudan bağlansaydı koruma diyotları iletime girer, aletin manşet
   özelliği ilk bağlantıda ölürdü. 220R/100R bölücü (1.03 V p-p) +
   AC kuplaj + VREF (VS/2) bias eklendi.
3. **ECP5 saat-yetenekli pinler.** Hangi banka hangi PLL girişine bağlı —
   Lattice pinout dosyasından çıkarılacak. DCOA/DCOB ve 80 MHz saat oraya
   gidecek.
4. **PHY REG_OUT bobini** değeri ve kondansatör tipi (datasheet s.46-53).
5. **AD9251 SYNC kullanımı** — iki çipi gerçekten hizalıyor mu, yoksa
   ek prosedür mü gerekiyor? Datasheet "Channel/Chip Synchronization"
   bölümü okunacak.
6. **Kart ölçüsü ve kutu** — layout başlamadan kutu seçilecek.

### Şema çizilirken açılan yeni maddeler

7. **ADT1-1WT+ pinout.** Sembol CD542 gövdesinin alışıldık dizilimiyle
   çizildi, veri sayfası elde yok. Yanlışsa RX ön ucunun tamamı ölü.
   Kart basılmadan pin 1/3/4/5/6 tek tek doğrulanacak. (03_adc)
8. **MAGJACK PARÇASI DEĞİŞTİ — HR911105A gigabit değilmiş.** Veri sayfası
   kapağı: "for 10/100Base-T NIC Applications". Şemasında yalnızca **iki**
   çift sargı var (TD, RD); gigabit dört çift ister. O parçayla iki GbE
   portu 100 Mbit'e düşerdi — aletin veri borusu on kat daralır, dört
   kanal IQ akışı imkânsız olurdu. BOM'a alınıp basılsaydı kart çöpe
   gitmezdi ama Ethernet'in tamamı yeniden tasarlanırdı.
   **Yeni parça: HR911130A**, LCSC C54408, $1.58, 6005 stok.
   Hâlâ açık: 130A'nın pinout'u ve ayak izi doğrulanmadı (KiCad'de
   sadece 105A'nın ayak izi var, gövde aynı mı bilinmiyor). Bacaklar
   şemada numarayla duruyor. **HR911130A veri sayfası gerekiyor.**
   (06_ethernet)
9. **W9825G6KH pin dizilimi** JEDEC 54 bacaklı x16 SDRAM standardından
   girildi. Özellikle 40. bacak (bazı üreticilerde NC, bazılarında ikinci
   CKE) doğrulanacak. (05_sdram)
10. **VCXO Vc DAC parçası** seçilmedi. 16 bit, düşük gürültülü, SPI;
    beslemesi +3.3V_CLK. Şemada başlık olarak duruyor. (08_control)
11. **Harici 10 MHz'in doğrudan FPGA girişine bağlanması.** ECP5 girişinin
    10 MHz sinüsü (>0.5 Vpp) yakalayacağı varsayıldı, komparatör konmadı.
    Bringup'ta ölçülecek. (08_control)
12. **Harici 10 MHz girişinde DC yolu yok — DEVRE HATASI.** Çizdiğim
    ağ: SMA → 50R → 100nF seri → FPGA. Kondansatörden sonra girişin
    hiçbir DC referansı yok, bacak havada kalıyor. Üstelik DC bias
    eklense bile 3.3 V LVCMOS eşikleri (VIH ~2.0 V, VIL ~0.8 V) 0.5 Vpp
    sinüsle aşılmıyor. İki çözüm:
    - **(a) diferansiyel giriş:** sinyal P bacağına, orta-gerilim bias
      N bacağına; ECP5 diferansiyel alıcısı küçük sinyali yakalar.
      Bedeli **bir pin daha** — banka 1 zaten 32/32, yer açmak lazım.
    - **(b) komparatör:** TLV3501 / LMV7219 sınıfı, SOT-23-5, ~$1.
      Pin harcamıyor, BOM'a bir satır ekliyor.
    Seçim yapılmadan bu giriş çalışmaz. Şimdilik (b) öneriliyor:
    banka 1'de yer yok ve harici referans zaten opsiyonel bir özellik,
    bir dolarlık parça pin planını bozmaktan ucuz.

14. **ADT1-1WT+ 75 Ω'luk bir parça.** Veri sayfası kapağı: "RF
    Transformer 75Ω 0.4 to 800 MHz". Empedans oranı 1:1 olduğu için
    50 Ω sistemde de dönüşüm yapıyor, ama parça 75 Ω için
    karakterize edilmiş — 50 Ω'da dönüş kaybı bozuluyor (|Γ| = 0.2,
    ~0.18 dB uyumsuzluk kaybı). ADC girişini yüksek empedanslı ve
    49.9 Ω'la sonlandırılmış sürdüğümüz için etkisi sınırlı, ama
    **TX tarafında SMA gerçek 50 Ω yüke bakıyor**, orada daha önemli.
    Mini-Circuits'in 50 Ω 1:1 muadilleriyle (ADT1-1+, TC1-1-13M+
    sınıfı) frekans aralığı ve fiyat karşılaştırılacak. Şu anki BOM
    satırı kalıyor; değişirse aynı CD542 gövdesi kullanılabiliyorsa
    kart değişmez.

13. **CFG[2:0] kombinasyonu** — Master SPI için Lattice sysCONFIG (TN1260)
    tablosundan. Her bacakta hem yukarı hem aşağı direnç ayak izi var,
    biri doldurulacak. **Değer girilmeden kart basılmaz.** (07_fpga_power)

---

## 11. ŞEMA DURUMU (kicad/A_main)

| Sayfa | Durum | ERC |
|---|---|---|
| 01_power | tam | temiz |
| 02_clock | **boş** — ADCLK846 veri sayfası bekliyor | — |
| 03_adc | tam | temiz |
| 04_dac | tam | temiz |
| 05_sdram | tam | temiz |
| 06_ethernet | tam (magjack eşlemesi hariç) | temiz |
| 07_fpga_power | tam | temiz |
| 08_control | tam | temiz |

Projede hata (error) kalmadı. Kalan uyarılar tek tek yukarıdaki açık
maddelere karşılık geliyor: 4 ADC saat hattı (02_clock), 24 magjack
bacağı + 16 MDI (§10.8), 4 zayıflatıcı RF ucu (C kartında, kasıtlı),
VCXO_VC (§10.10).

Üretim: `cd kicad/A_main && ./build.sh` — iskeleti kurar, sekiz sayfayı
üretir, kanonikleştirir, ERC koşar. `./build.sh pdf` PDF ve SVG de çıkarır.

## 11. DRC status, board A

Clean except two categories, both understood:

| Category | Count | Status |
|---|---|---|
| `unconnected_items` | 499 | Expected — board is placed, not routed |
| `copper_edge_clearance` | 49 | **By design** — edge-mount connector pads must touch the board edge |
| everything else | 0 | Courtyard overlaps, clearance, mask bridges, shorts: none |

The 49 edge-clearance violations belong to the SMA connectors (J20-J23,
J30-J33, J61), the magjacks (J40, J41) and the interboard headers. Their
pads reach the board outline because that is what an edge-mount part is.

A `kenar_montaj` PCB group is created by `ayir.py` and `dogrudan_sdr_A.kicad_dru`
grants it `edge_clearance (min 0mm)`. KiCad applies this to the footprint
bodies but **not** to their pads — `memberOfGroup()` does not resolve a pad
to its parent footprint's group. The remaining 49 must therefore be reviewed
and excluded individually in the GUI before fabrication, or the rule rewritten
against a drawn rule area once the outline is final.

A blanket exemption was deliberately not used: it would also hide a genuine
edge violation in the middle of the board.

### Verified placement geometry

| Constraint | Result |
|---|---|
| ADCLK846 to ADC-1 / ADC-2 | 30.0 mm / 30.0 mm, delta **0.00 mm** |
| RX chain SMA to transformer, all 4 | 29.5 mm, identical |
| RX chain transformer to ADC, all 4 | 36.2 mm, identical |
| Courtyard overlaps | 0 |
| Connectors on board edge | 17 of 19 (J1 power, J10 JTAG interior by choice) |
| FPGA decoupling | back side, 2.5 mm grid under the BGA |
| Mounting holes | H1-H4, four corners, 5 mm inset |

## 12. FPGA ball assignment is derived from geometry

The sheet generators used to map bank pins to bus signals alphabetically:

    io7 = sorted(n for n, nm in B7.items() if nm.startswith("PL"))
    for p, net in zip(io7, nets7): ...

"A10, A11, A12, B2, B3..." carries no information about where a ball
physically sits. SDRAM DQ0 could land on a ball at the far side of the
package, forcing its track to cut diagonally across the whole bundle.
Every such cut costs a via, a layer change, an impedance discontinuity
and extra delay, and it makes length matching impractical.

An ECP5 user I/O is interchangeable within its bank, so this mapping is
ours to choose. `ball_atama.py` reads the placed board, projects both
ends of each bus onto the axis perpendicular to the bundle, sorts both,
and pairs them in order. A monotonic mapping cannot cross.

Two constraints are preserved: the bank never changes (same I/O voltage,
same driver delay, same temperature behaviour), and differential and
clock-capable pins are left alone.

The flow is two-pass — generate, place, compute, regenerate — and
converges in one iteration because placement coordinates come from the
floorplan, not from the netlist.

### Result, board A

| Bundle | Lines | Crossings | Mean length | Spread |
|---|---|---|---|---|
| ADC1 | 16 | 0 | 59.6 mm | 7.5 mm |
| ADC2 | 16 | 0 | 91.2 mm | 5.1 mm |
| SDRAM bank 7 | 25 | 0 | 61.3 mm | 17.7 mm |
| SDRAM bank 0 | 7 | 0 | 54.4 mm | 6.4 mm |
| DAC1 port 1 | 14 | 0 | 86.5 mm | 8.7 mm |
| DAC1 port 2 | 14 | 0 | 93.2 mm | 8.2 mm |
| DAC2 | 14 | 0 | 63.3 mm | 8.1 mm |
| PHY1 RGMII | 12 | 0 | 69.2 mm | 6.4 mm |
| PHY2 RGMII | 12 | 0 | 92.5 mm | 1.5 mm |
| **Total** | **130** | **0** | | |

Before: 116 crossings. The spread column is the meander budget for the
length-matching pass.

SDRAM is measured as two bundles because its address lines overflow into
bank 0. They are two physically separate corridors on opposite faces of
the FPGA; measuring them as one list counted them as crossing each other
when they never share a channel.

## 13. Clocks were on pins with no clock capability

Eight of the nine clock nets landed on ordinary I/O balls. Only
SD_CLK_FPGA was on a PCLK pin, and only by chance -- the ball assignment
was alphabetical, so nothing steered a clock towards a clock pin.

A clock on a general I/O does not enter the clock tree directly. It goes
through general routing, collects skew and jitter, and at 125 MHz RGMII
receive it does not close timing. This would not have shown up until
gateware bring-up, on fabricated boards.

The ECP5 pin capability table is extracted from prjtrellis-db
(`ECP5/LFE5U-25F/iodb.json`, YosysHQ, open source) into `ecp5_saat.py`
so the build needs no network. CABGA256 has 36 clock-capable balls:
PCLKT/PCLKC are primary clock inputs, GR_PCLK reach the clock tree
through general routing and are the second choice.

`ball_atama.py` now places clocks before anything else, then lets the
geometric sort fill in around them.

| Net | Was | Now | Function |
|---|---|---|---|
| ADC1_DCO | N4 | M1 | PCLKT6_0 |
| ADC2_DCO | P1 | M2 | PCLKC6_0 |
| PHY1_RXC | K12 | M16 | PCLKT3_0 |
| PHY1_TXC | M11 | L16 | PCLKT3_1 |
| PHY2_RXC | N16 | M15 | PCLKC3_0 |
| PHY2_TXC | P13 | L15 | PCLKC3_1 |
| REF10_IN | D9 | B8 | PCLKC1_0 |
| SD_CLK_FPGA | K2 | J1 | PCLKT7_1 |

GPS_1PPS is deliberately left on an ordinary pin. At 1 Hz it never
enters the clock tree; it is captured against the system clock, and
spending a PCLK on it would waste one.

Clocks are assigned as a group rather than one at a time. Assigning them
in sequence let one clock take another's pin -- PHY1_RXC moved onto
PHY2_RXC's ball and ERC reported three violations. Every (clock, pin)
pair is now ranked by distance from the clock's own peripheral pad and
handed out nearest-first, each clock and each pin used once. Ranking by
distance also matters for crossings: taking the first free PCLK
satisfied the constraint but ran ADC1's data clock through the middle of
its own bundle, crossing five data lines.

Bundle crossings went from 0 to 6 as a result, all of them in the four
bundles that carry a clock. That is the right trade -- a clock pinned to
PCLK is worth more than a via on one line -- and the other five bundles
are still at zero.

## 14. W9825G6KH pinout verified against the datasheet

Closed. The symbol was built from the JEDEC 54-pin x16 layout with a
note that pin 40 differs between vendors -- No Connect on some, a second
CKE on others -- and had to be checked before fabrication.

Checked against Winbond's own datasheet, revision A04
(<https://www.winbond.com/resource-files/w9825g6kh_a04.pdf>). All 54 pins
were extracted from the pin table and compared with the symbol
mechanically rather than by eye. Every pin matches. Pin 40 is **NC**.

The only difference the comparison reported was pin 22, where the
datasheet writes A10/AP and the symbol writes A10. Same pin; AP is the
auto-precharge role the pin takes during a read or write command.

Confirmed in passing: 15 LDQM, 16 WE, 17 CAS, 18 RAS, 19 CS, 20 BS0,
21 BS1, 35 A11, 36 A12, 37 CKE, 38 CLK, 39 UDQM, 41 VSS.

Remaining open items are the HR911130A footprint against a 1:1 print,
and the AD8318 TADJ resistor value, which needs a temperature sweep at
bring-up rather than a document.
