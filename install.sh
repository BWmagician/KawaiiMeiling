#!/bin/bash
echo "正在为您安装红美铃桌宠所需的 macOS 运行环境..."
# 在本地虚拟环境中安全部署运行库
pip3 install requests PyQt5 duckduckgo_search -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "----------------------------------------"
if command -v ollama >/dev/null 2>&1; then
    # 核心修改：已同步更改为拉取 gemma4:latest 大模型
    echo "检测到您已安装 Ollama，正在为您自动拉取 gemma4:latest 大模型..."
    ollama pull gemma4:latest
    echo "Gemma4 模型拉取完成。"
else
    echo "友情提示：未检测到 Ollama 客户端。请访问 https://ollama.com 独立安装，"
    echo "并在终端手动运行：ollama pull gemma4:latest"
fi
echo "----------------------------------------"