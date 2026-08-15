#!/bin/bash
# Butun test tezgahlarini kostur.
#
#   ./sim/kos.sh
#
# NEDEN TEK KOMUT: her modulu ayri kosturmak zamanla unutuluyor ve
# bir degisiklik baska bir modulu bozdugunda haftalar sonra
# gorunuyor. Kart gelmeden once guvendigimiz tek sey bu testler.
set -u
cd "$(dirname "$0")/.."
export PATH=~/opt/oss-cad-suite/bin:$PATH

testler=(
  "tb_nco      sim/tb_nco.v      rtl/nco.v"
  "tb_cic      sim/tb_cic.v      rtl/cic_azalt.v"
  "tb_telafi   sim/tb_telafi.v   rtl/fir_telafi.v"
  "tb_paket    sim/tb_paket.v    rtl/paketleyici.v"
  "tb_kontrol  sim/tb_kontrol.v  rtl/kontrol_zinciri.v"
  "tb_dac      sim/tb_dac.v      rtl/dac_cikis.v"
  "tb_kayit    sim/tb_kayit.v    rtl/kayit.v"
  "tb_rgmii    sim/tb_rgmii.v    rtl/rgmii_veris.v"
  "tb_duc      sim/tb_duc.v      rtl/duc.v rtl/nco.v"
  "tb_ddc      sim/tb_ddc.v      rtl/nco.v rtl/karistirici.v rtl/cic_azalt.v"
)

gecen=0; kalan=0
for t in "${testler[@]}"; do
  set -- $t
  ad=$1; shift
  if iverilog -g2012 -o "/tmp/$ad" "$@" 2>/dev/null && \
     timeout 400 vvp "/tmp/$ad" 2>/dev/null | grep -aq "GECTI\|bitti"; then
    printf "  %-12s GECTI\n" "$ad"; gecen=$((gecen+1))
  else
    printf "  %-12s KALDI\n" "$ad"; kalan=$((kalan+1))
  fi
done
echo "  ----"
echo "  $gecen gecti, $kalan kaldi"
[ "$kalan" -eq 0 ]
