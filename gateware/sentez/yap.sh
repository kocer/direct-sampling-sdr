#!/bin/bash
# Gateware derleme — sentez, yer-yonlendirme, bitstream.
#
#   ./sentez/yap.sh            # varsayilan tohumla
#   ./sentez/yap.sh --ara      # gecen bir tohum bulana kadar dene
#
# NEDEN TOHUM ARAMA VAR. nextpnr'in yerlestirici baslangici rastgele
# ve clk_eth 125 MHz'e ~4 MHz payla kapaniyor: bes tohumun dordu
# geciyor, biri gecmiyor. Bir yapiyi "gecen tohumu bulduk" diye
# birakmak kirilgandir — ama tohumu SABITLEYIP payi da olcup yazmak
# durusu belgeler. Pay 10 MHz'in altinda kaldigi surece bu betik
# uyariyor; bir sonraki degisiklikte tekrar kacacagini bilelim.
#
# Pay artirmak icin yapilanlar (kayit icin):
#   - NCO sinus tablosu blok RAM'e (LUT 12724 -> 8795)
#   - FIFO okumasi senkron, doluluk yazmacli, gray cevrimi ayri kademe
#   - FIFO isaretci artislari onceden hesaplaniyor, 'oku' sadece mux suruyor
#   - RGMII yuku FIFO'dan bir cevrim onden okunuyor
#   - RGMII sayaci geri sayiyor (genis karsilastirma yerine sabitle)
#   - "son bayt" bayragi yazmacta: 16 bit karsilastirma FIFO'nun
#     tuketim yolundan cikti (117-129 -> 124-136 MHz)
set -u
cd "$(dirname "$0")/.."
export PATH=~/opt/oss-cad-suite/bin:$PATH

CIHAZ="--25k"
PAKET="CABGA256"
# VARSAYILAN TOHUM 1 — OLCULEREK SECILDI.
# Bes tohumun dordu geciyor; 1 en genis payi veriyor (clk_eth
# 136.2 MHz, hedef 125). Tohumu sabitlemek kapanmayi belgeliyor
# ama pay hala 9 MHz, yani buyuk bir ekleme yine kacirabilir.
# O durumda "--ara" baska tohum dener; tekrar tekrar kaciyorsa
# yapiyi duzeltmek gerekiyor, tohum aramak degil.
TOHUM="${TOHUM:-1}"

echo "== LPF uretiliyor (karttan)"
python3 sentez/lpf_yaz.py 2>/dev/null || { echo "LPF uretilemedi"; exit 1; }

echo "== sentez"
yosys -q -p "read_verilog rtl/*.v; synth_ecp5 -top ust -json sentez/ust.json" \
  || { echo "SENTEZ KALDI"; exit 1; }

kos_pnr() {
  nextpnr-ecp5 $CIHAZ --package $PAKET --json sentez/ust.json \
    --lpf sentez/ust.lpf --textcfg sentez/ust.cfg --seed "$1" 2>sentez/pnr.log >/dev/null
  grep -E "Max frequency for clock" sentez/pnr.log | tail -4
}

if [ "${1:-}" = "--ara" ]; then
  for s in 0 1 2 4 5 6 7 8; do
    echo "== yerlesim, tohum $s"
    cikti=$(kos_pnr "$s")
    if ! echo "$cikti" | grep -q FAIL; then
      echo "$cikti" | sed 's/^/   /'
      echo "== tohum $s GECTI"
      TOHUM=$s
      break
    fi
    echo "$cikti" | grep FAIL | sed 's/^/   /'
  done
else
  echo "== yerlesim, tohum $TOHUM"
  kos_pnr "$TOHUM" | sed 's/^/   /'
fi

# SADECE SON ZAMANLAMA RAPORUNA BAK.
#
# nextpnr zamanlamayi IKI KEZ raporluyor: once yerlesimden sonra
# (tahmin, yollar henuz cekilmemis), sonra yonlendirmeden sonra
# (gercek). Butun loga "grep FAIL" atmak yerlesim tahminini de
# yakaliyor ve gecen bir yapiyi KALDI diye gosteriyor.
#
# Bu bastan beri boyleydi ama tetiklenmiyordu: yerlesim tahmini de
# 80 MHz'in ustunde kaliyordu. Dort kanalli veris zinciri eklenince
# tahmin 72.90'a dustu, gercek sonuc ise 88.96 ile GECTI — ve script
# yapiyi reddetti. Yanlis alarmin bedeli, olmayan bir zamanlama
# sorununu kovalamak.
if tail -4 sentez/pnr.log | grep -q FAIL; then
  echo "ZAMANLAMA KALDI — './sentez/yap.sh --ara' baska tohum dener,"
  echo "ama tekrar tekrar kaciyorsa yapiyi duzeltmek gerekiyor."
  exit 1
fi

echo "== pay"
grep -E "Max frequency for clock" sentez/pnr.log | tail -4 | \
  sed -E 's/.*glbnet.([a-z0-9_]+).*: ([0-9.]+) MHz .PASS at ([0-9.]+).*/   \1: \2 MHz (hedef \3)/'

echo "== bitstream"
ecppack --compress sentez/ust.cfg sentez/ust.bit || exit 1
ls -l sentez/ust.bit | awk '{print "   " $5 " bayt"}'
echo "== bitti"
