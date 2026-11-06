"""⑥ チェック用ページ（review.html）を作る。render.py から呼ばれる。

動画の横に「どこを切ったか（理由つき）」「テロップ一覧」が並び、
クリックするとその場面に飛ぶ。保留中のカット候補もここで確認できる。
"""
from __future__ import annotations

import html

from common import fmt_time, map_span

TYPE_JA = {"silence": "無音", "filler": "フィラー", "retake": "言い直し", "offtopic": "脱線・冗長", "other": "その他"}


def out_pos(t: float, keeps) -> float:
    """元の時間 t の位置が、出来上がり動画では何秒目にあたるか（カット内なら直前の位置）。"""
    acc = 0.0
    for s, e in keeps:
        if t < s:
            return acc
        if t <= e:
            return acc + (t - s)
        acc += e - s
    return acc


def write_review(pdir, tl: dict, keeps, video_name: str) -> None:
    rows_cut = []
    for c in sorted(tl.get("cuts", []), key=lambda c: c["start"]):
        if c.get("type") == "silence" and c.get("enabled", True):
            continue  # 無音カットは数が多いので一覧からは省く（合計だけ表示）
        pos = out_pos(c["start"], keeps)
        state = "カット" if c.get("enabled", True) else "保留（残している）"
        cls = "on" if c.get("enabled", True) else "hold"
        rows_cut.append(
            f'<tr class="{cls}" data-t="{max(0, pos - 2):.2f}"><td>{fmt_time(pos)}</td>'
            f'<td>{html.escape(c.get("id", ""))}</td><td>{state}</td>'
            f'<td>{TYPE_JA.get(c.get("type"), c.get("type", ""))}</td>'
            f'<td>{c["end"] - c["start"]:.1f}秒</td><td>{html.escape(c.get("reason", ""))}</td></tr>'
        )
    rows_tel = []
    for t in sorted(tl.get("telops", []), key=lambda t: t["start"]):
        span = map_span(t["start"], t["end"], keeps)
        if span is None:
            continue
        rows_tel.append(
            f'<tr data-t="{span[0]:.2f}"><td>{fmt_time(span[0])}</td><td>{html.escape(t["id"])}</td>'
            f'<td class="{html.escape(t.get("style", "normal"))}">{html.escape(t["text"]).replace(chr(10), "<br>")}</td></tr>'
        )

    silence = [c for c in tl.get("cuts", []) if c.get("type") == "silence" and c.get("enabled", True)]
    new_len = sum(e - s for s, e in keeps)
    page = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>チェック: {html.escape(pdir.name)}</title>
<style>
body{{font-family:system-ui,"Hiragino Sans","Yu Gothic",sans-serif;margin:0;background:#f5f5f4;color:#1c1917}}
main{{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:16px;padding:16px;max-width:1500px;margin:auto}}
@media(max-width:900px){{main{{grid-template-columns:1fr}}}}
.player{{position:sticky;top:16px;align-self:start}}
video{{width:100%;max-height:80vh;background:#000;border-radius:8px}}
h1{{font-size:18px;margin:0 0 8px}} h2{{font-size:15px;margin:20px 0 6px}}
.summary{{font-size:14px;color:#57534e}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:#fff;border-radius:8px;overflow:hidden}}
td{{padding:6px 8px;border-bottom:1px solid #e7e5e4;vertical-align:top}}
tr{{cursor:pointer}} tr:hover{{background:#fef3c7}}
tr.hold{{background:#fff7ed}} td.emphasis{{color:#b45309;font-weight:bold}}
.how{{background:#fff;border-radius:8px;padding:10px 12px;font-size:14px;line-height:1.7}}
</style></head><body><main>
<div class="player">
<h1>{html.escape(pdir.name)}</h1>
<video id="v" src="{html.escape(video_name)}" controls></video>
<p class="summary">長さ {fmt_time(tl['duration'])} → {fmt_time(new_len)} ／ 無音カット {len(silence)} か所（合計 {sum(c['end'] - c['start'] for c in silence):.1f}秒）</p>
<div class="how">直したいところがあれば、Claude Code にそのまま日本語で伝えてください。<br>
例：「1:23 のテロップを『〇〇』に直して」「a012 は残して」「2:40〜2:55 はカットして」</div>
</div>
<div>
<h2>カット・保留（無音以外）</h2>
<table>{''.join(rows_cut) or '<tr><td>なし</td></tr>'}</table>
<h2>テロップ</h2>
<table>{''.join(rows_tel) or '<tr><td>なし</td></tr>'}</table>
</div></main>
<script>
const v=document.getElementById('v');
document.querySelectorAll('tr[data-t]').forEach(r=>r.onclick=()=>{{v.currentTime=+r.dataset.t;v.play();}});
</script></body></html>
"""
    (pdir / "review.html").write_text(page, encoding="utf-8")
