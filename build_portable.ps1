# build_portable.ps1 - Build portable bundle of the TW stock system
# Output: ..\TW_Portable  (embedded Python + packages + app + data + START.bat)
# Friends extract the folder and double-click START.bat. No Python install needed.
# Run: PowerShell in tw_backtest dir -> ./build_portable.ps1
# ASCII-only on purpose (PowerShell 5.1 mis-reads CJK in .ps1).

$ErrorActionPreference = "Stop"
$PYVER  = "3.10.11"
$SRC    = $PSScriptRoot
$OUT    = Join-Path $SRC "..\TW_Portable"
$PYDIR  = Join-Path $OUT "python"
$APPDIR = Join-Path $OUT "app"
$INCLUDE_DATA = $true   # bundle 876MB stock data (true=ready to use, big; false=download on first run)

Write-Host "==> 1/6 create output $OUT"
if (Test-Path $OUT) { Remove-Item $OUT -Recurse -Force }
New-Item -ItemType Directory -Path $OUT, $PYDIR, $APPDIR | Out-Null

Write-Host "==> 2/6 download embeddable Python $PYVER"
$embedZip = Join-Path $env:TEMP "pyembed.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$PYVER/python-$PYVER-embed-amd64.zip" -OutFile $embedZip
Expand-Archive $embedZip -DestinationPath $PYDIR -Force

Write-Host "==> 3/6 enable site-packages + install pip"
$pth = Get-ChildItem $PYDIR -Filter "python*._pth" | Select-Object -First 1
(Get-Content $pth.FullName) -replace '#import site', 'import site' | Set-Content $pth.FullName
Add-Content $pth.FullName "Lib\site-packages"
$getpip = Join-Path $env:TEMP "get-pip.py"
Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
& "$PYDIR\python.exe" $getpip --no-warn-script-location

Write-Host "==> 4/6 pip install packages (streamlit/pandas/numpy/plotly... ~5-15 min)"
& "$PYDIR\python.exe" -m pip install --no-warn-script-location -r (Join-Path $SRC "requirements.txt")
# pywebview 不在 requirements（雲端不裝）；隨身版桌面 App 需要，這裡另外裝
& "$PYDIR\python.exe" -m pip install --no-warn-script-location "pywebview>=5.0"

Write-Host "==> 5/6 copy app code (data included: $INCLUDE_DATA)"
# 排除：個人持倉/通知(含密碼)、暫存旗標、打包用檔；secrets.toml(共用密碼)保留
robocopy $SRC $APPDIR /E /XD "$SRC\__pycache__" "$SRC\backtest_results" "$SRC\.git" /XF "_launcher.bat" "build_portable.ps1" "_build.log" "*.pyc" "portfolio_*.csv" "notify_*.json" "config.json" "_progress.json" "_auto_stop.flag" /NFL /NDL /NJH /NJS /NP | Out-Null
if (-not $INCLUDE_DATA) {
    Get-ChildItem (Join-Path $APPDIR "data") -Filter "*.TW.csv"  | Remove-Item -Force
    Get-ChildItem (Join-Path $APPDIR "data") -Filter "*.TWO.csv" | Remove-Item -Force
}

Write-Host "==> 6/6 add launchers (relative paths, work on any machine)"
# 用相對路徑 .bat，不用 .lnk（.lnk 會存絕對路徑，到別台電腦失效）
Copy-Item (Join-Path $SRC "_launcher.bat")        (Join-Path $OUT "START.bat")
Copy-Item (Join-Path $SRC "_window_launcher.bat") (Join-Path $OUT "視窗版App.bat")

Write-Host ""
Write-Host "DONE. Portable bundle at: $OUT" -ForegroundColor Green
Write-Host "  START.bat     = 主要啟動（瀏覽器，看得到狀態/錯誤）"
Write-Host "  視窗版App.bat = 桌面視窗版（pythonw 無黑窗）"
Write-Host "Zip the whole folder; friends EXTRACT then double-click START.bat."
Write-Host "Password in app\.streamlit\secrets.toml (default tw2026)."
