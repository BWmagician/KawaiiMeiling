#!/bin/bash

# --- Configuration ---
APP_NAME="DeskPalAI"
VENV_NAME="deskpal_env"
OLLAMA_INSTALL_URL="https://ollama.com/download"
QWEN_MODEL_NAME="qwen:0.5b" # Or "qwen:0.5b-chat" if you prefer the chat variant
PYTHON_REQUIREMENTS_FILE="requirements.txt" # Assuming you have this file

# --- Colors for better readability ---
RED='\033[0;31m'
GREEN='\0330;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  ${APP_NAME} 安装脚本 (Linux / macOS)${NC}"
echo -e "${BLUE}========================================${NC}"

# --- 1. Check Python and pip ---
echo -e "\n${YELLOW}1. 检查 Python 和 pip...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 Python 3。请安装 Python 3.9 或更高版本。${NC}"
    echo -e "您可以在 https://www.python.org/downloads/ 下载并安装。"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if (( $(echo "$PYTHON_VERSION < 3.9" | bc -l) )); then
    echo -e "${RED}错误: Python 版本过低 (${PYTHON_VERSION})。请安装 Python 3.9 或更高版本。${NC}"
    echo -e "您可以在 https://www.python.org/downloads/ 下载并安装。"
    exit 1
fi
echo -e "${GREEN}Python 3 (${PYTHON_VERSION}) 已安装。${NC}"

if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 pip 3。请确保 pip 已随 Python 安装。${NC}"
    echo -e "尝试运行: python3 -m ensurepip --default-pip${NC}"
    exit 1
fi
echo -e "${GREEN}pip 3 已安装。${NC}"

# --- 2. Create/Activate Virtual Environment ---
echo -e "\n${YELLOW}2. 设置 Python 虚拟环境...${NC}"
if [ ! -d "$VENV_NAME" ]; then
    echo -e "${BLUE}创建虚拟环境 '$VENV_NAME'...${NC}"
    python3 -m venv "$VENV_NAME"
    if [ $? -ne 0 ]; then
        echo -e "${RED}错误: 无法创建虚拟环境。请确保 'python3-venv' (Ubuntu/Debian) 或 'python3-virtualenv' (Fedora) 包已安装。${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}虚拟环境 '$VENV_NAME' 已存在。${NC}"
fi

echo -e "${BLUE}激活虚拟环境...${NC}"
source "$VENV_NAME/bin/activate"
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 无法激活虚拟环境。${NC}"
    exit 1
fi
echo -e "${GREEN}虚拟环境已激活。${NC}"

# --- 3. Install Python Dependencies ---
echo -e "\n${YELLOW}3. 安装 Python 依赖...${NC}"

# Create a dummy requirements.txt if it doesn't exist for demonstration
if [ ! -f "$PYTHON_REQUIREMENTS_FILE" ]; then
    echo -e "创建示例 ${PYTHON_REQUIREMENTS_FILE} 文件。请确保您的实际依赖在此文件中。"
    echo "ollama" > "$PYTHON_REQUIREMENTS_FILE"
    echo "Pillow" >> "$PYTHON_REQUIREMENTS_FILE"
    echo "pyaudio" >> "$PYTHON_REQUIREMENTS_FILE" # For speech, might need system libs
    echo "speechrecognition" >> "$PYTHON_REQUIREMENTS_FILE"
    echo "gtts" >> "$PYTHON_REQUIREMENTS_FILE"
    echo "PyQt5" >> "$PYTHON_REQUIREMENTS_FILE" # Or PySide6
    echo "pyttsx3" >> "$PYTHON_REQUIREMENTS_FILE"
    echo "langchain" >> "$PYTHON_REQUIREMENTS_FILE"
    echo "langchain-community" >> "$PYTHON_REQUIREMENTS_FILE"
    echo "tiktoken" >> "$PYTHON_REQUIREMENTS_FILE"
    echo "chromadb" >> "$PYTHON_REQUIREMENTS_FILE"
    # Add any other libraries your oc.py, brain.py, widgets.py use
fi

pip install --upgrade pip
pip install -r "$PYTHON_REQUIREMENTS_FILE"
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 安装 Python 依赖失败。请检查 '${PYTHON_REQUIREMENTS_FILE}' 文件或网络连接。${NC}"
    deactivate # Exit venv on error
    exit 1
fi
echo -e "${GREEN}Python 依赖安装完成。${NC}"

# --- 4. Install Ollama ---
echo -e "\n${YELLOW}4. 安装 Ollama...${NC}"
echo -e "${BLUE}Ollama 是运行本地大语言模型所必需的。${NC}"
echo -e "${BLUE}请访问其官网下载并安装: ${OLLAMA_INSTALL_URL}${NC}"
echo -e "${BLUE}安装完成后，请返回此终端并按 Enter 键继续。${NC}"
read -p "安装完成后按 Enter 键..."

if ! command -v ollama &> /dev/null; then
    echo -e "${RED}错误: 未检测到 Ollama。请确保您已正确安装 Ollama 并将其添加到 PATH。${NC}"
    echo -e "您可能需要重新启动终端以使 PATH 生效。${NC}"
    deactivate
    exit 1
fi
echo -e "${GREEN}Ollama 已检测到。${NC}"

# --- 5. Download Qwen 0.5B Model ---
echo -e "\n${YELLOW}5. 下载 Qwen 0.5B 模型...${NC}"
echo -e "${BLUE}这将使用 Ollama 下载 ${QWEN_MODEL_NAME} 模型。这可能需要一些时间，取决于您的网络速度。${NC}"
ollama pull "$QWEN_MODEL_NAME"
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 下载 ${QWEN_MODEL_NAME} 模型失败。请检查您的网络连接或 Ollama 服务是否正在运行。${NC}"
    deactivate
    exit 1
fi
echo -e "${GREEN}Qwen 0.5B 模型下载完成。${NC}"

# --- Final Instructions ---
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}安装和设置已完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "\n${YELLOW}如何运行您的应用：${NC}"
echo -e "1. 确保您在当前目录 (${PWD})。"
echo -e "2. 如果您之前退出了终端或虚拟环境，请重新激活虚拟环境："
echo -e "   ${GREEN}source $VENV_NAME/bin/activate${NC}"
echo -e "3. 运行您的主应用文件 (例如 oc.py):"
echo -e "   ${GREEN}python oc.py${NC}"
echo -e "\n${YELLOW}提示：${NC} 当您完成应用使用后，可以通过运行 '${GREEN}deactivate${NC}' 命令退出虚拟环境。"
echo -e "\n${BLUE}享受使用 ${APP_NAME}！${NC}"

deactivate # Ensure we deactivate at the end for clean exit of the script