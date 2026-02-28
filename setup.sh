#!/usr/bin/env bash
# ============================================================
#  Anima Reply Bot — セットアップスクリプト
#  実行方法: bash setup.sh
# ============================================================

set -e

echo "============================================================"
echo "  Anima Reply Bot セットアップ"
echo "============================================================"

# ── Python バージョン確認 ────────────────────────────────
echo ""
echo "[1] Python バージョン確認..."
python --version || python3 --version

# ── 仮想環境の作成（任意）───────────────────────────────
echo ""
echo "[2] 仮想環境を作成しますか？ (y/N)"
read -r CREATE_VENV
if [[ "$CREATE_VENV" =~ ^[Yy]$ ]]; then
    python -m venv .venv
    echo "  仮想環境を作成しました: .venv/"
    echo "  有効化: source .venv/Scripts/activate  (Windows bash)"
    # shellcheck disable=SC1091
    source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null || true
    echo "  仮想環境を有効化しました。"
fi

# ── 依存パッケージのインストール ────────────────────────
echo ""
echo "[3] 依存パッケージをインストール中..."
pip install --upgrade pip
pip install pyairtable playwright

echo "  ✓ pyairtable インストール完了"
echo "  ✓ playwright インストール完了"

# ── Playwright ブラウザのインストール ───────────────────
echo ""
echo "[4] Playwright Chromium をインストール中..."
playwright install chromium
echo "  ✓ playwright install chromium 完了"

# ── インストール確認 ─────────────────────────────────────
echo ""
echo "[5] インストール確認..."
python -c "import pyairtable; print(f'  pyairtable: OK')"
python -c "from playwright.async_api import async_playwright; print('  playwright: OK')"

echo ""
echo "============================================================"
echo "  セットアップ完了！"
echo ""
echo "  実行コマンド:"
echo "    python anima_reply.py            # ヘッドレス（非表示）"
echo "    python anima_reply.py --visible  # ブラウザ表示（デバッグ）"
echo ""
echo "  注意事項:"
echo "    - 実行前に Chrome をすべて閉じてください"
echo "      （同じプロファイルが使用中だとエラーになります）"
echo "    - X にログイン済みの Chrome プロファイルを使用してください"
echo "============================================================"
