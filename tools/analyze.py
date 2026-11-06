"""① 動画を解析する：動画情報・無音区間・文字起こし（単語ごとの時間つき）。

使い方:
    python tools/analyze.py 素材.mp4 [--name 案件名] [--model large-v3-turbo]

結果は projects/<案件名>/ に保存される:
    meta.json        動画の情報（元ファイルの場所、解像度、長さ）
    silences.json    無音区間
    transcript.json  文字起こし（単語ごとの時間つき）
    transcript.txt   文字起こし（人とClaudeが読む用）
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from common import PROJECTS, die, fmt_time, load_config, probe, require_ffmpeg, run, save_json


def detect_silences(audio: Path, db: float, min_len: float) -> list[dict]:
    res = run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio),
         "-af", f"silencedetect=noise={db}dB:d={min_len}", "-f", "null", "-"],
        capture_output=True,
    )
    silences, start = [], None
    for line in res.stderr.splitlines():
        if m := re.search(r"silence_start: (-?[\d.]+)", line):
            start = max(0.0, float(m.group(1)))
        elif (m := re.search(r"silence_end: ([\d.]+)", line)) and start is not None:
            silences.append({"start": round(start, 3), "end": round(float(m.group(1)), 3)})
            start = None
    return silences


def transcribe(audio: Path, cfg: dict, model_name: str) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die("faster-whisper が入っていません。`pip install -r requirements.txt` を実行してください。")

    print(f"文字起こしモデル {model_name} を読み込み中…（初回はダウンロードに数分かかります）")
    model = WhisperModel(model_name, device=cfg["device"], compute_type=cfg["compute_type"])
    segments, _ = model.transcribe(
        str(audio),
        language=cfg["language"],
        word_timestamps=True,
        vad_filter=False,  # 「えー」なども拾いたいので VAD は使わない
        initial_prompt=cfg.get("initial_prompt") or None,
        condition_on_previous_text=False,  # 同じ文の繰り返し（幻覚）を減らす
    )
    out = []
    for seg in segments:
        words = [
            {"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word}
            for w in (seg.words or [])
        ]
        out.append({
            "id": len(out) + 1,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "words": words,
        })
        print(f"  [{fmt_time(seg.start)}] {seg.text.strip()}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="動画を解析する")
    ap.add_argument("video")
    ap.add_argument("--name", help="案件名（省略時はファイル名）")
    ap.add_argument("--model", help="Whisper モデル名（config.json の設定を上書き）")
    args = ap.parse_args()

    require_ffmpeg()
    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        die(f"{video} が見つかりません。")
    cfg = load_config()
    name = args.name or re.sub(r"[^\w\-]+", "_", video.stem)
    pdir = PROJECTS / name
    pdir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    meta = {"name": name, "source": str(video), **probe(video)}
    save_json(pdir / "meta.json", meta)
    print(f"動画: {meta['width']}x{meta['height']} / {fmt_time(meta['duration'])} / {meta['fps']}fps")

    audio = pdir / "audio.wav"
    print("音声を取り出し中…")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video),
         "-vn", "-ac", "1", "-ar", "16000", str(audio)])

    c = cfg["cut"]
    silences = detect_silences(audio, c["silence_db"], c["min_silence"])
    save_json(pdir / "silences.json", silences)
    print(f"無音区間: {len(silences)} か所")

    segments = transcribe(audio, cfg["whisper"], args.model or cfg["whisper"]["model"])
    save_json(pdir / "transcript.json", segments)
    with open(pdir / "transcript.txt", "w", encoding="utf-8") as f:
        for s in segments:
            f.write(f"#{s['id']} [{s['start']:.2f}-{s['end']:.2f}] {s['text']}\n")

    print(f"\n完了（{time.time() - t0:.0f}秒）→ {pdir}")


if __name__ == "__main__":
    main()
