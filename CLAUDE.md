# 動画編集AIエージェント

動画素材を渡すと、不要部分のカットとテロップ入れを行い、チェック用のプレビューを作る。
手順は `.claude/skills/edit-video/SKILL.md` に従う。

## 大事な決まり
- **編集内容はすべて `projects/<案件>/timeline.json` に書く。** 動画を直接いじらない。
  書き出しは `tools/render.py` が timeline.json のとおりに行う。
- timeline.json の時間は**元動画の秒数**。カット後の時間ではない。
- ユーザーは技術者ではない。説明は短く、やさしい日本語で。
- 動画・音声ファイル（projects/ の中身）は Git に入れない（.gitignore 済み）。

## ファイル
| ファイル | 役割 |
|---|---|
| `tools/analyze.py` | ① 解析（動画情報・無音・文字起こし） |
| `tools/auto_cut.py` | ② 無音・フィラーの自動カット |
| `tools/make_telops.py` | ③ テロップの下書き |
| `tools/render.py` | 書き出し（プレビュー / 本番）と review.html |
| `tools/review.py` | チェック用ページの作成 |
| `config.json` | 文字起こしモデル、無音の基準、テロップの見た目など |

## timeline.json の形
```json
{
  "source": "元動画の場所", "duration": 600.0, "width": 1920, "height": 1080, "fps": 30.0,
  "cuts":   [{"id": "a001", "start": 1.2, "end": 2.0, "type": "silence|filler|retake|offtopic|other",
              "reason": "理由", "enabled": true, "by": "auto|claude|user"}],
  "telops": [{"id": "t001", "start": 3.0, "end": 5.5, "text": "1行目\n2行目", "style": "normal|emphasis"}]
}
```

## 今後追加する予定
BGM（音量の自動調整つき）、図解、編集ソフト（Premiere / DaVinci）への書き出し。
