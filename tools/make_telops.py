"""③ 文字起こしからテロップの下書きを作って timeline.json に入れる。

使い方:
    python tools/make_telops.py 案件名 [--force]

- 文の切れ目と文字数で区切り、画面に収まるよう改行を入れる。
- フィラー（えー等）はテロップから除く。
- できるのは「下書き」。誤字の修正・言い回しの調整・強調の指定は Claude が行う。
- すでにテロップがある場合は上書きしない（--force で作り直し）。
"""
from __future__ import annotations

import argparse
import math
import re

from auto_cut import find_fillers
from common import die, load_config, load_json, project_dir, save_json

SENTENCE_END = re.compile(r"[。！？!?]$")


def line_chars(width: int, height: int, ratio: float) -> int:
    size = min(width, height) * ratio
    return max(8, math.floor(width * 0.9 / size))


def wrap(pieces: list[str], max_chars: int) -> str:
    """長ければ2行に分ける。単語の切れ目のうち、読点の直後 → 真ん中に近い所 の順に選ぶ。"""
    text = "".join(pieces)
    if len(text) <= max_chars:
        return text
    bounds, pos = [], 0
    for p in pieces[:-1]:
        pos += len(p)
        bounds.append(pos)
    ok = [b for b in bounds if b <= max_chars and len(text) - b <= max_chars] or bounds or [len(text) // 2]
    mid = len(text) / 2
    after_comma = [b for b in ok if text[b - 1] in "、，,"]
    cut = min(after_comma or ok, key=lambda b: abs(b - mid))
    return text[:cut] + "\n" + text[cut:]


def build(segments: list[dict], fillers: set[str], max_chars: int, max_lines: int) -> list[dict]:
    limit = max_chars * max_lines
    words = [w for seg in segments for w in seg["words"]]
    drop = {i + k for i, n, _ in find_fillers(words, fillers) for k in range(n)}
    words = [w for i, w in enumerate(words) if i not in drop]

    def length(ws):
        return sum(len(re.sub(r"\s+", "", w["word"])) for w in ws)

    chunks: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur and (length(cur + [w]) > limit or w["start"] - cur[-1]["end"] > 1.0):
            chunks.append(cur)
            cur = []
        cur.append(w)
        word = w["word"].strip()
        # 文末、または1行分を超えたところの読点で区切る
        if SENTENCE_END.search(word) or (re.search(r"[、，,]$", word) and length(cur) >= max_chars):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)

    telops = []
    for ch in chunks:
        pieces = [re.sub(r"\s+", "", w["word"]) for w in ch]
        pieces = [p for p in pieces if p]
        # 先頭の読点・末尾の句読点を落とす
        if pieces:
            pieces[0] = pieces[0].lstrip("、，,")
            pieces[-1] = pieces[-1].rstrip("。、，,")
        pieces = [p for p in pieces if p]
        if not pieces:
            continue
        telops.append({"start": round(ch[0]["start"], 3), "end": round(ch[-1]["end"], 3),
                       "text": wrap(pieces, max_chars), "style": "normal"})
    # 読みやすいよう、次のテロップまで少しだけ長く表示する
    for i, t in enumerate(telops):
        nxt = telops[i + 1]["start"] if i + 1 < len(telops) else t["end"] + 0.5
        t["end"] = round(max(t["end"], min(nxt, t["end"] + 0.5, t["start"] + 0.8)), 3)
        t["id"] = f"t{i + 1:03d}"
    return telops


def main() -> None:
    ap = argparse.ArgumentParser(description="テロップの下書きを作る")
    ap.add_argument("project")
    ap.add_argument("--force", action="store_true", help="既存のテロップを作り直す")
    args = ap.parse_args()

    pdir = project_dir(args.project)
    tl_path = pdir / "timeline.json"
    if not tl_path.exists():
        die("timeline.json がありません。先に auto_cut.py を実行してください。")
    timeline = load_json(tl_path)
    if timeline.get("telops") and not args.force:
        print(f"テロップは既に {len(timeline['telops'])} 個あります（作り直すなら --force）。")
        return

    cfg = load_config()
    tcfg = cfg["telop"]
    max_chars = line_chars(timeline["width"], timeline["height"], tcfg["size_ratio"])
    fillers = set(cfg["cut"]["fillers_auto"])
    timeline["telops"] = build(load_json(pdir / "transcript.json"), fillers, max_chars, tcfg["max_lines"])
    timeline["telop_max_chars_per_line"] = max_chars
    save_json(tl_path, timeline)
    print(f"テロップ下書き: {len(timeline['telops'])} 個（1行 最大{max_chars}文字）")


if __name__ == "__main__":
    main()
