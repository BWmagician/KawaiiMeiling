# 1. 强制将工作路径定位到项目目录
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=========================================" -ForegroundColor Red
Write-Host "正在为您唤醒门番红美铃..." -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Red

# 自动检测 Python 指令
$PythonCmd = ""
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $PythonCmd = "python3"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
}

# 差异化启动
if ($IsWindows -or $env:OS -like "*Windows*") {
    if ($PythonCmd) {
        Write-Host "成功识别系统环境，正在为您启动桌宠..." -ForegroundColor Green
        & $PythonCmd oc.py
    } else {
        Write-Host "【错误】未检测到 Python 运行环境，请先安装 Python！" -ForegroundColor Red
        Read-Host
    }
} else {
    $LocalPython = "./.venv/bin/python"
    if (!(Test-Path $LocalPython)) {
        $LocalPython = "./.venv/bin/python3"
    }
    
    if (Test-Path $LocalPython) {
        Write-Host "成功识别本地虚拟环境，正在启动桌宠..." -ForegroundColor Green
        & $LocalPython oc.py
    } else {
        Write-Host "正在通过全局环境启动桌宠..." -ForegroundColor Green
        & $PythonCmd oc.py
    }
}