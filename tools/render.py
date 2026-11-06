"""④ timeline.json のとおりに動画を書き出す（カット＋テロップ）。チェック用ページも作る。

使い方:
    python tools/render.py 案件名            # プレビュー（軽い・速い）→ preview.mp4
    python tools/render.py 案件名 --final    # 本番画質 → final.mp4

あわせて review.html（チェック用ページ）を作る。
"""
from __future__ import annotations

import argparse
import re
import time

from common import (die, fmt_time, keep_segments, load_config, load_json, map_span,
                    project_dir, require_ffmpeg, run)
from review import write_review

STYLES = {"normal", "emphasis"}


def validate(tl: dict) -> None:
    errors = []
    for c in tl.get("cuts", []):
        if not isinstance(c.get("start"), (int, float)) or not isinstance(c.get("end"), (int, float)):
            errors.append(f"カット {c.get('id')} の start/end が数字ではありません")
        elif c["end"] <= c["start"]:
            errors.append(f"カット {c.get('id')} の end が start 以前です")
    for t in tl.get("telops", []):
        if not str(t.get("text", "")).strip():
            errors.append(f"テロップ {t.get('id')} の文字が空です")
        if t.get("style", "normal") not in STYLES:
            errors.append(f"テロップ {t.get('id')} の style は {sorted(STYLES)} のどれかにしてください")
        if not t.get("end", 0) > t.get("start", 0):
            errors.append(f"テロップ {t.get('id')} の end が start 以前です")
    if errors:
        die("timeline.json に問題があります:\n  " + "\n  ".join(errors))


def ass_time(t: float) -> str:
    cs = round(t * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_text(text: str) -> str:
    text = text.replace("\\", "＼").replace("{", "｛").replace("}", "｝")
    return text.replace("\r", "").replace("\n", "\\N")


def write_ass(path, tl: dict, keeps, cfg: dict) -> int:
    w, h = tl["width"], tl["height"]
    size = round(min(w, h) * cfg["size_ratio"])
    outline = max(2, round(size * 0.09))
    shadow = max(1, round(size * 0.04))
    margin_v = round(h * cfg["bottom_margin_ratio"])
    margin_lr = round(w * 0.04)
    font = cfg["font"]

    def style(name, color, scale):
        return (f"Style: {name},{font},{round(size * scale)},{color},&H000000FF,{cfg['outline_color']},"
                f"&H80000000,-1,0,0,0,100,100,0,0,1,{round(outline * scale)},{shadow},2,"
                f"{margin_lr},{margin_lr},{margin_v},1")

    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style("normal", cfg["normal_color"], 1.0),
        style("emphasis", cfg["emphasis_color"], 1.15),
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    count = 0
    for t in sorted(tl.get("telops", []), key=lambda t: t["start"]):
        span = map_span(t["start"], t["end"], keeps)
        if span is None:
            continue  # テロップの区間が丸ごとカットされている
        anim = "{\\fad(60,60)}" if t.get("style") != "emphasis" else "{\\fad(40,60)\\fscx85\\fscy85\\t(0,120,\\fscx100\\fscy100)}"
        lines.append(f"Dialogue: 0,{ass_time(span[0])},{ass_time(span[1])},{t.get('style', 'normal')},,0,0,0,,"
                     f"{anim}{ass_text(t['text'])}")
        count += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def ffmpeg_major() -> int:
    out = run(["ffmpeg", "-version"], capture_output=True).stdout
    m = re.search(r"ffmpeg version n?(\d+)", out)
    return int(m.group(1)) if m else 6


def main() -> None:
    ap = argparse.ArgumentParser(description="動画を書き出す")
    ap.add_argument("project")
    ap.add_argument("--final", action="store_true", help="本番画質で書き出す")
    args = ap.parse_args()

    require_ffmpeg()
    pdir = project_dir(args.project)
    tl = load_json(pdir / "timeline.json")
    validate(tl)
    cfg = load_config()
    rcfg = cfg["render"]

    keeps = keep_segments(tl)
    if not keeps:
        die("全部カットされてしまっています。")
    n_telops = write_ass(pdir / "telops.ass", tl, keeps, cfg["telop"])

    sel = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in keeps)
    v = [f"fps={tl['fps']}", f"select='{sel}'", "setpts=N/FRAME_RATE/TB"]
    if not args.final:
        short = rcfg["preview_short_side"]
        v.append(f"scale=-2:{short}" if tl["width"] >= tl["height"] else f"scale={short}:-2")
    if n_telops:
        v.append("subtitles=telops.ass")
    graph = f"[0:v]{','.join(v)}[v];[0:a]aselect='{sel}',asetpts=N/SR/TB[a]"
    (pdir / "filter.txt").write_text(graph, encoding="utf-8")
    script_opt = "-/filter_complex" if ffmpeg_major() >= 7 else "-filter_complex_script"

    out = "final.mp4" if args.final else "preview.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
           "-i", tl["source"], script_opt, "filter.txt", "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "medium" if args.final else "veryfast",
           "-crf", str(rcfg["final_crf"] if args.final else rcfg["preview_crf"]),
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", rcfg["audio_bitrate"],
           "-movflags", "+faststart", out]

    new_len = sum(e - s for s, e in keeps)
    print(f"書き出し中… {fmt_time(tl['duration'])} → {fmt_time(new_len)}（テロップ {n_telops} 個）")
    t0 = time.time()
    run(cmd, cwd=pdir)
    write_review(pdir, tl, keeps, out)
    print(f"完了（{time.time() - t0:.0f}秒）\n  動画: {pdir / out}\n  チェック用ページ: {pdir / 'review.html'}")


if __name__ == "__main__":
    main()
