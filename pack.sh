#!/bin/bash
echo "正在为红美铃桌宠打包单文件程序..."
pyinstaller --noconsole --onefile oc.py
echo "----------------------------------------"
echo "打包结束。"
echo "请记得把 action1.png 到 action4.png，以及 memory.json，复制到 dist 目录下，保持和打包后的 oc 处于同级目录下运行。"