# KiCad çalışma dizini

```
lib/dogrudan-sdr.kicad_sym   sembol kütüphanesi
lib/gen_symbols.py           üreteç — sembolleri BU yazıyor, elle düzenleme
lib/ATTRIBUTION.md           ECP5 sembolü kaynağı ve lisansı
A_main/                      A kartı (ADC+DAC+saat+FPGA+PHY+güç)
C_frontend/                  C kartı (koruma+T/R+zayıflatıcı+ön seçici)
```

## Semboller

| Sembol | Pin | Birim | Kaynak | Durum |
|---|---|---|---|---|
| ECP5-BGA256 | 256 | 8 | Cynthion (CERN-OHL-P) | pin uyumu doğrulandı |
| AD9251 | 65 | 4 | datasheet Rev.C s.11-12 | görsel doğrulandı |
| AD9767 | 48 | 3 | datasheet Rev.G s.9-10 | pin sayımı doğrulandı |
| RTL8211F | 41 | 2 | datasheet Rev.1.1 s.14-17 | görsel doğrulandı |
| PE4312 | 21 | 1 | DOC-81482-4.01 s.15 | pin sayımı doğrulandı |
| ADP150 | 5 | 1 | datasheet Rev.E s.6 | — |
| ABLNO-V | 4 | 1 | Abracon ABLNO s.8 | **doğrulandı** |

KiCad standart kütüphanesinden ayrıca: `W25Q128JVS`, `TPS62130`, `TPS7A20`.

## Üreteci kullan, dosyayı elle düzenleme

```bash
cd lib
python3 gen_symbols.py          # kütüphaneye ekler
kicad-cli sym export svg -o /tmp/s dogrudan-sdr.kicad_sym
rsvg-convert -w 800 /tmp/s/AD9251_unit1.svg -o /tmp/x.png   # gözle bak
```

`gen_symbols.py` kutu geometrisini pin sayısı **ve isim uzunluklarından**
hesaplıyor. Elle kutu yazma; iki kere denedim, ikisinde de pin gövdesi
kutunun içinde kaldı ve o pine tel bağlanamadı.

> Üreteç kütüphaneye **ekliyor**, sıfırlamıyor. Yeniden üretmeden önce
> temiz kütüphaneyi geri yükle, yoksa semboller tekrarlanır.

## Doğrulanmış footprint'ler

Hepsi KiCad 10 standart kütüphanesinde:

```
BGA-256_14.0x14.0mm_Layout16x16_P0.8mm      ECP5 caBGA-256
QFN-64-1EP_9x9mm_P0.5mm_EP3.8x3.8mm         AD9251 LFCSP-64
LQFP-48_7x7mm_P0.5mm                        AD9767
QFN-40-1EP_5x5mm_P0.4mm_EP3.8x3.8mm         RTL8211F
QFN-20-1EP_4x4mm_P0.5mm_EP2.6x2.6mm         PE4312
TSOT-23-5                                   ADP150
```

ABLNO ayak izi bu depoda çizildi: `lib/dogrudan-sdr.pretty/`
`Oscillator_Abracon_ABLNO_4pad_14.3x8.7mm.kicad_mod`
Gövde 14.30 × 8.70 mm, 4 ped 2.5 × 1.5 mm, aralık 5.08 × 5.80 mm.

> Pin-1 işaretini ilk çizişte yanlış köşeye koydum (pad 4'ün yanına).
> Parçanın 180° ters lehimlenmesine yol açardı. SVG'ye bakınca yakalandı.
> **Her ayak izini çizdikten sonra render edip gözle bak.**

## Sıradaki adım: netlist şartnamesi

Şema üretmeden önce **hangi pin nereye** yazılacak, insan okuyabilir metin
olarak. Sebep: 256 pinlik BGA'nın bağlantılarını doğrudan `.kicad_sch`
dosyasına yazmak görsel olarak doğrulanamaz. Şartname gözden geçirilebilir,
şema ondan üretilir.
