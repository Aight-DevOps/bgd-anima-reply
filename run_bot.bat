@echo off
chcp 65001 > nul
cd /d C:\tools\GitHub\bgd-anima-reply

:: ── 二重起動防止 ──────────────────────────────────────
:: 前回の実行がまだ終わっていない場合はスキップ
if exist ".running" (
    echo %date% %time% - [SKIP] 前回の実行がまだ完了していません >> task_log.txt
    exit /b 0
)

:: ── ロックファイル作成 ────────────────────────────────
echo %date% %time% > .running

:: ── ログにセクション開始を記録 ────────────────────────
echo. >> task_log.txt
echo ================================================== >> task_log.txt
echo  %date% %time%  起動 >> task_log.txt
echo ================================================== >> task_log.txt

:: ── ボット実行 ────────────────────────────────────────
C:\Users\tatsu\AppData\Local\Programs\Python\Python312\python.exe anima_reply.py --today >> task_log.txt 2>&1

:: ── ロックファイル削除 ────────────────────────────────
del .running

exit /b 0
