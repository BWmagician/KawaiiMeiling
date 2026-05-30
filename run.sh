#!/bin/sh
script_dir=$(dirname "$(realpath "$0")")
echo $script_dir
echo "正在唤醒门番红美铃..."
python3 $script_dir/oc.py