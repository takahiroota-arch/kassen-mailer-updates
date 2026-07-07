# yt_frames — YouTube 動画からの静止画（フレーム）抽出ツール

YouTube の動画をダウンロードして、そこから静止画（フレーム）を抜き出すコマンドラインツールです。
一定間隔・毎秒 N 枚・指定時刻ピンポイント・シーン切り替わり検出、の 4 モードに対応しています。

## セットアップ

```bash
# このディレクトリで
python3 -m pip install -r requirements.txt
```

- `yt-dlp` … 動画のダウンロード（必須）
- `ffmpeg` … フレーム抽出。**システムに ffmpeg があればそれを使い、無ければ `imageio-ffmpeg` の同梱バイナリを自動利用します**
  （そのため ffmpeg を別途インストールしなくても動きます）。

## 使い方

```bash
# 5 秒ごとに 1 枚（デフォルト）
python3 yt_frames.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"

# 2 秒ごとに 1 枚、720p 以下でダウンロード、PNG で保存
python3 yt_frames.py URL --interval 2 --max-height 720 --format png

# 1 秒あたり 3 枚
python3 yt_frames.py URL --fps 3

# 指定した時刻だけ抜き出す（00:01:05 と 90 秒地点）
python3 yt_frames.py URL --timestamps 00:01:05 90

# シーンの切り替わりを検出して抜き出す（しきい値 0〜1、小さいほど敏感）
python3 yt_frames.py URL --scene 0.4

# 30〜60 秒の範囲だけを対象に、1 秒ごと
python3 yt_frames.py URL --interval 1 --start 30 --end 60

# フレーム抽出せず、動画そのものをダウンロードするだけ
python3 yt_frames.py URL --download-only
python3 yt_frames.py URL -d --max-height 1080   # 1080p 以下でDLだけ
```

`--download-only`（`-d`）を付けると、フレーム抽出は行わず動画ファイルを（動画タイトルのファイル名で）保存します。
`--max-height` で解像度も指定できます。

抜き出した画像は既定で `./frames/` に保存されます（`-o/--output-dir` で変更可）。

## オプション一覧

| オプション | 説明 | 既定 |
| --- | --- | --- |
| `url` | YouTube 動画の URL（必須） | — |
| `-o, --output-dir` | 出力先ディレクトリ | `./frames` |
| `--interval SEC` | N 秒ごとに 1 枚（抽出モード） | 5 |
| `--fps F` | 1 秒あたり F 枚（抽出モード） | — |
| `--timestamps T...` | 指定時刻のフレームのみ（抽出モード） | — |
| `--scene THRESH` | シーン変化検出 0〜1（抽出モード） | — |
| `--start T` | 対象の開始時刻（例 `30` / `00:00:30`） | 先頭 |
| `--end T` | 対象の終了時刻 | 末尾 |
| `--max-height PX` | ダウンロードする最大解像度（例 720, 1080） | 最高画質 |
| `--format {jpg,png}` | 画像フォーマット | jpg |
| `--quality 0-100` | 画質（大きいほど高画質） | 90 |
| `--keep-video` | ダウンロードした動画を削除せず残す | 削除する |
| `-d, --download-only` | フレーム抽出せず動画のダウンロードだけ行う | オフ |

`--interval` / `--fps` / `--timestamps` / `--scene` はいずれか 1 つだけ指定できます（未指定なら `--interval 5`）。

## 仕組み

1. `yt-dlp` で動画をダウンロード（`--max-height` 指定時はその解像度以下を選択）
2. `ffmpeg` の映像フィルタでフレームを抽出
   - 間隔指定 → `fps=1/SEC`
   - 毎秒指定 → `fps=F`
   - シーン検出 → `select='gt(scene,THRESH)'`
   - 時刻指定 → `-ss` で各時刻を 1 枚ずつ切り出し
3. 一時ダウンロードファイルは既定で削除（`--keep-video` で保持）

## 注意

- YouTube の利用規約・著作権に従い、ダウンロード権のあるコンテンツのみを対象にしてください。
- 動画によっては年齢制限・地域制限等でダウンロードできない場合があります。
