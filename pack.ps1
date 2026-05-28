# pack.ps1
<#
.SYNOPSIS
    将 DeskPal AI 应用打包成可执行文件。

.DESCRIPTION
    此脚本将使用 PyInstaller 将 Python 应用及其依赖打包成一个独立的 Windows 可执行文件。
    它会先激活虚拟环境，然后运行 PyInstaller。

.NOTES
    1. 确保已在 'requirements.txt' 中添加 'pyinstaller' 并运行了 'install.ps1'。
    2. 您可能需要根据应用的实际资源（图标、数据文件）修改 PyInstaller 命令。
    3. 打包完成后，可执行文件通常在 'dist' 文件夹中。
#>

# --- Configuration ---
$VenvName = "deskpal_env"
$MainAppFile = "oc.py"        # Your main Python application file
$AppNameForExe = "DeskPalAI"  # Desired name for the executable (without .exe)
$AppIcon = "icon.ico"         # Optional: Path to your application icon file (.ico format)
$PyInstallerArgs = "--onefile --windowed" # --onefile: single executable; --windowed: no console window

# --- Functions for Colored Output ---
function Write-Host-Green {
    param([string]$Message)
    Write-Host -ForegroundColor Green $Message
}
function Write-Host-Yellow {
    param([string]$Message)
    Write-Host -ForegroundColor Yellow $Message
}
function Write-Host-Red {
    param([string]$Message)
    Write-Host -ForegroundColor Red $Message
}
function Write-Host-Blue {
    param([string]$Message)
    Write-Host -ForegroundColor Blue $Message
}

function Exit-Script {
    param([string]$ErrorMessage)
    Write-Host-Red "`n错误: $ErrorMessage"
    Pause
    exit 1
}

Write-Host-Blue "========================================"
Write-Host-Blue "  $AppNameForExe 应用打包脚本"
Write-Host-Blue "========================================"

# --- 1. Check Main App File ---
Write-Host-Yellow "`n1. 检查主应用文件 '$MainAppFile'..."
if (-not (Test-Path -Path $MainAppFile)) {
    Exit-Script "主应用文件 '$MainAppFile' 未找到。请确保文件存在于当前目录。"
}
Write-Host-Green "主应用文件已找到。"

# --- 2. Activate Virtual Environment ---
Write-Host-Yellow "`n2. 激活 Python 虚拟环境..."
if (-not (Test-Path -Path "$VenvName\Scripts\Activate.ps1")) {
    Exit-Script "虚拟环境 '$VenvName' 未找到。请先运行 'install.ps1'。"
}
& "$VenvName\Scripts\Activate.ps1"
if (-not ($env:VIRTUAL_ENV)) {
    Exit-Script "无法激活虚拟环境。请手动检查并激活。"
}
Write-Host-Green "虚拟环境已激活。"

# --- 3. Check PyInstaller ---
Write-Host-Yellow "`n3. 检查 PyInstaller..."
try {
    (Get-Command pyinstaller -ErrorAction Stop).Source | Out-Null
    Write-Host-Green "PyInstaller 已安装。"
}
catch {
    Write-Host-Red "错误: PyInstaller 未安装。请确保在 '$PythonRequirementsFile' 中添加了 'pyinstaller' 并运行了 'install.ps1'。"
    deactivate
    Exit-Script "PyInstaller 未找到。"
}

# --- 4. Run PyInstaller ---
Write-Host-Yellow "`n4. 运行 PyInstaller 打包应用 (这可能需要较长时间)..."

# Construct PyInstaller command
$pyinstallerCommand = "pyinstaller $PyInstallerArgs --name $AppNameForExe"

# Add icon if specified and exists
if (Test-Path -Path $AppIcon) {
    $pyinstallerCommand += " --icon $AppIcon"
    Write-Host-Blue "已添加图标: $AppIcon"
} else {
    Write-Host-Yellow "警告: 未找到图标文件 '$AppIcon'，将使用 PyInstaller 默认图标。"
}

# Add any additional data files if your app needs them (e.g., config, images)
# Example for adding a 'data' folder and a 'config.ini' file:
# $pyinstallerCommand += " --add-data 'data;data' --add-data 'config.ini;.'"

$pyinstallerCommand += " $MainAppFile"

Write-Host-Blue "执行命令: $pyinstallerCommand"
Invoke-Expression $pyinstallerCommand # Execute the constructed command

if ($LASTEXITCODE -ne 0) {
    Write-Host-Red "`n错误: PyInstaller 打包失败。请检查上述错误消息。"
    Write-Host-Red "常见问题: 缺少依赖、资源文件路径不正确、Python 代码中存在无法解析的路径等。"
    deactivate
    Exit-Script "应用打包失败。"
}
Write-Host-Green "`n应用打包成功！"
Write-Host-Blue "`n可执行文件位于 'dist\$AppNameForExe.exe'"

# --- Final ---
deactivate
Write-Host-Blue "`n脚本运行完毕。"
Pause