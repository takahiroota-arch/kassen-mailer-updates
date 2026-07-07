#!/usr/bin/env python3
"""yt_frames — YouTube 動画をダウンロードして静止画（フレーム）を抜き出す CLI ツール.

依存:
    - yt-dlp        … 動画のダウンロード（必須）
    - ffmpeg        … フレーム抽出（システムに無ければ imageio-ffmpeg の同梱バイナリを使用）

使い方の例:
    # 5 秒ごとに 1 枚抜き出す（デフォルト）
    python yt_frames.py "https://www.youtube.com/watch?v=XXXX"

    # 2 秒ごとに 1 枚、720p 以下でダウンロード、PNG で保存
    python yt_frames.py URL --interval 2 --max-height 720 --format png

    # 1 秒あたり 3 枚
    python yt_frames.py URL --fps 3

    # 指定した時刻のフレームだけ（00:01:05 と 90 秒地点）
    python yt_frames.py URL --timestamps 00:01:05 90

    # シーン切り替わりを検出して抜き出す
    python yt_frames.py URL --scene 0.4

    # 30〜60 秒の範囲だけを対象に
    python yt_frames.py URL --interval 1 --start 30 --end 60
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


# --------------------------------------------------------------------------- #
# 依存解決
# --------------------------------------------------------------------------- #
def find_ffmpeg() -> str:
    """ffmpeg の実行パスを返す。システムに無ければ imageio-ffmpeg にフォールバック。"""
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit(
            "エラー: ffmpeg が見つかりません。\n"
            "  次のいずれかで用意してください:\n"
            "    - システムに ffmpeg をインストール（例: brew install ffmpeg / apt install ffmpeg）\n"
            "    - もしくは  pip install imageio-ffmpeg  （同梱バイナリを自動利用）"
        )


def require_yt_dlp():
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        sys.exit(
            "エラー: yt-dlp が見つかりません。\n"
            "  次でインストールしてください:  pip install yt-dlp"
        )


# --------------------------------------------------------------------------- #
# ダウンロード
# --------------------------------------------------------------------------- #
def download_video(url: str, workdir: Path, max_height: int | None, ffmpeg_dir: str) -> tuple[Path, str]:
    """動画をダウンロードして (ファイルパス, タイトル) を返す。"""
    import yt_dlp

    if max_height:
        fmt = f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best"
    else:
        fmt = "bestvideo+bestaudio/best"

    outtmpl = str(workdir / "%(id)s.%(ext)s")
    ydl_opts = {
        "format": fmt,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # imageio-ffmpeg のバイナリを使う場合、そのディレクトリを yt-dlp に伝える
        "ffmpeg_location": str(Path(ffmpeg_dir).parent),
    }

    print(f"⏬ ダウンロード中: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = Path(ydl.prepare_filename(info))
        # merge で拡張子が変わることがあるので実ファイルを探す
        if not filepath.exists():
            candidates = list(workdir.glob(f"{info['id']}.*"))
            if candidates:
                filepath = candidates[0]
    title = info.get("title", info.get("id", "video"))
    print(f"✅ ダウンロード完了: {filepath.name}  ({title})")
    return filepath, title


# --------------------------------------------------------------------------- #
# フレーム抽出
# --------------------------------------------------------------------------- #
def _safe_name(title: str) -> str:
    keep = "-_. "
    cleaned = "".join(c if (c.isalnum() or c in keep) else "_" for c in title).strip()
    return (cleaned or "video")[:80]


def extract_frames(
    ffmpeg: str,
    video: Path,
    outdir: Path,
    title: str,
    *,
    interval: float | None,
    fps: float | None,
    timestamps: list[str] | None,
    scene: float | None,
    start: str | None,
    end: str | None,
    img_format: str,
    quality: int,
) -> int:
    """ffmpeg でフレームを抽出し、生成枚数を返す。"""
    outdir.mkdir(parents=True, exist_ok=True)
    prefix = _safe_name(title)
    ext = img_format
    # jpg の品質 (2=高品質〜31=低品質) / png の圧縮率 (0〜9) を quality から算出
    quality_args: list[str]
    if img_format in ("jpg", "jpeg"):
        q = max(2, min(31, 33 - int(quality / 100 * 31)))  # quality 0-100 → qscale 31-2
        quality_args = ["-qscale:v", str(q)]
    else:  # png
        comp = max(0, min(9, 9 - int(quality / 100 * 9)))
        quality_args = ["-compression_level", str(comp)]

    # --- 個別タイムスタンプ指定モード ------------------------------------- #
    if timestamps:
        count = 0
        for i, ts in enumerate(timestamps, 1):
            out = outdir / f"{prefix}_t{i:03d}.{ext}"
            cmd = [ffmpeg, "-y", "-ss", ts, "-i", str(video), "-frames:v", "1", *quality_args, str(out)]
            _run(cmd)
            if out.exists():
                count += 1
                print(f"  🖼  {out.name}  (@{ts})")
        return count

    # --- vf フィルタ構築（interval / fps / scene） ------------------------ #
    trim: list[str] = []
    if start is not None:
        trim += ["-ss", start]
    if end is not None:
        trim += ["-to", end]

    if scene is not None:
        vf = f"select='gt(scene,{scene})',showinfo"
        vsync = ["-vsync", "vfr"]
    elif fps is not None:
        vf = f"fps={fps}"
        vsync = []
    else:
        # interval（デフォルト 5 秒）→ fps=1/interval
        iv = interval if interval is not None else 5.0
        vf = f"fps=1/{iv}"
        vsync = []

    pattern = str(outdir / f"{prefix}_%04d.{ext}")
    cmd = [ffmpeg, "-y", *trim, "-i", str(video), "-vf", vf, *vsync, *quality_args, pattern]
    _run(cmd)

    produced = sorted(outdir.glob(f"{prefix}_*.{ext}"))
    return len(produced)


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-2000:] + "\n")
        sys.exit(f"エラー: ffmpeg の実行に失敗しました (exit {result.returncode})")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="yt_frames",
        description="YouTube 動画をダウンロードして静止画（フレーム）を抜き出します。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("url", help="YouTube 動画の URL")
    p.add_argument("-o", "--output-dir", default="frames", help="出力先ディレクトリ (既定: ./frames)")

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--interval", type=float, metavar="SEC", help="N 秒ごとに 1 枚抜き出す (既定: 5)")
    mode.add_argument("--fps", type=float, metavar="F", help="1 秒あたり F 枚抜き出す")
    mode.add_argument("--timestamps", nargs="+", metavar="T", help="指定した時刻のフレームだけ (例: 00:01:05 90)")
    mode.add_argument("--scene", type=float, metavar="THRESH", help="シーン変化を検出して抜き出す (0〜1, 例 0.4)")

    p.add_argument("--start", metavar="T", help="この時刻以降だけを対象 (例: 30 または 00:00:30)")
    p.add_argument("--end", metavar="T", help="この時刻まで対象 (例: 60 または 00:01:00)")

    p.add_argument("--max-height", type=int, metavar="PX", help="ダウンロードする最大解像度 (例: 720, 1080)")
    p.add_argument("--format", choices=["jpg", "png"], default="jpg", help="画像フォーマット (既定: jpg)")
    p.add_argument("--quality", type=int, default=90, metavar="0-100", help="画質 0〜100 (既定: 90)")
    p.add_argument("--keep-video", action="store_true", help="ダウンロードした動画ファイルを削除せず残す")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    require_yt_dlp()
    ffmpeg = find_ffmpeg()

    outdir = Path(args.output_dir).expanduser().resolve()
    workdir = outdir / ".video"
    workdir.mkdir(parents=True, exist_ok=True)

    video, title = download_video(args.url, workdir, args.max_height, ffmpeg)

    print("✂️  フレーム抽出中 ...")
    n = extract_frames(
        ffmpeg,
        video,
        outdir,
        title,
        interval=args.interval,
        fps=args.fps,
        timestamps=args.timestamps,
        scene=args.scene,
        start=args.start,
        end=args.end,
        img_format=args.format,
        quality=args.quality,
    )

    if not args.keep_video:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"🎬 動画を保持: {video}")

    print(f"\n🎉 完了: {n} 枚のフレームを保存しました → {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
