#!/usr/bin/env bash
# D karti semasini uretir, kanoniklestirir, dogrular.
#
#   ./build.sh          uret + ERC
#   ./build.sh pdf      ustune PDF ve SVG de cikar
#
# KANONIKLESTIRME NEDEN GEREKLI: kendi urettigimiz dosya gecerli ama
# KiCad'in yazdigi bicimle birebir ayni degil (generator etiketi, sayi
# bicimi, paren yerlesimi). Aradaki fark KiCad'i acilista "bir hata
# bulundu ve otomatik duzeltildi" uyarisi vermeye itiyor. Uretimden
# sonra bir kez 'sch upgrade' calistirinca dosya kanonik hale geliyor
# ve ikinci gecis onu degistirmiyor (sabit nokta dogrulandi).
set -e
cd "$(dirname "$0")"

echo "== iskelet =="
python3 mkproject.py

echo "== sayfalar =="
for g in gen_*.py; do
    [ -e "$g" ] || continue
    python3 "$g"
done

echo "== kanoniklestirme =="
for f in *.kicad_sch; do
    kicad-cli sch upgrade --force "$f" >/dev/null 2>&1 || true
done
echo "   $(ls -1 *.kicad_sch | wc -l) dosya"

# BOM'U ZINCIR URETSIN.
# BOM_*.csv elle uretilmis dosyalardi ve build.sh onlara hic
# dokunmuyordu. Semaya bes kondansator eklendikten sonra BOM
# degismedi; ARDC paketine de o bayat hali girdi. Bir BOM'un
# semayla tutmamasi, uretimde yanlis parca siparisi demek.
echo "== BOM =="
python3 bom.py csv 2>/dev/null | tail -1
echo "== ERC =="
kicad-cli sch erc dogrudan_sdr_D.kicad_sch -o /tmp/erc.rpt 2>&1 | grep -E "Found|violation" || true
grep -oP '\[.*?\]:' /tmp/erc.rpt 2>/dev/null | sort | uniq -c | sort -rn | sed 's/^/   /' || true

if [ "$1" = "pdf" ]; then
    echo "== cikti =="
    kicad-cli sch export pdf dogrudan_sdr_D.kicad_sch -o /tmp/A.pdf >/dev/null
    rm -rf /tmp/A_svg && mkdir -p /tmp/A_svg
    kicad-cli sch export svg dogrudan_sdr_D.kicad_sch -o /tmp/A_svg >/dev/null
    echo "   /tmp/A.pdf  ve  /tmp/A_svg/"
fi

echo
echo "ac:  kicad $(pwd)/dogrudan_sdr_D.kicad_pro"
