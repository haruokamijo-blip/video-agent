"""② 機械的に判断できるカット（無音・フィラー）を timeline.json に書き込む。

使い方:
    python tools/auto_cut.py 案件名

- 何度実行しても大丈夫。自動カット（by: "auto"）だけを作り直し、
  Claude やユーザーが追加したカットはそのまま残す。
- 「あの」「まあ」など意味がある場合もある言葉は enabled: false（保留）で入れる。
  Claude が前後の文脈を見て判断する。
"""
from __future__ import annotations

import argparse
import re

from common import fmt_time, load_config, load_json, project_dir, save_json

STRIP = re.compile(r"[\s、。，,．.！!？?…「」『』]+")


def norm(word: str) -> str:
    return STRIP.sub("", word)


def silence_cuts(silences: list[dict], duration: float, pad: float, min_len: float) -> list[dict]:
    cuts = []
    for s in silences:
        start = 0.0 if s["start"] <= 0.05 else s["start"] + pad
        end = duration if s["end"] >= duration - 0.05 else s["end"] - pad
        if end - start >= min_len - 2 * pad and end > start:
            where = "冒頭の" if start == 0 else "最後の" if end == duration else ""
            cuts.append({"start": round(start, 3), "end": round(end, 3), "type": "silence",
                         "reason": f"{where}無音 {s['end'] - s['start']:.1f}秒", "enabled": True})
    return cuts


def find_fillers(words: list[dict], vocab: set[str]) -> list[tuple[int, int, str]]:
    """フィラーの位置を (開始の単語番号, 単語数, 文字) で返す。
    「え」「ー」のように分かれて出てくることがあるので、2単語つなげても確認する。"""
    found, i = [], 0
    while i < len(words):
        for n in (2, 1):
            text = norm("".join(w["word"] for w in words[i:i + n]))
            if i + n <= len(words) and text in vocab:
                found.append((i, n, text))
                i += n
                break
        else:
            i += 1
    return found


def filler_cuts(segments: list[dict], auto: set[str], ask: set[str]) -> list[dict]:
    words = [w for seg in segments for w in seg["words"]]
    cuts = []
    for i, n, text in find_fillers(words, auto | ask):
        sure = text in auto
        cuts.append({
            "start": round(words[i]["start"], 3),
            "end": round(words[i + n - 1]["end"], 3),
            "type": "filler",
            "reason": f"フィラー「{text}」" if sure else f"フィラーかも「{text}」（意味があるなら残す）",
            "enabled": sure,
        })
    return cuts


def main() -> None:
    ap = argparse.ArgumentParser(description="無音とフィラーを自動カット")
    ap.add_argument("project")
    args = ap.parse_args()

    pdir = project_dir(args.project)
    cfg = load_config()["cut"]
    meta = load_json(pdir / "meta.json")
    tl_path = pdir / "timeline.json"
    timeline = load_json(tl_path) if tl_path.exists() else {
        "source": meta["source"], "duration": meta["duration"],
        "width": meta["width"], "height": meta["height"], "fps": meta["fps"],
        "cuts": [], "telops": [],
    }

    kept = [c for c in timeline["cuts"] if c.get("by") != "auto"]
    auto = silence_cuts(load_json(pdir / "silences.json"), meta["duration"], cfg["padding"], cfg["min_silence"])
    auto += filler_cuts(load_json(pdir / "transcript.json"), set(cfg["fillers_auto"]), set(cfg["fillers_ask"]))
    for n, c in enumerate(sorted(auto, key=lambda c: c["start"]), 1):
        c["id"] = f"a{n:03d}"
        c["by"] = "auto"
    timeline["cuts"] = sorted(kept + auto, key=lambda c: c["start"])
    save_json(tl_path, timeline)

    on = [c for c in auto if c["enabled"]]
    total = sum(c["end"] - c["start"] for c in on)
    print(f"自動カット: {len(on)} か所（合計 {total:.1f}秒）、保留: {len(auto) - len(on)} か所")
    for c in auto:
        if not c["enabled"]:
            print(f"  保留 {c['id']} {fmt_time(c['start'])} {c['reason']}")


if __name__ == "__main__":
    main()
