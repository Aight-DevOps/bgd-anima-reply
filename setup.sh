#!/usr/bin/env bash
# ============================================================
#  Anima Reply Bot — セットアップスクリプト
#  実行方法: bash setup.sh
#  動作確認済み環境: WSL (Ubuntu), Linux
# ============================================================

set -e

echo "============================================================"
echo "  Anima Reply Bot セットアップ"
echo "============================================================"

# ── Python コマンド解決 ──────────────────────────────────
echo ""
echo "[1] Python / pip コマンドを確認中..."

# python3 / python どちらかを使う
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "  [ERROR] Python が見つかりません。Python 3.9 以上をインストールしてください。"
    exit 1
fi
echo "  Python: $($PYTHON --version)"

# pip がない場合は apt でインストール（WSL/Ubuntu 想定）
if ! $PYTHON -m pip --version &>/dev/null; then
    echo ""
    echo "  pip が見つかりません。apt でインストールします（sudo が必要です）..."
    sudo apt-get update -qq
    sudo apt-get install -y python3-pip
    echo "  ✓ pip インストール完了"
fi
echo "  pip: $($PYTHON -m pip --version)"

# ── 仮想環境の作成（任意）───────────────────────────────
echo ""
echo "[2] 仮想環境を作成しますか？ (y/N)"
read -r CREATE_VENV
if [[ "$CREATE_VENV" =~ ^[Yy]$ ]]; then
    # venv 作成を試みる（失敗時は python3-venv をインストールしてリトライ）
    if ! $PYTHON -m venv .venv 2>/dev/null; then
        echo "  python3-venv が不足しています。インストールします..."
        sudo apt-get install -y python3-venv python3-full
        $PYTHON -m venv .venv
    fi
    echo "  仮想環境を作成しました: .venv/"
    # shellcheck disable=SC1091
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null || true
    echo "  仮想環境を有効化しました。"
    echo "  ※ 次回以降の実行前に: source .venv/bin/activate"
fi

# ── 依存パッケージのインストール ────────────────────────
echo ""
echo "[3] 依存パッケージをインストール中..."
$PYTHON -m pip install --upgrade pip -q
$PYTHON -m pip install -r requirements.txt
echo "  ✓ 依存パッケージ インストール完了"

# ── Playwright ブラウザのインストール ───────────────────
echo ""
echo "[4] Playwright Chromium をインストール中..."

# Playwright の依存ライブラリも一緒にインストール（WSL では必要な場合がある）
if command -v sudo &>/dev/null; then
    $PYTHON -m playwright install --with-deps chromium
else
    $PYTHON -m playwright install chromium
fi
echo "  ✓ Playwright Chromium インストール完了"

# ── インストール確認 ─────────────────────────────────────
echo ""
echo "[5] インストール確認..."
$PYTHON -c "import pyairtable; print('  pyairtable : OK')"
$PYTHON -c "from playwright.async_api import async_playwright; print('  playwright : OK')"
$PYTHON -c "import dotenv; print('  python-dotenv: OK')"

echo ""
echo "============================================================"
echo "  セットアップ完了！"
echo ""
echo "  【初回のみ】X へのログイン認証状態を保存:"
echo "    $PYTHON anima_reply.py --setup-auth"
echo ""
echo "  実行コマンド:"
echo "    $PYTHON anima_reply.py --today           # 今日のレコードを処理"
echo "    $PYTHON anima_reply.py --today --limit 1 # テスト（1件のみ）"
echo "    $PYTHON anima_reply.py --visible         # ブラウザを表示して実行"
echo "============================================================"
