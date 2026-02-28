# ============================================================
#  Anima Reply Bot - タスクスケジューラ登録スクリプト
#  実行方法（管理者権限のPowerShellで）:
#    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#    .\setup_task.ps1
# ============================================================

$TaskName   = "AnimaReplyBot"
$BatFile    = "C:\tools\GitHub\bgd-anima-reply\run_bot.bat"
$WorkingDir = "C:\tools\GitHub\bgd-anima-reply"

# ── 既存タスクを削除（上書き登録のため）──────────────────
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "既存タスク '$TaskName' を削除しました。"
}

# ── アクション ────────────────────────────────────────────
# cmd.exe 経由で run_bot.bat を実行（文字化け対策含む）
$Action = New-ScheduledTaskAction `
    -Execute          "cmd.exe" `
    -Argument         "/c `"$BatFile`"" `
    -WorkingDirectory $WorkingDir

# ── トリガー：毎日 09:00 起動、30分ごとに繰り返し 13時間 ──
# 09:00 スタート → 30分ごと → 22:00 まで（13時間）
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
$Trigger.Repetition.Interval = "PT30M"   # 30分ごと
$Trigger.Repetition.Duration = "PT13H"   # 13時間（09:00〜22:00）

# ── 設定 ──────────────────────────────────────────────────
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `       # 起動時刻を逃した場合に次回実行
    -RunOnlyIfNetworkAvailable `# ネットワーク接続時のみ実行
    -ExecutionTimeLimit "02:00:00" `  # 最大2時間で強制終了
    -MultipleInstances IgnoreNew     # 実行中は新規起動をスキップ

# ── タスク登録 ────────────────────────────────────────────
Register-ScheduledTask `
    -TaskName   $TaskName `
    -Action     $Action `
    -Trigger    $Trigger `
    -Settings   $Settings `
    -RunLevel   Highest `
    -Force | Out-Null

Write-Host ""
Write-Host "=============================================="
Write-Host "  タスク '$TaskName' を登録しました"
Write-Host "=============================================="
Write-Host ""
Write-Host "  実行スケジュール:"
Write-Host "    毎日 09:00〜22:00、30分ごとに実行"
Write-Host ""
Write-Host "  ログファイル:"
Write-Host "    $WorkingDir\task_log.txt"
Write-Host ""
Write-Host "  タスクの確認:"
Write-Host "    Get-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "  タスクの削除:"
Write-Host "    Unregister-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
