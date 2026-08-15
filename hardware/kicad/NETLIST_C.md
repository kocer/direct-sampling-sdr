# C KARTI — RF ön uç şartnamesi

A kartı bitti (`kicad/A_main`, 264 bileşen, ERC temiz). Bu kart onun
anten tarafı: koruma, T/R, zayıflatıcı, bant filtresi bankası.

---

## 0. Neden dört özdeş zincir

Bu aletin ayırt edici özelliği dört faz-uyumlu kanal. Faz uyumu ADC'de
başlamıyor, **antende** başlıyor: dört yolun genlik ve faz cevabı aynı
değilse gürültü iptali, yön bulma ve ışın şekillendirme çalışmaz.

Bu yüzden dört RX zinciri **birebir aynı** olmak zorunda — aynı röle,
aynı filtre, aynı yol uzunluğu. "Bir kanala filtre koyalım, ötekiler
düz geçsin" kalıcı faz farkı yaratır ve kalibrasyonla tam kapanmaz
(bant kenarlarında faz eğimi frekansla değişir).

**Sonuç: ne yapılırsa dört kere yapılıyor.** Aşağıdaki adetler hep ×4.

---

## 1. Röle seçimi — KİLİTLENEN röle şart

İlk hesap kartı düşürdü:

```
normal röle, 12 V bobin, ~30 mA
dört kanal x bir aktif bant = 4 role surekli cekili
4 x 12 V x 30 mA = 1.44 W     A kartinin toplam butcesi 2.8 W
```

Sadece filtre seçimi güç bütçesinin yarısını yiyordu. Saha modunda
aküyle çalışacak bir alette kabul edilemez.

**Kilitlenen (latching) röle**: sadece anahtarlama anında akım çeker,
sonra sıfır. Bir HF filtre bankasında zaten standart çözüm.

| Parça | LCSC | Stok | Fiyat | Not |
|---|---|---|---|---|
| **G6KU-2F-Y-TR DC5** | C2153173 | 7613 | $0.84 | Omron, 2 Form C, kilitlenen, RF için (50 Ω, 3 GHz'e kadar) |
| TQ2SA-L2-5V-Z | C2684450 | 3102 | $1.88 | Panasonic, çift bobin, alternatif |
| AGQ200A12Z | C2684439 | 7454 | $0.70 | Panasonic, ucuz alternatif |

**G6KU seçildi.** G6K ailesi RF sinyal rölesi olarak zaten standart;
U harfi kilitlenen sürüm. 2 Form C, yani **tek röle bir filtre
bölümünün hem girişini hem çıkışını** anahtarlıyor.

Bobin 5 V → C kartında bir +5 V rayı gerekiyor. Kilitlenen olduğu için
akım sadece darbe süresince (~20 ms) akıyor; küçük bir buck yeter.

---

## 2. Bant planı — KARAR BEKLİYOR

Filtre bankası kartın boyunu ve maliyetini belirleyen tek şey.

| Seçenek | Bant | Röle (×4 kanal) | Filtre parçası | Röle maliyeti |
|---|---|---|---|---|
| **A** dar | 5 | 20 | ~160 | $17 |
| **B** tam | 7 | 28 | ~224 | $24 |
| **C** geniş | 9 | 36 | ~288 | $30 |

Seçenek **B** (7 pozisyon) öneriliyor:

```
1  160 m      1.8 - 2.0 MHz
2  80/60 m    3.5 - 5.4
3  40/30 m    7.0 - 10.2
4  20/17 m    14.0 - 18.2
5  15/12/10 m 21.0 - 29.7
6  6 m        50 - 54
7  BYPASS     doğrudan geçiş — VHF/UHF alt-örnekleme ve genel tarama
```

7. pozisyon şart: alet HF telsizi değil, 1–500 MHz alıcısı. Bant
filtresi bandın dışını öldürür; uydu, radiosonde ve UHF deneyleri
bypass'tan geçecek.

Maliyet farkı küçük (5 ↔ 7 arası $7 ve ~64 pasif parça). Asıl bedel
**kart alanı**: bölüm başına ~18 × 12 mm, 28 bölüm ≈ 6000 mm² sadece
filtreler. Kartı 200 × 150 mm bandına oturtuyor. 2 katman olduğu için
maliyeti düşük.

> **Bu kararı vermeden filtre çizilmez.** Bant sayısı kartın ölçüsünü,
> ölçü de kutuyu belirliyor.

---

## 3. Kanal başına zincir

```
anten SMA
  │
  ├─ gaz deşarj tüpü → toprak            yıldırım / statik
  ├─ SMBJ TVS                            hızlı geçici
  │
  T/R rölesi (G6KU)  ──TX──► TX yolu (A kartından IOUT)
  │
  RX
  │
  ├─ PIN limitleyici (BAV99 sırt sırta)  yakındaki vericiye karşı
  │
  bant filtresi bankası (7 pozisyon, G6KU ×7)
  │
  PE4312 zayıflatıcı 0-31.5 dB
  │
  A kartına (koaks kuyruk)
```

### Koruma katmanları — neden üç tane

Okul istasyonunda kendi vericimiz aynı çatıda. Üç ayrı tehdit:

1. **Yıldırım / statik** — gaz deşarj tüpü, kilovoltları toprağa
2. **Hızlı geçici** — TVS, nanosaniye mertebesinde kenetler
3. **Yakın verici** — PIN/diyot limitleyici, sürekli RF gücü sınırlar

Üçü farklı zaman ölçeğinde çalışıyor; biri diğerinin yerine geçmiyor.
Gaz tüpü yavaş (µs), TVS hızlı ama sürekli güç taşımaz, diyot
limitleyici sürekli çalışır ama kilovolt görürse ölür.

---

## 4. Zayıflatıcı — açılış durumu kritik

PE4312 ×2 A kartından buraya taşındı (RF zincirinin parçası).

> **Dört kanal için dört zayıflatıcı gerekiyor**, iki değil. Faz uyumu
> zincirlerin özdeş olmasını şart koşuyor. BOM'da iki vardı; bu şartname
> dörde çıkarıyor. Ek maliyet 2 × $1.45 = $2.90, ve A kartında iki
> kontrol hattı seti daha gerekiyor — **banka 0 dolu, yer yok.**
>
> Çözüm: dört zayıflatıcı **aynı seri hattı** paylaşsın, LE hatları
> ayrı olsun. Data+Clock ortak (2 hat) + 4 LE = 6 hat. Şu an ayrılan
> hat sayısı da 6. **A kartı değişmiyor**, sadece anlamı değişiyor.
> C kartı şeması bunu böyle bağlayacak.

Açılış durumu (veri sayfası s.6): seri modda bile C0.5–C16 bacaklarındaki
seviye belirliyor. Altısı da 10k ile yukarı → **31.5 dB**, alıcı en sağır
halinde açılıyor. Boş bırakılsa zayıflatma tanımsız olurdu.

---

## 5. Röle sürücü

28 filtre + 4 T/R = **32 kilitlenen röle**. Tek bobinli kilitlenen röle
her iki yön için de darbe ister → sürücü iki yönlü olmalı.

| Yaklaşım | Parça | Hat | Not |
|---|---|---|---|
| kaydırmalı yazmaç + sürücü | TPIC6B595 ×5 | 3 | 40 çıkış, açık drenaj, 150 mA |
| H köprü dizisi | pahalı | — | tek bobinli röleyi iki yönde sürer |

Tek bobinli G6KU için **iki TPIC6B595 seti** (biri "set", biri "reset")
ya da yarım köprü. En basit: her röleye iki açık drenaj çıkışı
(set ve reset), yani 64 çıkış → **TPIC6B595 ×8**, $0.68 × 8 = $5.44.

3 hat (SER, SRCLK, RCLK) A kartından geliyor, zaten ayrılmış.

---

## 6. Güç

```
VIN_PROT (9-18 V, A kartından)
  └─► buck ─► +5 V   role bobinleri (darbeli)
+3V3 (A kartından)   PE4312 VDD, kaydırmalı yazmaç lojik
```

Röleler kilitlenen olduğu için sürekli tüketim ~0. Darbe sırasında
32 × 100 mA olası ama **hepsi aynı anda anahtarlanmaz** — firmware
sırayla darbeler. 5 V rayı 200 mA yeterli.

---

## 7. Kart arası

A kartındaki iki başlık (`J63` 2×10, `J65` 1×6) + RF için koaks kuyruk.

| Sinyal | Adet | Nerede |
|---|---|---|
| RLY_SER, RLY_SRCLK, RLY_RCLK | 3 | J63 |
| TR1..TR4 | 4 | J63 |
| ATT_DATA, ATT_CLK (ortak) | 2 | J63/J65 |
| ATT_LE ×4 | 4 | J63/J65 |
| VIN_PROT, +3V3, GND | 3 | ikisinde de |
| RF RX ×4, RF TX ×4 | 8 | **koaks kuyruk**, başlık DEĞİL |

Dijital hatların yanında toprak var (J63'te her tek pin sinyal, çift pin
toprak) — röleler 12 V anahtarlıyor ve kenarları sert, yanındaki RF'e
kuplaj yapmasın.

---

## 8. Açık kararlar

1. **Bant sayısı** (§2). Kartın ölçüsünü belirliyor. 7 öneriliyor.
2. **Kutu.** A ve C aynı kutuya mı, ayrı mı? Layout ikisi için de
   kutudan sonra başlıyor.
3. **Filtre topolojisi ve Q.** JLCPCB'de yüksek Q'lu RF bobini yok;
   jenerik bobinle 5. derece Chebyshev'in kenar dikliği ve ekleme
   kaybı hesaplanacak. Yetmezse bobinler ayrı getirtilip elde
   lehimlenecek — kartın geri kalanı yine dizdirilebilir.
4. **UHF T/R rölesi.** G6K 3 GHz'e kadar spec'li, sorun yok. Ama
   6 m üstü için filtre bankası bypass'ta kalıyor; UHF ön seçici
   isteniyorsa ayrı bir pozisyon gerekir.
5. **Gaz deşarj tüpü parçası** seçilmedi.
