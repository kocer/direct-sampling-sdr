# Elle takilan parcalar — kart D

Bu parcalar JLCPCB dizgisine GIRMIYOR (delikli). Ayri
siparis edilip elle lehimleniyor.

## Sart: gumus mika ya da RF porselen

Disk seramik ALMAYIN. 100 W'ta harmonik filtresinin sont
kondansatorunden 14 MHz'te ~1.3 A RF akimi geciyor ve
uzerinde ~93 V var. Disk seramik bu akimda isinir,
kapasitesi kayar, filtre bozulur. Bozulma sadece verici tam
gucte calisirken cikar — tezgahta olcerken gorunmez.

En az 500 V, C0G/mika. Uygun aileler: Cornell Dubilier CD15/CD19
(gumus mika), ATC 100B (porselen), Vishay MKP degil.

| deger | adet | tur |
|---|---|---|
| 1000pF | 1 | gumus mika / RF porselen |
| 110pF | 1 | gumus mika / RF porselen |
| 120pF | 1 | gumus mika / RF porselen |
| 13pF | 1 | gumus mika / RF porselen |
| 1500pF | 1 | gumus mika / RF porselen |
| 150pF | 1 | gumus mika / RF porselen |
| 1600pF | 2 | gumus mika / RF porselen |
| 160pF | 3 | gumus mika / RF porselen |
| 180pF | 1 | gumus mika / RF porselen |
| 200pF | 1 | gumus mika / RF porselen |
| 24pF | 1 | gumus mika / RF porselen |
| 2700pF | 1 | gumus mika / RF porselen |
| 270pF | 3 | gumus mika / RF porselen |
| 3.3pF | 1 | gumus mika / RF porselen |
| 360pF | 1 | gumus mika / RF porselen |
| 430pF | 1 | gumus mika / RF porselen |
| 470uF | 2 | elektrolitik |
| 51pF | 1 | gumus mika / RF porselen |
| 560pF | 2 | gumus mika / RF porselen |
| 62pF | 3 | gumus mika / RF porselen |
| 75pF | 1 | gumus mika / RF porselen |
| 820pF | 2 | gumus mika / RF porselen |
| 91pF | 3 | gumus mika / RF porselen |

Bu dosyayi tedarik_denetim.py uretiyor; elle degistirme.