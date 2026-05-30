import os
import re
import requests
from duckduckgo_search import DDGS


def should_trigger_search(text):
    """智能意图判定：检测是否属于强时效性或需要网络知识的词汇（已排除时间日期等本地可完美解决的问题）"""
    text_lower = text.lower()

    # 1. 强拦截词：如果主公单纯问时间、星期、日期等，由 Python 本地系统时钟 0 毫秒完美解答，绝对不去网络搜索！
    ignore_words = [
        "几点",
        "日期",
        "几号",
        "星期几",
        "周几",
        "时间",
        "年份",
        "现在时刻",
    ]
    if any(w in text_lower for w in ignore_words):
        return False

    # 2. 强搜索词
    keywords = [
        "今天",
        "明天",
        "天气",
        "新闻",
        "热搜",
        "谁是",
        "最新",
        "怎么回事",
        "为什么",
        "如何",
        "怎么",
        "股票",
        "今日",
        "发生了什么",
        "上映",
        "发售",
    ]
    return any(kw in text_lower for kw in keywords)


def search_text_rag(query):
    """鸭鸭走文本搜索（RAG）：获取最相关的 2 条网页背景摘要"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=2))
            if results:
                formatted = []
                for i, r in enumerate(results):
                    formatted.append(
                        f"[{i + 1}] 标题: {r.get('title')}, 摘要: {r.get('body')}"
                    )
                return "\n".join(formatted)
    except Exception:
        pass
    return ""


def search_and_download_image_vrag(query, save_dir):
    """鸭鸭走图片搜索（V-RAG）：获取首张公开图并下载至本地供 VLM 脑补视觉"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=1))
            if results:
                img_url = results[0].get("image")
                if img_url:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    }
                    # 绕过本地系统代理
                    res = requests.get(
                        img_url,
                        headers=headers,
                        timeout=5,
                        proxies={"http": None, "https": None},
                    )
                    if res.status_code == 200:
                        target_path = os.path.join(save_dir, "temp_search.jpg")
                        with open(target_path, "wb") as f:
                            f.write(res.content)
                        return True, target_path
    except Exception:
        pass
    return False, ""
