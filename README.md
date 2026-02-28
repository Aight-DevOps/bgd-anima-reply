# Anima Reply Bot

Airtable に蓄積された X（旧 Twitter）の相互フォロワーへのリプライドラフトを取得し、Playwright を使って自動返信するボットです。

---

## 目次

1. [仕組みの概要](#仕組みの概要)
2. [前提条件](#前提条件)
3. [Airtable テーブル構造](#airtable-テーブル構造)
4. [インストール](#インストール)
5. [設定](#設定)
6. [初回セットアップ（X へのログイン）](#初回セットアップx-へのログイン)
7. [手動実行](#手動実行)
8. [スケジュール自動実行](#スケジュール自動実行)
9. [ファイル構成](#ファイル構成)
10. [ログの確認](#ログの確認)
11. [トラブルシューティング](#トラブルシューティング)

---

## 仕組みの概要

```
Airtable
[STG]ANIMA-WORK-REPLY
  ApproveCheck = ✓
  ReplyStatus  = Draft
  GeneratedDate = 当日
        ↓
anima_reply.py
  ① Airtable からレコード取得
  ② 保存済み認証状態で Playwright Chromium 起動
  ③ ReplyLink (intent/post URL) に遷移
  ④ ReplyDraft を人間らしいタイピングで入力
  ⑤ 送信
  ⑥ ReplyStatus を Complete に更新
        ↓
scheduler.py
  毎日 09:00〜22:00、30分ごとに ① を繰り返す
```

**ボット検知対策として：**
- ページ読み込み後 5〜10秒 のランダム待機
- 1文字ずつ 0.1〜0.3秒 のランダムタイピング
- 送信前 2〜4秒 のランダム待機
- 次のリプライまで **60〜120秒** のランダムインターバル

---

## 前提条件

| 必要なもの | バージョン |
|---|---|
| Python | 3.10 以上 |
| Google Chrome | インストール済み（任意のバージョン） |
| Airtable アカウント | Personal Access Token 取得済み |
| X（Twitter）アカウント | Chrome でログイン済み |

---

## Airtable テーブル構造

対象テーブル名：**`[STG]ANIMA-WORK-REPLY`**

| フィールド名 | 型 | 用途 |
|---|---|---|
| `ApproveCheck` | チェックボックス | ✓ のレコードだけを処理対象にする |
| `ReplyStatus` | テキスト | `Draft` → 処理待ち / `Complete` → 送信済み / `SKIP` → スキップ |
| `ReplyLink` | URL | `https://x.com/intent/post?in_reply_to=...&text=...` 形式のリプライ URL |
| `ReplyDraft` | テキスト | 送信するリプライ本文 |
| `GeneratedDate` | 日時 | レコード生成日時（当日フィルタに使用） |

### ReplyStatus の遷移

```
Draft ──→ Complete  （送信成功）
      └──→ SKIP      （投稿削除 / 入力欄なし / 本文・URLが空）
```

---

## インストール

```bash
# 1. リポジトリをクローン
git clone <このリポジトリの URL>
cd bgd-anima-reply

# 2. 依存パッケージをインストール
pip install pyairtable playwright schedule python-dotenv

# 3. Playwright 用 Chromium をインストール
playwright install chromium
```

---

## 設定

`.env.example` をコピーして `.env` を作成し、実際の値を入力します。

```bash
cp .env.example .env
```

```ini
# .env
AIRTABLE_TOKEN=patXXXXXXXXXXXXXX.XXXXXXXX...   # Airtable Personal Access Token
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX             # Airtable Base ID
```

> `.env` は `.gitignore` に含まれているため、Git にはコミットされません。

### Airtable Personal Access Token の取得

1. [Airtable](https://airtable.com) にログイン
2. 右上のアバター → **Developer Hub**
3. **Personal access tokens** → **Create new token**
4. スコープに `data.records:read` `data.records:write` を付与
5. 使用する Base を選択してトークンを生成

### Airtable Base ID の確認

Airtable の Base を開いたときの URL から確認できます。

```
https://airtable.com/appXXXXXXXXXXXXXX/...
                     ^^^^^^^^^^^^^^^^^ ← これが Base ID
```

---

## 初回セットアップ（X へのログイン）

Chrome の Cookie は暗号化されているため直接読み取れません。
代わりに **Playwright のブラウザで X に手動ログインし、その認証状態を保存**します。

```bash
python anima_reply.py --setup-auth
```

1. ブラウザが開き、X のログインページが表示されます
2. 通常通りログインします
3. ホーム画面が表示されると**自動的に認証状態を保存**してブラウザが閉じます
4. `auth_state.json` が生成されます（**Git には含めないこと**）

> **再ログインが必要なタイミング**
> X のセッションが切れたり、ログイン状態が無効になると SKIP が続くようになります。
> その際は `--setup-auth` を再実行してください。

---

## 手動実行

```bash
# 今日のデータを全件処理（ヘッドレス）
python anima_reply.py --today

# 今日のデータを1件だけテスト（ブラウザ表示あり）
python anima_reply.py --today --limit 1 --visible

# 全期間のデータを処理（日付フィルターなし）
python anima_reply.py
```

### オプション一覧

| オプション | 説明 |
|---|---|
| `--today` | GeneratedDate が当日 (JST) のレコードのみ対象 |
| `--limit N` | 処理件数を N 件に制限（テスト用） |
| `--visible` | ブラウザを表示して実行（デバッグ用） |
| `--setup-auth` | 初回ログイン・認証状態の保存 |

---

## スケジュール自動実行

### 起動方法

```bash
python scheduler.py
```

- 毎日 **09:00〜22:00** の間、**30分ごと**に `anima_reply.py --today` を実行します
- 時間帯外は何もしません
- 前回の実行がまだ終わっていない場合はスキップします
- ログは `task_log.txt` に追記されます

### Windows 起動時に自動起動させる（Windows のみ）

```powershell
# PowerShell で実行
powershell -ExecutionPolicy Bypass -Command "
\$WshShell = New-Object -ComObject WScript.Shell
\$Shortcut = \$WshShell.CreateShortcut((Join-Path ([System.Environment]::GetFolderPath('Startup')) 'AnimaReplyBot.lnk'))
\$Shortcut.TargetPath       = 'C:\Users\<ユーザー名>\AppData\Local\Programs\Python\Python312\python.exe'
\$Shortcut.Arguments        = 'C:\<リポジトリのパス>\scheduler.py'
\$Shortcut.WorkingDirectory = 'C:\<リポジトリのパス>'
\$Shortcut.WindowStyle      = 7
\$Shortcut.Save()
Write-Host '登録完了'
"
```

> **Python の実行パス確認方法**
> `where python` をターミナルで実行すると表示されます

登録を解除するには：

```powershell
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AnimaReplyBot.lnk"
```

---

## ファイル構成

```
bgd-anima-reply/
│
├── anima_reply.py          # メインスクリプト
├── scheduler.py            # スケジューラ（30分サイクル実行）
├── register_startup.ps1    # Windows スタートアップ登録スクリプト
├── run_bot.bat             # Windows タスクスケジューラ用ラッパー（代替方式）
├── setup_task.ps1          # Windows タスクスケジューラ登録スクリプト（代替方式）
├── setup.sh                # Linux/Mac 向けセットアップスクリプト
├── .gitignore
├── README.md
│
├── auth_state.json         # ← 自動生成（Git に含めない）
└── task_log.txt            # ← 自動生成（Git に含めない）
```

### タスクスケジューラ方式（代替）

`scheduler.py` を常駐させる代わりに、Windows のタスクスケジューラから `run_bot.bat` を定期実行する方式も使えます。

```powershell
# PowerShell（管理者権限）で実行
powershell -ExecutionPolicy Bypass -File setup_task.ps1
```

---

## ログの確認

```bash
# 最新のログを確認
tail -30 task_log.txt

# リアルタイムで監視
# （Git Bash / PowerShell）
Get-Content task_log.txt -Wait -Tail 20
```

ログの見方：

```
[2026-02-28 09:30:00] ==================================================
[2026-02-28 09:30:00] ボット起動
...
  ✓ リプライ送信完了
  → Airtable 更新: Complete  (recXXXXXXXXXXXXXX)
...
[2026-02-28 09:35:00] ボット終了
[2026-02-28 10:00:00] ボット起動
  対象レコードが見つかりません（ApproveCheck=ON & ReplyStatus=Draft）。
[2026-02-28 10:00:00] ボット終了
```

---

## トラブルシューティング

### ログインページにリダイレクトされる（SKIP が続く）

X のセッションが切れています。再ログインが必要です。

```bash
python anima_reply.py --setup-auth
```

### `auth_state.json` が見つからない

初回セットアップが未実施です。

```bash
python anima_reply.py --setup-auth
```

### `No module named 'pyairtable'` などのエラー

依存パッケージが未インストールです。

```bash
pip install pyairtable playwright schedule
playwright install chromium
```

### 送信ボタンが見つからない（SKIP になる）

- リプライ先のポストが削除されている → 仕様通り SKIP になります
- X の UI が変わった可能性があります。`--visible` で実際の画面を確認してください

```bash
python anima_reply.py --today --limit 1 --visible
```

### scheduler.py が動いているか確認したい

```bash
# Python プロセスの確認（Windows）
tasklist /FI "IMAGENAME eq python.exe"

# ログの末尾を確認
tail -5 task_log.txt
```
