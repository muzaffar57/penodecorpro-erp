#!/bin/bash
# tools/vaqt_sayohati.sh — kech105 (9 + 50-band, QAROR "Toshkent vaqti bo'yicha"): BUTUN test to'plamini soatni CHEGARA
# paytlariga surib yurgizadi. Hisobot kun / oy / yili Toshkent kalendari (UTC+5) bo'yicha — "joriy davr" ni UTC dan
# oladigan kod yoki test FAQAT Toshkent 00:00–05:00 (UTC 19:00–24:00) da yiqiladi, oddiy soatda ko'rinmaydi (kech105
# o'lchovi: moslanmagan to'plamda 26 test SOXTA yiqildi; moslangandan keyin 4 ta HAQIQIY server xatosi topildi).
# Vaqt / sana mantig'iga (hisobot davri, "bugun", oy oxiri) tegadigan HAR o'zgarishdan keyin yurgiziladi.
#
# Talab: pip install time-machine (konteynerda: --break-system-packages) + tools/hammasi.sh talablari.
# Ishlatish (repo ildizidan yoki istalgan joydan):
#   bash tools/vaqt_sayohati.sh               # 4 payt, natija: /tmp/vaqt_<payt>/_xulosa.txt (tools/hammasi.sh formati)
#   YANGIDAN=1 bash tools/vaqt_sayohati.sh    # oldingi natijalarni o'chirib, boshidan
# Paytlar (UTC → Toshkent):
#   oy_utc   2026-09-30T21:00Z → 01.10 02:00 (oy va kun chegarasi), jarayon mintaqasi TZ=UTC
#   oy_tosh  o'sha payt, TZ=Asia/Tashkent (testlar lokal soatga bog'liq emasligi)
#   kun      2026-10-15T20:00Z → 16.10 01:00 (faqat kun chegarasi), TZ=UTC
#   yil      2026-12-31T20:00Z → 01.01.2027 01:00 (yil chegarasi), TZ=Asia/Tashkent
# Talab: har birida fail=0, yomon_rc=0 (chiqish kodi 0). Soat `tools/vaqt_sayohati/sitecustomize.py` orqali suriladi
# (PYTHONPATH; JS testlariga ta'sir qilmaydi).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -c "import time_machine" 2>/dev/null || { echo "time-machine o'rnatilmagan: pip install time-machine"; exit 2; }
export PYTHONPATH="$ROOT/tools/vaqt_sayohati${PYTHONPATH:+:$PYTHONPATH}"
KOD=0
for q in "oy_utc 2026-09-30T21:00:00+00:00 UTC" "oy_tosh 2026-09-30T21:00:00+00:00 Asia/Tashkent" \
         "kun 2026-10-15T20:00:00+00:00 UTC" "yil 2026-12-31T20:00:00+00:00 Asia/Tashkent"; do
  set -- $q
  LOG="/tmp/vaqt_$1" TZ="$3" VAQT_SAYOHAT="$2" bash "$ROOT/tools/hammasi.sh" > /dev/null 2>&1
  echo "$1 ($2, TZ=$3): $(grep -a '^NATIJA' "/tmp/vaqt_$1/_xulosa.txt" | tail -1)"
  grep -aq 'fail=0 yomon_rc=0' "/tmp/vaqt_$1/_xulosa.txt" || KOD=1
done
exit $KOD
