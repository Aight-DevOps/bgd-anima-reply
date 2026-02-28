#!/usr/bin/env python3
"""
Anima Reply Bot
===============
Airtable の [STG]ANIMA-WORK-REPLY テーブルからリプライドラフトを取得し、
Playwright を使って X (旧 Twitter) へ自動返信するスクリプト。

【初回のみ】ログイン状態の保存:
  python anima_reply.py --setup-auth

【通常実行】:
  python anima_reply.py --visible --today --limit 1   # 表示モード、今日1件テスト
  python anima_reply.py --today                       # ヘッドレスで今日のデータ全件
  python anima_reply.py                               # ヘッドレスで全件
"""

import asyncio
import random
import re
import argparse
import sys
import io
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Windows コンソールの文字化け対策
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pyairtable import Api
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ── 設定（.env ファイルから読み込む）────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv 未インストールの場合は環境変数から直接読む

import os
AIRTABLE_TOKEN   = os.environ["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = os.environ["AIRTABLE_BASE_ID"]
TABLE_NAME       = "[STG]ANIMA-WORK-REPLY"

# 認証状態の保存先（--setup-auth で生成）
AUTH_STATE_FILE = Path(__file__).parent / "auth_state.json"

# 待機時間設定（秒）
WAIT_PAGE_LOAD_MIN     = 5
WAIT_PAGE_LOAD_MAX     = 10
WAIT_TYPING_MIN        = 0.1
WAIT_TYPING_MAX        = 0.3
WAIT_BEFORE_SUBMIT_MIN = 2
WAIT_BEFORE_SUBMIT_MAX = 4
WAIT_BETWEEN_REPLY_MIN = 60
WAIT_BETWEEN_REPLY_MAX = 120
# いいね待機時間設定（秒）
# リプライ送信前、ランダムな時間待機してからいいねする（人間らしい操作に見せるため）
WAIT_BEFORE_REPLY_LIKE_MIN       = 3
WAIT_BEFORE_REPLY_LIKE_MAX       = 8
WAIT_LIKE_PAGE_LOAD_MIN          = 3
WAIT_LIKE_PAGE_LOAD_MAX          = 7
WAIT_BEFORE_LIKE_CLICK_MIN       = 1
WAIT_BEFORE_LIKE_CLICK_MAX       = 3
# ─────────────────────────────────────────────────────────────────────────────


# ── 初回セットアップ：手動ログインして認証状態を保存 ──────────────────────────

async def setup_auth():
    """
    ブラウザを表示して X にログインし、認証状態を auth_state.json に保存する。
    初回のみ実行すればよい。ログイン完了を自動検知して保存する。
    """
    print("=" * 60)
    print("  認証セットアップ")
    print("=" * 60)
    print()
    print("ブラウザが開きます。X にログインしてください。")
    print("ログインが完了すると自動的に認証状態を保存してブラウザを閉じます。")
    print("（最大5分待機します）")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await page.goto("https://x.com/login", wait_until="domcontentloaded")

        print("👉 ブラウザで X にログインしてください...")
        print("   ログイン完了後、自動的に認証状態を保存します。")

        # ログイン完了の検知：ホームタイムラインが表示されるまで待機（最大5分）
        try:
            # ホーム画面の主要要素が出てくるまで待つ
            await page.wait_for_selector(
                '[data-testid="primaryColumn"], [aria-label="Home timeline"], [data-testid="AppTabBar_Home_Link"]',
                timeout=300_000,  # 5分
            )
            print("\n✓ ログイン完了を検知しました。")
        except PlaywrightTimeoutError:
            print("\n⚠ タイムアウト：ログインが検知できませんでした。")
            await browser.close()
            return

        # 認証状態（Cookie + localStorage）を保存
        await context.storage_state(path=str(AUTH_STATE_FILE))
        print(f"✓ 認証状態を保存しました: {AUTH_STATE_FILE}")
        print("  次回からは --setup-auth なしで実行できます。")

        await asyncio.sleep(2)
        await browser.close()


# ── Airtable 操作 ─────────────────────────────────────────────────────────────

def get_airtable_records(limit: int = 0, today_only: bool = False):
    """
    ApproveCheck=TRUE かつ ReplyStatus='Draft' のレコードを取得。
    today_only=True: GeneratedDate が今日(JST)のもの限定。
    limit > 0: その件数のみ（テスト用）。
    """
    api   = Api(AIRTABLE_TOKEN)
    table = api.table(AIRTABLE_BASE_ID, TABLE_NAME)
    records = table.all(
        formula="AND({ApproveCheck}=1, {ReplyStatus}='Draft')"
    )

    if today_only:
        # JST今日の 00:00 を UTC に変換して比較
        jst = timezone(timedelta(hours=9))
        now_jst = datetime.now(jst)
        today_start_jst = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc_str = today_start_jst.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        records = [
            r for r in records
            if r["fields"].get("GeneratedDate", "") >= today_start_utc_str
        ]

    if limit > 0:
        records = records[:limit]

    return records, table


def update_airtable_status(table, record_id: str, status: str):
    """ReplyStatus フィールドを更新する。"""
    table.update(record_id, {"ReplyStatus": status})
    print(f"  → Airtable 更新: {status}  ({record_id})")


# ── X (Twitter) 操作 ──────────────────────────────────────────────────────────

async def is_post_unavailable(page) -> bool:
    """ポストが削除・凍結・存在しないページかどうかを判定する。"""
    indicators = [
        "This post is unavailable",
        "This Tweet is unavailable",
        "This account doesn't exist",
        "Hmm...this page doesn't exist",
        "Something went wrong. Try reloading",
    ]
    for text in indicators:
        try:
            if await page.get_by_text(text, exact=False).count() > 0:
                return True
        except Exception:
            pass
    return False


async def reply_to_tweet(page, reply_url: str, reply_text: str) -> str:
    """
    ReplyLink (x.com/intent/post?... 形式) に遷移してリプライを送信する。

    戻り値:
      "Complete" : 送信成功
      "SKIP"     : ポスト削除・入力欄不可・送信ボタン不可
    """
    print(f"  → ページ移動: {reply_url[:80]}")

    try:
        await page.goto(reply_url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as e:
        print(f"  ✗ ページ移動エラー: {e}")
        return "SKIP"

    # ─ ページ読み込み後の待機（5〜10秒）─
    wait_load = random.uniform(WAIT_PAGE_LOAD_MIN, WAIT_PAGE_LOAD_MAX)
    print(f"  … ページ読み込み待機 {wait_load:.1f}s")
    await asyncio.sleep(wait_load)

    # ─ ログインページへのリダイレクト検出 ─
    if "login" in page.url or "flow/login" in page.url:
        print("  ✗ ログインページにリダイレクト → 認証状態が無効です")
        print("    python anima_reply.py --setup-auth を実行して再ログインしてください")
        return "SKIP"

    # ─ ポスト削除・利用不可チェック ─
    if await is_post_unavailable(page):
        print("  ✗ ポストが削除または利用不可のため SKIP")
        return "SKIP"

    # ─ リプライ入力欄を待機・取得 ─
    textarea_selector = '[data-testid="tweetTextarea_0"]'
    try:
        textarea = await page.wait_for_selector(textarea_selector, timeout=15_000)
    except PlaywrightTimeoutError:
        try:
            await page.screenshot(path="debug_screenshot.png", full_page=True)
            print(f"  📸 debug_screenshot.png に画面を保存（URL: {page.url}）")
        except Exception:
            pass
        print("  ✗ リプライ入力欄が見つかりません → SKIP")
        return "SKIP"

    if not textarea:
        print("  ✗ リプライ入力欄が None → SKIP")
        return "SKIP"

    # ─ 入力欄をクリックしてフォーカス ─
    await textarea.click()
    await asyncio.sleep(random.uniform(0.5, 1.0))

    # ─ URL に埋め込まれた既存テキストをクリア ─
    await page.keyboard.press("Control+a")
    await asyncio.sleep(0.2)
    await page.keyboard.press("Delete")
    await asyncio.sleep(0.3)

    # ─ 1文字ずつ人間らしいタイピング（0.1〜0.3秒/文字）─
    preview = reply_text[:50] + ("..." if len(reply_text) > 50 else "")
    print(f"  … テキスト入力中: 「{preview}」")
    for char in reply_text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(WAIT_TYPING_MIN, WAIT_TYPING_MAX))

    # ─ 送信前の待機（2〜4秒）─
    wait_submit = random.uniform(WAIT_BEFORE_SUBMIT_MIN, WAIT_BEFORE_SUBMIT_MAX)
    print(f"  … 送信前待機 {wait_submit:.1f}s")
    await asyncio.sleep(wait_submit)

    # ─ 送信ボタンをクリック ─
    for sel in ['[data-testid="tweetButton"]', '[data-testid="tweetButtonInline"]']:
        try:
            btn = await page.wait_for_selector(sel, timeout=5_000)
            if btn:
                await btn.click()
                print("  ✓ リプライ送信完了")
                await asyncio.sleep(random.uniform(2, 3))
                return "Complete"
        except PlaywrightTimeoutError:
            continue
        except Exception as e:
            print(f"  ✗ 送信エラー ({sel}): {e}")
            continue

    print("  ✗ 送信ボタンが見つかりません → SKIP")
    return "SKIP"


async def like_tweet(page, tweet_id: str) -> bool:
    """
    指定した tweet_id のツイートにいいねをする。
    人間らしい操作に見せるため、ランダムな待機時間を設けてからいいねる。

    戻り値:
      True  : いいね成功
      False : いいね失敗・スキップ
    """
    tweet_url = f"https://x.com/i/web/status/{tweet_id}"
    print(f"  → [いいね] ツイートページへ移動: {tweet_url}")

    try:
        await page.goto(tweet_url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as e:
        print(f"  ✗ [いいね] ページ移動エラー: {e}")
        return False

    # ─ ページ読み込み後の待機（人間らしくランダムに）─
    wait_load = random.uniform(WAIT_LIKE_PAGE_LOAD_MIN, WAIT_LIKE_PAGE_LOAD_MAX)
    print(f"  … [いいね] ページ読み込み待機 {wait_load:.1f}s")
    await asyncio.sleep(wait_load)

    # ─ ログインページへのリダイレクト検出 ─
    if "login" in page.url or "flow/login" in page.url:
        print("  ✗ [いいね] ログインページにリダイレクト → 認証状態が無効です")
        return False

    # ─ ポスト削除・利用不可チェック ─
    if await is_post_unavailable(page):
        print("  ✗ [いいね] ポストが削除または利用不可のため SKIP")
        return False

    # ─ いいねボタンを探してクリック ─
    # まだいいねしていない場合は aria-label に "Like" が含まれる
    # 既にいいね済みの場合は aria-label に "Unlike" が含まれる
    like_selector = '[data-testid="like"]'
    already_liked_selector = '[data-testid="unlike"]'

    # クリック前に少し待機（より自然な操作感のため）
    wait_before_click = random.uniform(WAIT_BEFORE_LIKE_CLICK_MIN, WAIT_BEFORE_LIKE_CLICK_MAX)
    print(f"  … [いいね] クリック前待機 {wait_before_click:.1f}s")
    await asyncio.sleep(wait_before_click)

    # 既にいいね済みか確認
    try:
        already = await page.wait_for_selector(already_liked_selector, timeout=3_000)
        if already:
            print("  ✓ [いいね] 既にいいね済みのためスキップ")
            return True
    except PlaywrightTimeoutError:
        pass

    # いいねボタンをクリック
    try:
        btn = await page.wait_for_selector(like_selector, timeout=10_000)
        if btn:
            await btn.click()
            print("  ✓ [いいね] いいね完了")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            return True
    except PlaywrightTimeoutError:
        print("  ✗ [いいね] いいねボタンが見つかりません")
    except Exception as e:
        print(f"  ✗ [いいね] クリックエラー: {e}")

    return False


# ── メイン処理 ────────────────────────────────────────────────────────────────

async def main(headless: bool, limit: int, today_only: bool):
    print("=" * 60)
    print("  Anima Reply Bot  起動")
    today_label = "今日のみ" if today_only else "全期間"
    print(f"  ヘッドレスモード: {headless}  処理上限: {'無制限' if limit == 0 else f'{limit} 件'}  対象: {today_label}")
    print("=" * 60)

    # ─ 認証状態ファイルの確認 ─
    if not AUTH_STATE_FILE.exists():
        print()
        print("  [エラー] 認証状態ファイルが見つかりません。")
        print("  初回は以下を実行してください:")
        print("    python anima_reply.py --setup-auth")
        return

    # ── 1. Airtable からレコード取得 ─────────────────────────
    print("\n[Step 1] Airtable からレコード取得中...")
    records, table = get_airtable_records(limit=limit, today_only=today_only)

    if not records:
        print("  対象レコードが見つかりません（ApproveCheck=ON & ReplyStatus=Draft）。")
        return

    print(f"  {len(records)} 件のレコードを処理します。")
    for r in records:
        f = r["fields"]
        print(f"    → {r['id']}  {f.get('GeneratedDate','')[:10]}  {f.get('ReplyDraft','')[:30]}...")

    # ── 2. Playwright 起動（保存済み認証状態を使用）────────────
    async with async_playwright() as p:
        print(f"\n[Step 2] Playwright Chromium 起動中（認証状態: {AUTH_STATE_FILE.name}）...")

        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=str(AUTH_STATE_FILE),   # 保存済みCookie + localStorage を読み込む
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()

        # ── 3. レコードごとに処理 ─────────────────────────────
        print("[Step 3] X へのリプライ送信を開始します...\n")

        total   = len(records)
        success = 0
        skipped = 0

        for idx, record in enumerate(records, 1):
            record_id  = record["id"]
            fields     = record.get("fields", {})
            reply_url  = fields.get("ReplyLink",  "").strip()
            reply_text = fields.get("ReplyDraft", "").strip()

            print(f"─── [{idx}/{total}] レコード: {record_id} ───")

            if not reply_url or not reply_text:
                print("  ✗ ReplyLink または ReplyDraft が空 → SKIP")
                update_airtable_status(table, record_id, "SKIP")
                skipped += 1
                continue

            # ─ リプライ前にいいねをつける ─
            # ReplyLink から tweet_id を抽出する
            # 形式例: https://x.com/intent/post?in_reply_to=1234567890
            #      or: https://twitter.com/intent/tweet?in_reply_to=1234567890
            m = re.search(r"in_reply_to=([0-9]+)", reply_url)
            if m:
                tweet_id = m.group(1)
                # リプライ送信前、人間らしいランダム待機を挟んでからいいね
                wait_before_like = random.uniform(
                    WAIT_BEFORE_REPLY_LIKE_MIN,
                    WAIT_BEFORE_REPLY_LIKE_MAX,
                )
                print(f"\n  … [いいね] リプライ前待機 {wait_before_like:.1f}s してからいいね開始...")
                await asyncio.sleep(wait_before_like)
                await like_tweet(page, tweet_id)
            else:
                print("  ⚠ [いいね] ReplyLink から tweet_id が取得できないためいいねをスキップ")

            result = await reply_to_tweet(page, reply_url, reply_text)
            update_airtable_status(table, record_id, result)

            if result == "Complete":
                success += 1
            else:
                skipped += 1

            if idx < total:
                interval = random.uniform(WAIT_BETWEEN_REPLY_MIN, WAIT_BETWEEN_REPLY_MAX)
                print(f"\n  … 次のリプライまで {interval:.0f} 秒 待機中...\n")
                await asyncio.sleep(interval)

        await browser.close()

    # ── 4. 結果サマリー ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("  処理完了")
    print(f"  成功 (Complete): {success} 件")
    print(f"  スキップ (SKIP): {skipped} 件")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Anima Reply Bot — AirtableデータをもとにXへ自動リプライ"
    )
    parser.add_argument(
        "--setup-auth",
        action="store_true",
        help="【初回のみ】ブラウザを開いて X にログインし認証状態を保存する",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="ブラウザを表示して実行（デフォルトはヘッドレス/非表示）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="処理するレコード数の上限（0=無制限、テスト時は 1 を推奨）",
    )
    parser.add_argument(
        "--today",
        action="store_true",
        help="今日(JST)生成されたレコードのみ対象にする",
    )
    args = parser.parse_args()

    if args.setup_auth:
        asyncio.run(setup_auth())
    else:
        asyncio.run(main(headless=not args.visible, limit=args.limit, today_only=args.today))
