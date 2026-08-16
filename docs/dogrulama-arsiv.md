> **ARSIV — 15 Agustos 2026 anlik goruntusu.**
>
> Bu belge ARDC paketinden CIKARILDI ve arsiv olarak burada duruyor.
> Icindeki sayilar yazildigi andaki tasarima ait ve o tarihten sonra
> iki ayri yeniden tasarim oldu (katlanma bastirmasi ve tolerans
> merkezleme), ustune formal dogrulama ve CDC duzeltmeleri geldi.
>
> GUNCEL DOGRULAMA KANITI: `ardc/VERIFICATION.md`. O dosya elle
> yazilmiyor — `ardc/topla.py` araclari kosturup ciktilarini yakalayarak
> uretiyor, yani eskiyemez. Bu belgenin eskimesi de zaten o araci
> yazmanin sebebi oldu.
>
> Burada tutulmasinin sebebi: hangi hatanin NASIL bulundugunu anlatiyor
> ve o anlatim hala degerli.

# Doğrulama — ne koşturuldu, ne bulundu, ne düzeltildi

Bu turda üç kartın **şeması** baştan sona denetlendi. Aşağıdaki her
sayı bir komuttan çıkıyor; komut satırı yanında yazılı. Bütün koşular
`kicad/` dizininden ve `export PYTHONHASHSEED=0` ile yapıldı
(yerleşim tekrarlanabilirliği bunu şart koşuyor).

**Kapsam sınırı, baştan:** bu tur **şema tarafıdır**. Kartların
`.kicad_pcb` dosyaları yeniden kurulmadı, çünkü üç otomatik
yönlendirici koşuyordu ve kartı netlistten yeniden kurmak koşan işi
geçersiz kılıyor. Aşağıda "karttan okundu" diyen ölçümler
düzeltmelerden ÖNCEKİ karta aittir; şema düzeltmeleri karta ancak
`yap.sh` zinciri yeniden koşturulunca geçer.

---

## 1. Şema üretimi ve ERC

```
cd A_main && ./build.sh      # aynısı C_rf ve D_pa için
```

| Kart | ERC ihlali |
|---|---|
| A | **0** |
| C | **0** |
| D | **0** |

Ara durumlarda ihlal çıktı ve hiçbiri gizlenmedi; hepsi giderildi.
Çıkanlar ve sebepleri §3'te (DRV8833 ve LM358 düzeltmelerinde
etiket çakışması yüzünden geçici olarak 17 ve 3 ihlal oluştu).

**ERC'nin gördüğü hata sınıfı dardır.** Aşağıdaki bulguların
hiçbirini ERC yakalamadı; hepsi "Found 0 violations" verirken oradaydı.

---

## 2. Mevcut denetim araçları

| Araç | Komut | A | C | D | Sonuç |
|---|---|---|---|---|---|
| Ağsız ped | `python3 ped_denetim.py` | 0 | 0 | 0 | temiz — regresyon yok |
| Referans çakışması | `python3 ref_denetim.py` | 0 | **1 → 0** | 0 | biri bulundu ve düzeltildi, §4 |
| Kondansatör temini | `python3 kondansator_denetim.py` | 6 uyarı | 2 uyarı | 2 uyarı | **0 parça temin edilemez** |
| Güç yolu genişliği | `python3 guc_yolu.py` | 2 "ince" | 0 | 0 | ikisi de yanlış alarm, §6 |

`ped_denetim` üç kartta da sıfır: önceki turda bulunan 31 ağsız ped
düzeltmesi yerinde duruyor.

`kondansator_denetim`'in 10 uyarısının hepsi "sınıra yakın — tek
kaynak/pahalı olabilir" türünden; "PAKETTE BU KAPASITE BU GERİLİMDE
YOK" diyen tek satır yok.

---

## 3. Yeni denetim: sembol pin ADI ↔ bağlı olduğu AĞ

Mevcut araçlar ped **numarasına** bakıyordu: "bu pedin ağı var mı".
Pin **yanlış yere** bağlıysa hiçbiri konuşmuyor — pedin ağı vardır,
netlist tutarlıdır, ERC susar, DRC susar.

İki yeni araç yazıldı:

- **`kicad/sema_denetim.py`** — sembol kütüphanesinden pin adını,
  karttan o pin numarasının ağını okuyup eşleştiriyor. Toprak adlı pin
  toprakta mı, besleme adlı pin beslemede mi, NC pini bağlı mı, her
  besleme rayının yakınında ayırma kondansatörü var mı.
- **`kicad/netlist_denetim.py`** — `kicad-cli sch export netlist`
  çıktısından çalışıyor, yani **kart gerekmiyor**. Veri sayfasından
  doğrulanmış 22 pin-ağ beklentisini kilitliyor.

### 3.1 Aracın kendi yanlış alarmları önce ayıklandı

İlk koşu 43 bulgu verdi. İkisi aracın hatasıydı:

- 19 bulgu: KiCad bağlanmamış pede `unconnected-(U4-NC-Pad4)` adını
  veriyor. Bu bir ağ değil, ağ **yokluğunun** adı. Araç bunları "NC
  pini bir ağa bağlı" sayıyordu.
- 8 bulgu: RTL8211F'in iç regülatörünün ürettiği `PHY1_1V0` rayı ad
  kalıbına uymuyordu. Ray artık **yapısından** tanınıyor: üzerinde
  toprağa giden en az iki kondansatör varsa besleme rayıdır.

Ayrıca araç, türetilmiş (`extends`) sembolleri sessizce atlıyordu —
**yedi entegre hiç denetlenmeden geçmişti** (MCP4922 ×2, LM358 ×2,
W25Q128JVS, TPS7A20, MCP9700). `schlib.pins()` kullanılarak kapatıldı.

Kalan 18 bulgunun hepsi tek tek izlendi.

### 3.2 Veri sayfasından doğrulanan ve DÜZELTİLEN hatalar

| # | Kart | Ne | Kaynak | Sonucu ne olurdu |
|---|---|---|---|---|
| 1 | A | **U62 TLV3501 komparatörü sürekli KAPALIYDI.** SHDN (pin 6) +3V3'e bağlıydı. | TI SBOS321E §7.4.1: *"When the shutdown pin is high, the device draws approximately 2 µA, and the output goes to high impedance. When the shutdown pin is low, the TLV3501 is active."* | Harici 10 MHz referans girişi (GPSDO/etalon disiplini) hiç çalışmaz. Koddaki yorum polariteyi ters yazmıştı. **GND'ye alındı.** |
| 2 | C | **16 DRV8833'ün VCP ve VINT bacakları boştaydı** (`s.nc()` ile "kullanılmıyor" işaretli). | TI SLVSAR1: VM–VCP arasına 0.01 µF/16 V, VINT'ten toprağa 2.2 µF/6.3 V **zorunlu**. VINT bir besleme girişi değil, iç regülatör çıkışı. | Şarj pompası yüksek yan FET'i süremez → 28 filtre rölesinin hiçbiri kilitlenmez. **32 kondansatör eklendi.** |
| 3 | A | **Yedi regülatörün (U3 + U4…U9) tek bir kondansatörü yoktu.** En yakın +3V3 kapasitesi 18–37 mm, çıkış raylarınınki 40–94 mm ötede. | ADP150 Rev.G "Capacitor Selection": giriş ve çıkışa 1 µF X5R **gerekli**; TPS7A20 (SBVS340) aynı. | Kondansatörsüz LDO çarpık çalışmaz, **salınır**; salınım beslediği rayın (ADC AVDD, VCXO, FPGA VCCAUX) gürültü tabanına biner. **14 kondansatör eklendi** (C10…C23). |
| 4 | D | **Dört INA240'ın +5V ayırması yoktu** (en yakın 21–50 mm). | TI SBOS662C "Power-Supply Recommendations": *"a 0.1-µF capacitor placed as closely as possible to the supply and ground pins"* | Bias servosunun ölçüm kolu; gürültülü okuma doğrudan geçit gerilimine ve dinlenme akımına gidiyor. **4 × 100 nF eklendi.** |
| 5 | D | **İki LM358'in +12V ayırması yoktu.** Ölçüldü: en yakın kondansatör U41 için **227.1 mm**, U42 için 207.9 mm — kart 275×185 mm, yani öbür uçta. | genel | Bu opamplar final MOSFET'in geçidini sürüyor. A sınıfı katta termal kaçışın başlangıç noktası. **2 × 100 nF eklendi.** |
| 6 | D | **U10 PE4312'nin ayırması yoktu** (C kartındaki dördünün her birinde iki tane var, D'deki tek çip atlanmış). | — | **2 × 100 nF eklendi.** |
| 7 | D | **U55 MCP9700 sıcaklık sensörünün ayırması yoktu.** | DS20001942 "Layout Considerations": VDD–VSS arasına 0.1 µF | Bu sensör PA flanş sıcaklığını ölçüyor ve aşırı sıcaklık kesmesini tetikliyor. **1 × 100 nF eklendi.** |
| 8 | C+D | **Beş PE4312'nin 3 numaralı bacağında seri 10 kΩ yoktu.** | pSemi DOC-81482 s.5: *"A 10-kΩ resistor on the inputs to pin 1 and 3 eliminates the package resonance between the RF input pin and the two digital inputs. The specified attenuation error versus frequency performance depends upon this condition."* | Bu direnç olmadan veri sayfasındaki zayıflatma doğruluğu geçerli değil. Pin 1'de açılış çekme direnci zaten aynı işi görüyordu. **5 direnç eklendi.** |
| 9 | A | **Kristalin yük kapasitesi BOM'da yazmıyordu.** Değer sadece "25MHz" idi. | LCSC C9006 = YXC X322525MOB4SI, CL = **12 pF** | Aynı gövdede 20 pF'lik bir kristal alınırsa salınım ~24 ppm yukarıda koşar; 802.3'ün ±50 ppm bütçesi kristal toleransıyla birlikte taşar ve Ethernet "bazen link kuruyor" diye arızalanır. Değer **"25MHz CL12pF"** yapıldı, BOM eşlemesi güncellendi. |

Yük kapasitesi hesabı, kayıt için: iki bacakta 18 pF →
CL = 18·18/(18+18) + Cstray = 9 + ~3 = **12 pF**, seçilen kristalle
tutuyor. Cstray 3 pF varsayımı ilk prototipte 25 MHz ölçülerek
doğrulanmalı (`URETIM` açık maddesi).

### 3.3 Ayak izi paketi denetimi

Koordinatörün istediği gözle her entegrenin paketi kontrol edildi.
Ped sayısı tutan ama paketi yanlış olan iki şey bulundu:

| Parça | Bulunan | Veri sayfası | Yapılan |
|---|---|---|---|
| **PE4312** (C ×4, D ×1) | açık ped **2.6 × 2.6 mm** | DOC-81482 Şekil 26: açık ped **2.15 ± 0.05 mm** kare, önerilen lehim alanı 2.20 mm | `TQFN-20-1EP_4x4mm_P0.5mm_EP2.1x2.1mm`. 2.6 mm'de açık ped kenarı ile en yakın sinyal pedi arasındaki boşluk 0.4 yerine 0.2 mm kalıyordu ve macun şablonu gerçek pedden %46 fazla lehim koyuyordu. |
| **AD9251** (kütüphane varsayılanı) | EP 3.8 mm + termal via | CP-64-4: 9×9 mm LFCSP, açık ped nominal **4.7 mm** | Kütüphane varsayılanı gerçek kullanımla (EP 4.7) eşitlendi. Kartı etkilemiyordu (sayfa örneği varsayılanı eziyor) ama bu sembolü alan bir sonraki kişi yanlış pedi miras alıyordu. |

Doğrulanıp **doğru** bulunanlar (değişiklik yok): AD9251 LFCSP-64
9×9 · AD9767 LQFP-48 7×7 · ECP5 caBGA-256 14×14 P0.8 · W9825G6KH
TSOP-II-54 · ADCLK846 LFCSP-24 4×4 · SN65LVDS2 SOT-23-5 · TPS62130
VQFN-16 3×3 · LM5164 SO PowerPAD-8 · RTL8211F WQFN-40 5×5 P0.4 ·
DRV8833 HTSSOP-16 PowerPAD · W25Q128JVSIQ SOIC-8 208 mil.

Pin **dizilimi** birebir doğrulananlar: INA240 D paketi
(1 IN−, 2 GND, 3 REF2, 4 NC, 5 OUT, 6 VS, 7 REF1, 8 IN+ — SBOS662C
Tablo 6-1 ile birebir), PE4312 20 pin + açık ped (DOC-81482 Tablo 9
ile birebir), AD8318 LFCSP-16, TLV3501 SOT-23-6.

Devre kararı olarak doğrulananlar: PE4312 P/S = HIGH → **seri** mod
(veri sayfası s.5 ile birebir), pin 12 GND → normal mod; AD8318 ENBL
= VPSI → normal çalışma, VOUT–VSET bağlı → ölçüm modu; INA240 IN+
şöntün besleme tarafında, IN− yük tarafında.

### 3.4 Termal via'lar — ölçüldü, dördü kaldırıldı

KiCad'in `_ThermalVias` sürümü açık pedin içine **delikli (PTH)** via
koyuyor. Bu via'ların komşu sinyal pediyle arasındaki boşluk ölçüldü:

| Parça | Via | Boşluk | Güç | Karar |
|---|---|---|---|---|
| PE4312 (C ×4, D ×1) | 4 | **0.201 mm** | 0.43 mW | **kaldırıldı** |
| RTL8211F (A ×2) | 16 | **0.229 mm** | ~0.5 W | **kaldırıldı** — A altı katmanlı, In1/In4 tam toprak düzlemi |
| ADCLK846 (A ×1) | 9 | **0.283 mm** | ~0.32 W | **kaldırıldı** |
| DRV8833 (C ×16) | 12 | 0.833 mm | ~0 (darbeli) | **bırakıldı** — ihlal yok, PowerPAD toprak dönüşü |
| LM5164 (D ×1) | 6 | 0.636 mm | ~1 W buck | **bilerek bırakıldı — sebebi güç** |

Neden önemli: yönlendirici DSN sınıf kurallarında güç ağlarını 300 µm'de
tutuyor, yani bu çiftler her turda ihlal sayılıyor ve ihlal geometriden
geldiği için **çözülemiyor**. D kartının yönlendirme günlüğünde ihlal
sayısı turdan tura sabit kalıyor (152 → 152 → 152) ama yönlendirilmemiş
ağ sayısı düşüyor (62 → 56 → 52) — sabit taban tam bu.

Kaldırılan via'ların yerine gereken kısa toprak sapını, yönlendirmeden
sonra `dikis.py` hedefli olarak atıyor; sabit ızgaralı footprint
via'sından esnek.

---

## 4. Araç zincirinde bulunan tuzaklar

Bunlar devrede değil, **üretim zincirinde** hata; ikisi de sessizce
yanlış çıktı üretiyordu.

### 4.1 `lib/gen_symbols.py` beş düzeltmeyi geri alıyordu

Önceki turda AD9251'in açık pedi `"0"` → `"65"`, PE4312'ninki
`"Pad"` → `"21"` yapılmıştı. Düzeltmeler **doğrudan**
`lib/dogrudan-sdr.kicad_sym` dosyasına yazılmıştı; **üreteç eski
kaldı.** Yani `gen_symbols.py`'yi bir daha koşturan herkes iki
düzeltmeyi geri alıyordu. Bu turda gerçekten oldu ve `build.sh`
`KeyError: '65'` ile durdu — bu sefer gürültü çıkardı, ama sonuç
sessiz de olabilirdi.

Üreteç düzeltildi; artık ürettiği kütüphane ile depodakinin tek farkı
§3.3'teki kasıtlı ayak izi değişiklikleri:

```
python3 lib/gen_symbols.py && diff <(git show HEAD:kicad/lib/dogrudan-sdr.kicad_sym) lib/dogrudan-sdr.kicad_sym
# yalnizca 4 Footprint satiri farkli
```

### 4.2 Güç sembolü referans bloğu taşıyordu (`ref_denetim` yakaladı)

`schlib.Sheet` her sayfaya sayfa numarası × **100** blok veriyordu,
yani sayfa başına yalnız 99 güç sembolü. Taşınca **sessizce komşu
sayfanın bloğuna** giriliyor. Ölçüldü:

- C kartı `05_driver`: 16 PWR_FLAG eklendikten sonra sayaç 600'ü geçti;
  `#PWR611` hem 05_driver'daki bir PWR_FLAG hem 06_iface'deki bir GND
  oldu.
- Ayrıca **zaten taşmış bir sayfa vardı**: C kartı `03_filter` 144 güç
  sembolü kullanıyor, yani 300 tabanından 444'e kadar gidiyor ve sayfa
  04'ün bloğunun içine giriyordu.

Blok 100 → **1000** yapıldı. En yoğun sayfa 144 sembol, yani beş kat pay.
ERC bunu görmüyordu; `ref_denetim.py` gördü.

Doğrulama:

```
python3 ref_denetim.py          # uc kartta da "0 catisma bulgusu"
```

### 4.3 BOM CSV'si özetten daha kötüydü

`bom.py csv` LCSC kodunu ararken ekrandaki özetten farklı bir zincir
kullanıyordu; özet "BASE" derken CSV aynı satıra `?` yazıyordu.
**Üç kartta 68 satır** böyleydi — siparişe giden dosya, ekranda temiz
görünen bir BOM'dan sessizce daha kötü. Düzeltildi.

Düzeltirken ikinci bir hata yapıldı ve o da ölçülerek yakalandı:
A kartının `bom.py`'sinde `pasif_ara()` yok, çağrı `NameError`
veriyordu; hata görünmedi çünkü üretim komutunda stderr `/dev/null`'a
gidiyordu ve **CSV 78 satır yerine 31 satırda kesilmişti**. Kesilmiş
bir BOM ile sipariş, eksik parçayla dizgi demek. Düzeltildi.

Son durum:

| Dosya | Satır | LCSC kodu olmayan |
|---|---|---|
| `bom/BOM_A.csv` | 78 | 6 |
| `bom/BOM_C.csv` | 62 | 1 |
| `bom/BOM_D.csv` | 85 | 17 |

Kalan 24'ün çoğu D kartındaki elle sarılan toroid ve panel konnektörü —
LCSC'de zaten yoklar.

---

## 5. Düzeltilmemiş, AÇIK maddeler

### 5.1 Ayırma kondansatörleri kendi entegresinin yanında değil

Şema tarafı artık tam: her entegrenin her besleme rayında kondansatör
var (netlist'ten doğrulandı). Ama **yerleştirici onları çipin yanında
tutmuyor.** Karttan ölçülen mesafeler:

| Kart | Entegre | Ray | En yakın kondansatör |
|---|---|---|---|
| A | U16, U17 SN65LVDS2 | +3V3 | 21.1 / 25.5 mm (kendi 100 nF'leri var) |
| A | U62 TLV3501 | +3V3 | 30.5 mm (C902 var) |
| C | U41–U43 PE4312 | +3V3 | 48.5–64.8 mm (her birinin iki tanesi var) |
| D | U60, U61 AD8318 | +5V | 64.5 / 85.3 mm (C407/C411 var) |
| D | U56, U57 | +3V3 | 28.0 / 22.3 mm |

Bunlar şema hatası **değil**; `gercek_yerlesim.py`'nin düzeltilmesi
gereken davranışı. Bu turda dokunulmadı çünkü yerleşimi değiştirmek
kartı yeniden kurmayı ve koşan yönlendirmeyi çöpe atmayı gerektiriyor.
**Yönlendirme bitince ilk iş bu olmalı** — 64 mm ötedeki bir ayırma
kondansatörü elektriksel olarak yok sayılır.

### 5.2 Şema düzeltmeleri karta henüz geçmedi

Bu turda 55 parça eklendi ve 4 ayak izi değişti. Kartlar bunları
görmedi. Yönlendirme bitince zincirin (`yap.sh A/C/D`) yeniden
koşturulması **zorunlu**; aksi hâlde şema ile kart uyuşmuyor.

### 5.3 Veri sayfası doğrulaması gereken, uydurulmayan maddeler

Bunları doğrulayamadım; tahmin yazmak yerine açık bırakıyorum.

1. **RTL8211F açık ped ölçüsü.** Ayak izi EP 3.6 × 3.6 mm seçilmiş.
   Realtek'in mekanik çizimini elde edemedim (datasheet erişime kapalı).
   WQFN-40 5×5 için 3.6 makul ama **doğrulanmadı**.
2. **AD8318 açık ped.** `NXP_VQFN-16-1EP_4x4mm_P0.65mm_EP2.1x2.1mm`
   kullanılıyor — ADI parçasına NXP ayak izi. ADI CP-16-3'ün açık pedi
   2.25 mm civarı; 2.1 güvenli tarafta ama ADI'nin kendi land
   pattern'ıyla karşılaştırılmadı.
3. **AD8318 TADJ direnci HF'te.** 500 Ω seçilmiş. Veri sayfası
   Tablo 5'te 900 MHz–8 GHz için değer var, **1.8–54 MHz için yok** ve
   "deneme gerekir" diyor. Üretimde sıcaklık taramasıyla doğrulanacak.
4. **Kristal yük kondansatörü.** 18 pF, 12 pF'lik kristale göre
   Cstray = 3 pF varsayımıyla doğru. Cstray 5 pF çıkarsa ~48 ppm
   sapma olur ve 802.3 bütçesi zorlanır. İlk prototipte ölçülecek.
5. **PE4312 pin 3'teki seri 10 kΩ ile zamanlama.** 10 kΩ × ~5 pF
   = 50 ns; veri sayfası fCLK azami 10 MHz (100 ns) ve tSDSUP 10 ns
   istiyor. Üreticinin kendi değerlendirme kartı da aynı direnci
   koyuyor, ama gateware'in seri saat hızı buna göre sınırlanmalı.

---

## 6. Yanlış alarm olduğu gösterilen bulgular

Rapor "temiz" demiyor; neyin gerçekten temiz olduğunu gösteriyor.

**`guc_yolu.py` A kartında iki ağı "ince" diyor** (+3V3: en ince
150 µm < gerekli 386 µm; +1V1: 150 µm < 300 µm). İncelendi: bu
150 µm'lik izler ECP5'in (U10) BGA kaçış saplarıdır —
`elle_cek.py`'nin toptan via'ya çektiği 0.57 mm uzunluğunda parçalar,
+3V3'te 9, +1V1'de 6 tane. Her top rayın akımının payını taşıyor
(+3V3'te 1.2 A / 9 = 133 mA, +1V1'de 1.0 A / 6 = 167 mA); 1 oz bakırda
150 µm ~430 mA taşıyor. Gövde genişliği DSN sınıf kuralından geliyor
ve doğru: +3V3 600 µm, +1V1 800 µm. Aracın `min()` alması fazla kaba.

**`ref_denetim.py` §3 "referans dizisinde boşluk"** A'da 5, C'de 135,
D'de 12 satır veriyor. Örnekleme yapıldı: bunlar numaralandırma
tercihi (filtre bankasında bölüm başına adımlı referans). Aracın
kendi çıktısı da bunları `bulgu` saymıyor.

---

## 6b. Devre simülasyonu — bağlantı doğru, değerler yanlıştı

Buraya kadarki bütün denetimler **bağlantıyı** ölçüyor: hangi pin
hangi ağa bağlı, hangi ped boşta. Hiçbiri bir kondansatörün
**değerinin** doğru olup olmadığını söylemiyor. O yüzden filtreler
ngspice ile simüle edildi.

İki kartta da sonuç ağırdı.

### 6b.1 C kartı — alış bant filtreleri hiçbir şey geçirmiyordu

Altı pozisyonun da tepesi, geçirmesi gereken bandın **altındaydı**;
bandın kendisi 24–41 dB bastırılmıştı. Alıcı her bantta sağır olurdu.

| bant | tepe | bandın kenarında |
|---|---|---|
| 160m | 1.43 MHz | −34 dB |
| 80/60m | 3.32 | −25 |
| 40/30m | 6.74 | −27 |
| 20/17m | 13.38 | −32 |
| 15/10m | 20.72 | −28 |
| 6m | 43.06 | −41 |

Sebep aritmetik: üç rezonatör çıplak LC gibi hesaplanmış, kuplaj
kondansatörleri ise onlara paralel binip frekansı aşağı çekiyor.
160 m'de elle doğrulandı — 430 + 270 + 62 = 762 pF, 16 µH ile
1.44 MHz, simülasyonun bulduğu tepe 1.43.

Telafi tek başına yetmedi: tepeden kuplajlı yapı dar bant içindir,
bu pozisyonlar ise geniş (80+60 m = %44 oransal bant genişliği).
Yapı **merdiven bant geçirene** çevrildi (sönt / seri / sönt,
3 kutuplu Chebyshev 0,1 dB). Doğrulama, değerler **E12'ye
oturtulmuş hâlde** ve bobin Q'su dahil yapıldı:

| bant | ekleme kaybı | en kötü bant kenarı | önceki |
|---|---|---|---|
| 160m | 1,31 dB | −1,71 | −34 |
| 80/60m | 0,52 | −0,97 | −25 |
| 40/30m | 0,73 | −1,49 | −27 |
| 20/17m | 0,83 | −1,04 | −32 |
| 15/10m | 0,71 | −1,00 | −28 |
| 6m | 1,72 | −2,37 | −41 |

Bölüm başına parça 3 bobin + 7 kondansatörden 3 + 3'e düştü; kart
502'den 406 parçaya indi. Bobinler tamamen SMD: toroid Q'su 150,
SMD 40, aradaki fark 160 m'de 1 dB ve HF'te alıcının gürültü
tabanını atmosferik gürültü belirliyor. Karşılığında elle sarılacak
48 parça ortadan kalktı.

### 6b.2 D kartı — verici her bantta yasal sınırın altındaydı

İkinci harmonik bastırma 3–30 dB arasındaydı; gereken 30 MHz altında
43 dB, üstünde 60 dB. 80/60 m'de 3,5 MHz'in harmoniği **3,4 dB**
aşağıdaydı, yani filtre ona neredeyse hiç dokunmuyordu. Kartta
belirtisi olmazdı: çıkış gücü, SWR ve verim doğru okunurken harmonik
yayılır.

Sebep yanlış bir değer değil, bant gruplaması: pozisyon 5,37 MHz'i
geçirmek zorunda olduğu için kesim 6,0 MHz'te, ama aynı pozisyonun
en düşük bandı olan 3,5 MHz'in harmoniği 7,0 MHz — kesimin hemen
üstü. Kutup artırmak kurtarmıyor; Chebyshev bastırma formülüyle
hesaplandı, 9 kutup bile orada 32 dB veriyor.

Her seri bobine **tuzak kondansatörü** eklendi (iletim sıfırı tam
harmonikte) ve 80 ile 60 m ayrı pozisyonlara alındı. Yedinci röle
bypass'tı; harmonik filtresi devre dışıyken yayın zaten hiçbir
durumda meşru olmadığı için oraya 60 m kondu.

| bant | ekleme kaybı | 2. harmonik | önceki |
|---|---|---|---|
| 160m | 0,61 dB | **−82,4** | −25,2 |
| 80m | 0,64 | −80,7 | (gruptaydı) |
| 60m | 0,45 | −81,9 | (gruptaydı) |
| 40/30m | 1,45 | −58,0 | −9,5 |
| 20/17m | 0,88 | −68,4 | −18,2 |
| 15/10m | 1,35 | −61,0 | −14,1 |
| 6m | 1,14 | −82,8 | −30,2 |

### 6b.3 Simülasyon araçlarının kendi hataları

Üç tanesi çıktı ve üçü de "bu sayı olamaz" denerek yakalandı, bir
şey çökmedi:

1. 1 V'luk kaynak 50 Ω üzerinden eşleşmiş yükte 0,5 V verir; kayıpsız
   filtre bile −6,02 dB okur. Düşülmeden bütün ekleme kayıpları 6 dB
   kötümser raporlandı. Her yapılandırmada tekrarlanan "7 dB taban"
   ele verdi.
2. E12 yuvarlayıcı çarpma yerine bölme yapıp her değeri 10'un
   kuvvetine oturttu (10000/1000/100). Sentez çıktısının bu kadar
   yuvarlak olması imkânsız.
3. Bobin kaybı sabit 1 MHz ile hesaplandı; 25 MHz'lik filtrede kayıp
   25 kat az çıkıyordu. Q=40 ile 0,02 dB ekleme kaybı fiziksel olarak
   mümkün değil.

Araçlar depoda: `kicad/filtre_sim.py` (eski topolojiyi ölçer, neyin
yanlış olduğunun kaydı), `kicad/filtre_tasarim.py` (yeni topolojiyi
sentezler ve doğrular), `kicad/lpf_sim.py` (harmonik filtreleri).

---

## 7. Doğrulama komutlarının tamamı

```bash
cd kicad
export PYTHONHASHSEED=0

# sema uretimi + ERC (uc kart)
for d in A_main C_rf D_pa; do (cd $d && ./build.sh); done

# mevcut denetimler
python3 ped_denetim.py            # 0 / 0 / 0
python3 ref_denetim.py            # 0 / 0 / 0 catisma
python3 kondansator_denetim.py    # 0 parca temin edilemez
python3 guc_yolu.py               # A'da 2 (yanlis alarm, §6)

# yeni denetimler
python3 sema_denetim.py           # karttan okur (kart eski)
python3 netlist_denetim.py        # SEMADAN okur — 22 kilit, 0 bulgu

# ciktilar
kicad-cli sch export pdf A_main/dogrudan_sdr_A.kicad_sch -o ../ardc/sema/dogrudan_sdr_A.pdf
(cd A_main && python3 bom.py csv)
```

`netlist_denetim.py` çıktısı (üç kart):

```
KART A   420 ag    => 0 bulgu
KART C   450 ag    => 0 bulgu
KART D   172 ag    => 0 bulgu
TOPLAM 0 bulgu
```

Kilitlenen 22 beklentinin her birinin yanında veri sayfası kaynağı
yazılı; amaç bilgiyi kodda tutmak, ki bir daha kimse geri almasın.
