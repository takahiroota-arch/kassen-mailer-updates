# KASSEN MAILER — 更新配信マニフェスト

このリポジトリは **KASSEN MAILER（社内メーラー）のアップデート通知**に使う小さな公開マニフェストです。
`latest.json` に「最新版のバージョン・ダウンロードリンク・更新メモ」だけを置きます。
**秘密情報（APIキー等）やアプリ本体（zip）はここには置きません。**

アプリは起動時とⓘ設定→アップデート確認で、次のURLを読みに来ます:
`https://raw.githubusercontent.com/takahiroota-arch/kassen-mailer-updates/main/latest.json`

## 新しい版を配布する手順（管理者）
1. `~/Desktop/kassen-mail` で `package.json` の `version` を上げる
2. `npm run dist` → 配布zip `dist/KASSEN-MAILER-mac-arm64.zip` を作成（手順は INSTALL.md）
3. その zip を **kassen.tokyo 限定共有の Google ドライブ**にアップロードし、共有リンクを取得
   - 直接ダウンロードにしたい場合: `https://drive.google.com/uc?export=download&id=<FILE_ID>` 形式のリンクにする
4. この `latest.json` を編集して push:
   - `version` … 手順1で上げた番号（例 `0.3.0`）
   - `url` … 手順3のダウンロードリンク
   - `notes` … 変更点の要約（設定画面と通知に表示される）
5. 各メンバーのアプリが次回起動時／アップデート確認時に検知し、
   「新しいバージョンがあります」と通知＋ダウンロードリンクを表示します

> ⚠️ zip にはAnthropicキーが埋め込まれる（抽出可能）ため、**必ずアクセス制御下（Drive限定共有）**に置き、公開URLには置かないこと。
