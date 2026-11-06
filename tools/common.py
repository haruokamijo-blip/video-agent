"""共通の小道具：設定の読み込み、ffprobe、時間の変換、カット区間の計算など。

時間はすべて「元動画の秒数」で扱う。カット後の時間への変換はレンダリング時に行う。
こうしておくと、カットを後から変えてもテロップの位置がずれない。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"


def die(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            die(f"{tool} が見つかりません。README の「準備」を見て ffmpeg を入れてください。")


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_config() -> dict:
    return load_json(ROOT / "config.json")


def project_dir(arg: str) -> Path:
    """'projects/abc' でも 'abc' でも受け付ける。"""
    p = Path(arg)
    if not p.is_dir():
        p = PROJECTS / arg
    if not (p / "meta.json").exists():
        die(f"プロジェクト {arg} が見つかりません（先に analyze.py を実行してください）。")
    return p


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, encoding="utf-8", errors="replace", **kw)


def probe(video: Path) -> dict:
    out = run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(video)],
        capture_output=True,
    ).stdout
    info = json.loads(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        die("映像トラックがありません。")
    if a is None:
        die("音声トラックがありません。")
    w, h = int(v["width"]), int(v["height"])
    # スマホ動画は回転情報付きのことが多い。ffmpeg は自動で回すので幅と高さを入れ替える。
    rotation = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(float(sd["rotation"]))
    if "rotate" in v.get("tags", {}):
        rotation = int(v["tags"]["rotate"])
    if abs(rotation) % 180 == 90:
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    if not 1 <= fps <= 240:
        fps = 30.0
    return {
        "width": w,
        "height": h,
        "fps": round(fps, 3),
        "duration": float(info["format"]["duration"]),
    }


def fmt_time(t: float) -> str:
    """秒 → 'm:ss.s'（人が読む用）"""
    t = max(0.0, t)
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:04.1f}"


def merged_cuts(timeline: dict) -> list[tuple[float, float]]:
    """有効なカットを並べ替えて、重なりをまとめる。"""
    dur = timeline["duration"]
    spans = sorted(
        (max(0.0, c["start"]), min(dur, c["end"]))
        for c in timeline.get("cuts", [])
        if c.get("enabled", True) and c["end"] > c["start"]
    )
    merged: list[list[float]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1] + 0.05:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged if e - s > 0.01]


def keep_segments(timeline: dict) -> list[tuple[float, float]]:
    """カットされずに残る区間（元動画の時間）。"""
    keeps, pos = [], 0.0
    for s, e in merged_cuts(timeline):
        if s > pos:
            keeps.append((pos, s))
        pos = max(pos, e)
    if timeline["duration"] > pos:
        keeps.append((pos, timeline["duration"]))
    return [(s, e) for s, e in keeps if e - s > 0.05]


def to_output_time(t: float, keeps: list[tuple[float, float]]) -> float | None:
    """元動画の時間 → カット後の時間。カットされた所なら None。"""
    acc = 0.0
    for s, e in keeps:
        if t < s:
            return None
        if t <= e:
            return acc + (t - s)
        acc += e - s
    return None


def map_span(start: float, end: float, keeps: list[tuple[float, float]]) -> tuple[float, float] | None:
    """区間を出力の時間に写す。両端がカット内なら残る部分に寄せる。"""
    acc, out_s, out_e = 0.0, None, None
    for s, e in keeps:
        lo, hi = max(start, s), min(end, e)
        if lo < hi:
            if out_s is None:
                out_s = acc + (lo - s)
            out_e = acc + (hi - s)
        acc += e - s
    if out_s is None or out_e - out_s < 0.2:
        return None
    return out_s, out_e
