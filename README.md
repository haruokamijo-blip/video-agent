# 動画編集AIエージェント

動画を渡すと、Claude Code が次の作業をしてくれます。

1. **不要部分のカット**：無音、「えー」「あのー」、言い直し、脱線
2. **テロップ入れ**：文字起こしから作り、誤字を直し、大事なところは強調
3. **チェック用ページ**：どこを切ったか（理由つき）とテロップの一覧を、動画と並べて表示
4. 直してほしいところを日本語で伝えると修正し、OKなら本番画質で書き出し

> BGM と図解は、今後追加する予定です。

---

## 準備（パソコンで最初の1回だけ）

### かんたんな方法：Claude Code に準備してもらう
1. パソコンに **Claude Code** を入れます。Claude のデスクトップアプリの「Code」からも使えます。
2. Claude Code に次のように頼みます。
   > https://github.com/haruokamijo-blip/video-agent をダウンロードして、README の「準備」に書いてあるものをこのパソコンに入れて

### 自分でやる場合
必要なものは次の4つです。

| 必要なもの | Windows | Mac |
|---|---|---|
| Python 3.10 以上 | https://www.python.org からインストール（「Add python.exe to PATH」にチェック） | `brew install python` |
| ffmpeg | `winget install Gyan.FFmpeg` | `brew install ffmpeg` |
| Git | `winget install Git.Git` | `brew install git` |
| 日本語フォント Noto Sans JP | https://fonts.google.com/noto/specimen/Noto+Sans+JP からダウンロードしてインストール | 同じ |

入れ終わったら、ターミナル（Windows は PowerShell）で次を実行します。
```
git clone https://github.com/haruokamijo-blip/video-agent.git
cd video-agent
pip install -r requirements.txt
```

---

## 使い方

1. `video-agent` フォルダで Claude Code を開きます。
2. 次のように頼みます。
   ```
   /edit-video C:\Users\あなた\Videos\素材.mp4
   ```
   ファイル名を書かずに「デスクトップの 素材.mp4 を編集して」と頼んでも大丈夫です。
3. しばらく待つと、`projects/素材/review.html` ができます。ダブルクリックするとブラウザで開きます。
4. 直してほしいところを、そのまま日本語で伝えます。
   - 「1:23 のテロップを『〇〇』に直して」
   - 「2:40〜2:55 もカットして」
   - 「保留になっているところは全部カットでいい」
5. OK なら「完成させて」と伝えます。→ `projects/素材/final.mp4` が完成品です。

### 時間の目安
最初の文字起こしに時間がかかります。10分の動画で、パソコンの性能によって5〜20分ほどです。
初回だけ、文字起こしAI（約1.5GB）のダウンロードも入ります。

---

## 好みに合わせて変える（config.json）

| 項目 | 意味 | 初期値 |
|---|---|---|
| `cut.min_silence` | この秒数以上の無音をカット | 0.6 |
| `cut.padding` | カットの前後に残す余白（秒） | 0.15 |
| `cut.fillers_auto` | 必ずカットする口癖 | えー、えっと など |
| `telop.font` | テロップのフォント | Noto Sans JP |
| `telop.size_ratio` | 文字の大きさ（画面に対する割合） | 0.058 |
| `whisper.model` | 文字起こしAI。遅いパソコンなら `small` にすると速くなる（精度は下がる） | large-v3-turbo |

Claude Code に「無音カットをもう少し控えめにして」のように頼んでも、変えてくれます。

---

## しくみ（参考）

```
素材.mp4 → [解析] 文字起こし・無音検出
         → [カット] 無音・口癖は自動 ＋ 言い直し・脱線は Claude が判断
         → [テロップ] 下書きを自動で作成 → Claude が誤字修正・強調
         → timeline.json（編集指示書）
         → [書き出し] ffmpeg → preview.mp4 + review.html
```
動画そのものは直接いじらず、`timeline.json`（どこを切るか、どのテロップを出すか）だけを書き換えます。
そのため、何度でもやり直せます。
動画ファイルは自分のパソコンの中だけで処理され、GitHub には上がりません。
