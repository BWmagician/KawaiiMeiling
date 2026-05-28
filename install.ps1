# 1. 强制将工作路径锁定在当前项目文件夹，防止路径偏移
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=========================================" -ForegroundColor Red
Write-Host "正在为您配置红美铃桌宠所需的极简运行环境..." -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Red

# 2. 自动检测系统活跃的 Python 指令
$PythonCmd = ""
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $PythonCmd = "python3"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
}

if ($PythonCmd -eq "") {
    Write-Host "【错误】未在您的系统中检测到任何 Python 环境！" -ForegroundColor Red
    Write-Host "请前往 Python 官网下载并安装：https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "安装时请务必勾选底部的 'Add python.exe to PATH' 选项喵！" -ForegroundColor Yellow
    Read-Host "按回车退出..."
    exit
}

# 3. 差异化部署策略
if ($IsWindows -or $env:OS -like "*Windows*") {
    # Windows 平台：直接进行全局安装，完美避开 Python 3.13 首次创建 venv 时 ensurepip 挂死挂起的 Bug！
    Write-Host "检测到 Windows 平台，正在直接为您部署核心运行库 (PyQt5, requests)..." -ForegroundColor Cyan
    & $PythonCmd -m pip install requests PyQt5 -i https://pypi.tuna.tsinghua.edu.cn/simple --user
} else {
    # macOS 平台：依然保持隔离的 .venv 沙箱，避开系统 PEP 668 限制
    Write-Host "检测到 macOS 平台，正在为您创建隔离虚拟环境..." -ForegroundColor Cyan
    if (!(Test-Path ".\.venv")) {
        & $PythonCmd -m venv .venv
    }
    $LocalPip = "./.venv/bin/pip"
    & $LocalPip install requests PyQt5 -i https://pypi.tuna.tsinghua.edu.cn/simple
}

Write-Host ""
Write-Host "-----------------------------------------" -ForegroundColor DarkYellow
Write-Host "正在检测本地 Ollama 环境..." -ForegroundColor Cyan

# 4. 检测并拉取 0.5B 本地小模型
$OllamaCheck = Get-Command ollama -ErrorAction SilentlyContinue
if ($OllamaCheck) {
    Write-Host "检测到本地已安装 Ollama，正在为您自动拉取 0.5B 决策小模型..." -ForegroundColor Green
    ollama pull qwen2.5:0.5b
    Write-Host "模型拉取完成！" -ForegroundColor Green
} else {
    Write-Host "【提示】未检测到 Ollama 命令行工具。请至官网 https://ollama.com 下载。" -ForegroundColor Yellow
}

Write-Host "-----------------------------------------" -ForegroundColor DarkYellow
Write-Host "运行环境配置完毕！主公现在可以使用 run.ps1 启动美铃了喵！" -ForegroundColor Green
Write-Host "按回车键退出..."
Read-Host