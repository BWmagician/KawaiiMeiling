import sys
import os
import requests
import subprocess
import json

# Windows 底层 API 支持
if sys.platform == "win32":
    import ctypes

    # 全局多媒体硬件虚拟键扫码值
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_PLAY_PAUSE = 0xB3
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002


def trigger_media_action(action):
    """控制本地媒体播放状态：切歌、暂停、播放等"""

    # 1. macOS 平台的 AppleScript 进程级控制逻辑
    if sys.platform == "darwin":
        apps = ["NeteaseMusic", "Spotify", "Music"]
        script_map = {
            "next": "next track",
            "prev": "previous track",
            "play_pause": "playpause",
        }
        cmd = script_map.get(action)
        if not cmd:
            return False

        for app in apps:
            try:
                # 使用 UNIX 原生 pgrep 指令直接检查系统活跃进程
                res = subprocess.run(["pgrep", "-f", app], capture_output=True)
                if res.returncode != 0 and app == "NeteaseMusic":
                    res = subprocess.run(
                        ["pgrep", "-f", "网易云音乐"], capture_output=True
                    )

                # 只有当检测到目标播放器正在运行，才进行底层安全调用
                if res.returncode == 0:
                    script = f'tell application "{app}" to {cmd}'
                    subprocess.run(["osascript", "-e", script])
                    print(
                        f"[DEBUG-CONNECTOR] 已成功通过名称 ({app}) 控制播放器执行: {action}"
                    )
                    return True
            except Exception as e:
                if app == "NeteaseMusic":
                    try:
                        script_cn = f'tell application "网易云音乐" to {cmd}'
                        subprocess.run(["osascript", "-e", script_cn])
                        print(
                            "[DEBUG-CONNECTOR] 已成功通过中文名称 (网易云音乐) 控制播放器"
                        )
                        return True
                    except Exception:
                        pass
                print(f"[DEBUG-ERROR] AppleScript 控制失败: {e}")

    # 2. Windows 平台的系统全局多媒体虚拟键模拟
    elif sys.platform == "win32":
        try:
            vk_map = {
                "next": VK_MEDIA_NEXT_TRACK,
                "prev": VK_MEDIA_PREV_TRACK,
                "play_pause": VK_MEDIA_PLAY_PAUSE,
            }
            vk = vk_map.get(action)
            if vk:
                # 模拟硬件键盘按下与弹起，系统全局播放器会自动响应
                ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
                ctypes.windll.user32.keybd_event(
                    vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0
                )
                print(f"[DEBUG-CONNECTOR] 已模拟 Windows 全局多媒体按键: {action}")
                return True
        except Exception as e:
            print(f"[DEBUG-ERROR] Windows 模拟按键失败: {e}")
    return False


def request_netease_song(song_name):
    """网易云智能点歌：通过公开 API 嗅探 ID，并安全地触发 orpheus 协议唤醒客户端播放"""
    if not song_name:
        return False

    # 升级为 HTTPS 接口，避免 HTTP 劫持与重定向
    search_url = f"https://music.163.com/api/search/get?s={song_name}&type=1&limit=1"

    headers = {
        "Referer": "https://music.163.com",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    try:
        response = requests.get(
            search_url,
            headers=headers,
            timeout=5,
            proxies={"http": None, "https": None},
        )
        if response.status_code == 200:
            # 增加对非 JSON 响应（如反爬 HTML 拦截页）的防护
            try:
                data = response.json()
            except Exception:
                print(
                    f"[DEBUG-ERROR] 网易云接口未返回有效的 JSON 数据，可能遇到了人机验证。响应预览: {response.text[:100]}"
                )
                return False

            # 二次加载字符串形式的 JSON
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    return False

            if isinstance(data, dict):
                # 核心修复：防止 result 字段为 None 时触发 AttributeError 崩溃
                result_data = data.get("result")
                if not isinstance(result_data, dict):
                    print(
                        f"[DEBUG-CONNECTOR] 未能在网易云中检索到歌曲 '{song_name}' (返回数据为空)"
                    )
                    return False

                songs = result_data.get("songs") or []
                if songs:
                    song_id = songs[0].get("id")
                    song_title = songs[0].get("name")
                    artist = songs[0].get("artists", [{}])[0].get("name", "未知歌手")
                    print(
                        f"[DEBUG-CONNECTOR] 智能点歌成功! 已检索到: '{song_title}' - {artist}, ID: {song_id}"
                    )

                    # 安全唤醒客户端协议
                    protocol_url = f"orpheus://song/?id={song_id}"
                    try:
                        if sys.platform == "darwin":
                            subprocess.run(["open", protocol_url], check=True)
                        elif sys.platform == "win32":
                            os.startfile(protocol_url)
                        return True
                    except Exception as proto_err:
                        print(
                            f"[DEBUG-ERROR] 唤醒本地网易云客户端失败，请检查是否安装了客户端或协议是否注册。详情: {proto_err}"
                        )
                else:
                    print(
                        f"[DEBUG-CONNECTOR] 网易云中未找到与 '{song_name}' 匹配的歌曲。"
                    )
            else:
                print(f"[DEBUG-ERROR] 返回的数据非预期的字典格式: {type(data)}")
    except Exception as e:
        print(f"[DEBUG-ERROR] 网易云智能点歌通信失败: {e}")
    return False
