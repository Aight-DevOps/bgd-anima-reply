#!/usr/bin/env python3
"""
Anima Reply Bot - スケジューラ
==============================
このスクリプトを起動しておくだけで、毎日 09:00〜22:00 の間
30分ごとに anima_reply.py を自動実行します。

起動方法:
  python scheduler.py

停止方法:
  Ctrl+C を押す
"""

import schedule
import time
import subprocess
import sys
import os
import io
from datetime import datetime

# Windows コンソールの文字化け対策
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE  = sys.executable          # このスクリプトを実行しているPythonを使う
BOT_SCRIPT  = os.path.join(SCRIPT_DIR, "anima_reply.py")
LOG_FILE    = os.path.join(SCRIPT_DIR, "task_log.txt")

# 実行時間帯（この範囲外は何もしない）
RUN_HOUR_START = 9   # 09:00
RUN_HOUR_END   = 22  # 22:00

# 二重起動防止フラグ
_bot_running = False


def log(msg: str):
    """ログをコンソールとファイル両方に出力する。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_bot():
    """ボットを1回実行する。時間帯チェックと二重起動防止付き。"""
    global _bot_running

    now = datetime.now()

    # ─ 実行時間帯チェック（09:00〜22:00 のみ）─
    if not (RUN_HOUR_START <= now.hour < RUN_HOUR_END):
        return  # 時間外は静かにスキップ

    # ─ 二重起動防止 ─
    if _bot_running:
        log("[SKIP] 前回の実行がまだ完了していません。このサイクルはスキップします。")
        return

    _bot_running = True
    log("=" * 50)
    log("ボット起動")

    try:
        result = subprocess.run(
            [PYTHON_EXE, BOT_SCRIPT, "--today"],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        # 出力をログに書き込む
        if result.stdout:
            for line in result.stdout.splitlines():
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
                print(line, flush=True)
        if result.stderr:
            for line in result.stderr.splitlines():
                err_line = f"[STDERR] {line}"
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(err_line + "\n")

    except Exception as e:
        log(f"[ERROR] ボット実行中にエラーが発生しました: {e}")
    finally:
        _bot_running = False
        log("ボット終了")
        log("=" * 50)


def main():
    log("=" * 50)
    log("Anima Reply Bot スケジューラ 起動")
    log(f"実行サイクル: {RUN_HOUR_START:02d}:00〜{RUN_HOUR_END:02d}:00、30分ごと")
    log(f"ログファイル: {LOG_FILE}")
    log("停止するには Ctrl+C を押してください")
    log("=" * 50)

    # 30分ごとに実行（時間帯チェックは run_bot 内で実施）
    schedule.every(30).minutes.do(run_bot)

    # 起動直後に1回即実行（時間帯内であれば）
    run_bot()

    # メインループ
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # 30秒ごとにスケジュールをチェック
    except KeyboardInterrupt:
        log("スケジューラを停止しました。")


if __name__ == "__main__":
    main()
