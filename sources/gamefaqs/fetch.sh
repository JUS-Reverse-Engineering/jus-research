#!/bin/bash
# Fetch Jump Ultimate Stars GameFAQs guides via the Wayback Machine
# (gamefaqs.gamespot.com blocks direct scraping with Cloudflare).
# Extracts plain text from the <pre> blocks into raw/<id>-<slug>.txt.
# Usage: ./fetch.sh   (skips files that already exist)
set -u
cd "$(dirname "$0")"
mkdir -p raw

GUIDES="
53073|mykas0-walkthrough
45856|genroh-guide
47453|allen-walker
47894|arale
47060|bankai-ichigo
49230|dio
49910|don-patch
52262|dr-mashirito
52424|edajima
46504|eve
51204|franky
47666|frieza
46732|gintoki
46542|gohan
47182|goku
49032|gon-freaks
46608|gotenks
46926|hiei
46708|hitsugaya
46858|ichigo-kurosaki
46575|jaguar
46754|jotaro
46302|kagura
46618|kakashi
46549|kazuki-mutou
46478|kenshiro
46804|killua
46226|kurama
49273|lenalee-vicevirtuoso
53025|lenalee-wong
49253|majin-buu
50074|momotaro
47359|luffy
47061|muhyo-yamcha
50905|muhyo-lordlegacy
46921|nami
47526|naruto
46537|neuro
46791|nico-robin
46844|piccolo
46626|raoh
46459|renji
46229|rukia
46574|sakura
46640|sanji
46543|sasuke
46807|seiya
46293|taikoubou
46141|train-heartnet
48474|tsuna
51174|vegeta
46755|yoh
46477|yugi
46607|yusuke
45966|ally-boost-faq
48966|deck-making
47980|glitch-faq
47130|healing-faq
52886|j-gem-faq
46489|manga-moments
59773|statistics-faq
49288|support-faq
46526|wireless-mode
"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

for line in $GUIDES; do
  id="${line%%|*}"
  slug="${line#*|}"
  out="raw/${id}-${slug}.txt"
  [ -s "$out" ] && { echo "skip $out (exists)"; continue; }
  url="https://gamefaqs.gamespot.com/ds/933199-jump-ultimate-stars/faqs/${id}"
  snap=$(curl -s "http://archive.org/wayback/available?url=${url#https://}" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("archived_snapshots",{}).get("closest",{}).get("url",""))')
  if [ -z "$snap" ]; then
    echo "MISSING snapshot: $id $slug" >&2
    sleep 2
    continue
  fi
  html=$(curl -sL -A "$UA" "$snap")
  echo "$html" | python3 -c '
import sys, re, html
src = sys.stdin.read()
blocks = re.findall(r"<pre[^>]*>(.*?)</pre>", src, re.S | re.I)
text = "\n".join(html.unescape(re.sub(r"<[^>]+>", "", b)) for b in blocks)
sys.stdout.write(text)
' > "$out"
  size=$(wc -c < "$out" | tr -d " ")
  if [ "$size" -lt 2000 ]; then
    echo "SUSPICIOUSLY SMALL ($size bytes): $id $slug from $snap" >&2
  else
    echo "ok $out ($size bytes)"
  fi
  sleep 2
done
echo "done"
