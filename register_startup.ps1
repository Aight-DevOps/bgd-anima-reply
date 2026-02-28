# ============================================================
#  Anima Reply Bot - Windows スタートアップ登録スクリプト
# ============================================================

$ScriptDir    = 'C:\tools\GitHub\bgd-anima-reply'
$PythonExe    = 'C:\Users\tatsu\AppData\Local\Programs\Python\Python312\python.exe'
$SchedulerPy  = $ScriptDir + '\scheduler.py'
$ShortcutName = 'AnimaReplyBot.lnk'
$StartupFolder = [System.Environment]::GetFolderPath('Startup')
$ShortcutPath  = Join-Path $StartupFolder $ShortcutName

# ショートカット作成
$WshShell  = New-Object -ComObject WScript.Shell
$Shortcut  = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath       = $PythonExe
$Shortcut.Arguments        = $SchedulerPy
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.WindowStyle      = 7
$Shortcut.Description      = 'Anima Reply Bot Scheduler'
$Shortcut.Save()

Write-Host ''
Write-Host '=============================================='
Write-Host '  スタートアップ登録が完了しました'
Write-Host '=============================================='
Write-Host ''
Write-Host ('  登録先: ' + $ShortcutPath)
Write-Host ''
Write-Host '  次回PCログイン時から自動起動します。'
Write-Host '  今すぐ起動する場合: python scheduler.py'
Write-Host ''
Write-Host '  登録解除:'
Write-Host ('  Remove-Item ' + $ShortcutPath)
Write-Host ''
