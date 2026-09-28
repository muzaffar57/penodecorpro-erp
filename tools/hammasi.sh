#!/bin/bash
# tools/hammasi.sh — repodagi BARCHA testlar (tools/test_*.py va tools/test_*.js), QAYTA DAVOM ETADIGAN.
#
# Ishlatish (repo ildizidan yoki istalgan joydan):
#   bash tools/hammasi.sh                        # SQLite, TENANT_FILTER o'chiq  → natija: /tmp/hammasi_tf0
#   TF=1 bash tools/hammasi.sh                   # TENANT_FILTER=1 (global korxona filtri YOQIQ) → /tmp/hammasi_tf1
#   PG_URL=postgresql://postgres@127.0.0.1:5432 bash tools/hammasi.sh
#                                                # PG_URL ni qo'llaydigan testlar HAQIQIY PostgreSQL da (har test o'z
#                                                # bazasini DROP / CREATE qiladi); qolganlari SQLite da  → /tmp/hammasi_pg_tf0
#   LOG=/yol/papka bash tools/hammasi.sh         # natija papkasini o'zingiz bering
#   YANGIDAN=1 bash tools/hammasi.sh             # oldingi natijalarni o'chirib, boshidan
#
# Har test tugagach <LOG>/<fayl>.rc yoziladi; qayta ishga tushirilsa .rc bori o'tkazib yuboriladi (konteyner qayta
# yuklansa ham davom etadi). Oxirida <LOG>/_xulosa.txt:
#   <fayl> rc=<chiqish kodi> ok=<o'tdi> fail=<yiqildi>
#   NATIJA jami=… ok=… fail=… yomon_rc=…      ← talab: fail=0 va yomon_rc=0
#   TUGADI
#
# Talablar: python3 + `pip install -r requirements.txt` (+ pyflakes, httpx); node + `npm install -g jsdom@24`.
# PG testlari PARALLEL yurgizilmaydi (bu skript ketma-ket yurgizadi). Bir test chegarasi — 900 s.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF="${TF:-}"
PG="${PG_URL:-}"
if [ -z "${LOG:-}" ]; then
  if [ -n "$PG" ]; then LOG="/tmp/hammasi_pg_tf${TF:-0}"; else LOG="/tmp/hammasi_tf${TF:-0}"; fi
fi
[ "${YANGIDAN:-}" = "1" ] && rm -rf "$LOG"
mkdir -p "$LOG"
cd "$ROOT" || exit 1
NODE_PATH="$(npm root -g 2>/dev/null)"
export NODE_PATH
FAYLLAR="$(ls tools/test_*.py) $(ls tools/test_*.js)"
for f in $FAYLLAR; do
  b="$(basename "$f")"
  [ -f "$LOG/$b.rc" ] && continue
  T="$(mktemp -d /tmp/tst_XXXXXX)"
  case "$f" in
    *.py) CMD="python3 $f" ;;
    *.js) CMD="node $f" ;;
  esac
  # `env` da avval -u (o'chirish) opsiyalari, keyin QIYMAT=... berilishi shart.
  OCHIR=(); QIYMAT=(TMPDIR="$T")
  if [ -z "$TF" ]; then OCHIR+=(-u TENANT_FILTER); else QIYMAT+=(TENANT_FILTER="$TF"); fi
  if [ -z "$PG" ]; then OCHIR+=(-u PG_URL); else QIYMAT+=(PG_URL="$PG"); fi
  env "${OCHIR[@]}" "${QIYMAT[@]}" timeout 900 $CMD > "$LOG/$b.log" 2>&1
  echo $? > "$LOG/$b.rc"
  rm -rf "$T"
done
: > "$LOG/_xulosa.txt"
JAMI_OK=0; JAMI_FAIL=0; YOMON=0
for f in $FAYLLAR; do
  b="$(basename "$f")"
  RC="$(cat "$LOG/$b.rc")"
  N="$(grep -a "NATIJA" "$LOG/$b.log" | tail -1)"
  OK="$(echo "$N" | sed -n "s/.*o'tdi = \([0-9]*\).*/\1/p")"
  FL="$(echo "$N" | sed -n "s/.*yiqildi = \([0-9]*\).*/\1/p")"
  OK="${OK:-0}"; FL="${FL:-0}"
  JAMI_OK=$((JAMI_OK + OK)); JAMI_FAIL=$((JAMI_FAIL + FL))
  if [ "$RC" != "0" ] || [ -z "$N" ]; then YOMON=$((YOMON + 1)); fi
  echo "$b rc=$RC ok=$OK fail=$FL" >> "$LOG/_xulosa.txt"
done
echo "NATIJA jami=$((JAMI_OK + JAMI_FAIL)) ok=$JAMI_OK fail=$JAMI_FAIL yomon_rc=$YOMON" >> "$LOG/_xulosa.txt"
echo TUGADI >> "$LOG/_xulosa.txt"
tail -2 "$LOG/_xulosa.txt"
