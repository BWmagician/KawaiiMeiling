const BLACKLIST_KEYWORDS = ['login', 'signin', 'bank', 'checkout', 'pay', 'password', 'wallet', 'mail.google'];

function isSensitivePage() {
    const url = window.location.href.toLowerCase();
    return BLACKLIST_KEYWORDS.some(keyword => url.includes(keyword));
}

// 格式化物理时间戳为标准大模型易读的 MM:SS 格式
function formatTime(seconds) {
    if (isNaN(seconds) || seconds === Infinity) return "00:00";
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function safeExtractText() {
    if (isSensitivePage()) {
        console.log("[美铃感知] 检测到敏感页面，已自动停用抓取以保护主公隐私。");
        return { text: null, imageUrl: null };
    }

    const url = window.location.href.toLowerCase();
    let metaContext = "";
    // 捕获网页中的开放图谱封面图链接（如 B站/YouTube 视频封面的物理 JPG 地址）
    let imageUrl = document.querySelector('meta[property="og:image"]')?.getAttribute('content') || "";

    // ==================== 1. Bilibili 专属动态视觉与播放进度提取器 ====================
    if (url.includes("bilibili.com/video/")) {
        const bTitle = document.querySelector('h1.video-title')?.innerText || document.title;
        const upName = document.querySelector('.up-name')?.innerText?.trim() ||
            document.querySelector('.up-info--username')?.innerText?.trim() || "未知UP主";
        const bDesc = document.querySelector('.desc-info-text')?.innerText?.trim() ||
            document.querySelector('.video-desc-info')?.innerText?.trim() || "暂无简介";

        let playProgress = "";
        const videoEl = document.querySelector('video');
        if (videoEl) {
            const curTimeStr = formatTime(videoEl.currentTime);
            const durationStr = formatTime(videoEl.duration);
            if (!videoEl.paused) {
                playProgress = `，当前视频播放进度为 ${curTimeStr} / ${durationStr}，且正处于播放状态`;
            } else {
                playProgress = `，当前视频播放进度为 ${curTimeStr} / ${durationStr}，但已被主公暂停`;
            }
        }

        metaContext += `【系统感知：主公正在观看B站视频。\n`;
        metaContext += `视频标题: "${bTitle}"，UP主: "${upName}"，内容简介: "${bDesc.substring(0, 120).replace(/\s+/g, ' ')}"${playProgress}】\n`;
    }

    // ==================== 2. YouTube 专属动态视觉与播放进度提取器 ====================
    else if (url.includes("youtube.com/watch")) {
        const yTitle = document.querySelector('ytd-watch-metadata #title yt-formatted-string')?.innerText || document.title;
        const channelName = document.querySelector('#channel-name a')?.innerText?.trim() || "未知频道";

        let playProgress = "";
        const videoEl = document.querySelector('video');
        if (videoEl) {
            const curTimeStr = formatTime(videoEl.currentTime);
            const durationStr = formatTime(videoEl.duration);
            if (!videoEl.paused) {
                playProgress = `，当前视频播放进度为 ${curTimeStr} / ${durationStr}，且正处于播放状态`;
            } else {
                playProgress = `，当前视频播放进度为 ${curTimeStr} / ${durationStr}，但已被主公暂停`;
            }
        }

        metaContext += `【系统感知：主公正在观看YouTube视频。\n`;
        metaContext += `视频标题: "${yTitle}"，频道主: "${channelName}"${playProgress}】\n`;
    }

    // ==================== 3. 其它常规网站 Open Graph 备用提取器 ====================
    else {
        const ogTitle = document.querySelector('meta[property="og:title"]')?.getAttribute('content');
        const ogDesc = document.querySelector('meta[property="og:description"]')?.getAttribute('content');
        const ogType = document.querySelector('meta[property="og:type"]')?.getAttribute('content');
        const keywords = document.querySelector('meta[name="keywords"]')?.getAttribute('content');

        if (ogTitle) {
            metaContext += `【系统感知：主公正在浏览/阅读类型为 ${ogType || "网页"} 的媒体内容。\n`;
            metaContext += `标题: "${ogTitle}"`;
            if (ogDesc) {
                metaContext += `，简介: "${ogDesc.substring(0, 150).replace(/\s+/g, ' ')}"`;
            }
            if (keywords) {
                metaContext += `，关联关键字: "${keywords}"`;
            }
            metaContext += "】\n";
        }
    }

    // 4. 备用提取常规网页正文段落
    const textElements = document.querySelectorAll('p, h1, h2, h3, article, section');
    let bodyText = "";
    for (let el of textElements) {
        if (el.offsetWidth > 0 && el.offsetHeight > 0) {
            bodyText += el.innerText.trim() + " ";
        }
        if (bodyText.length > 600) {
            break;
        }
    }

    return { text: (metaContext + bodyText).trim(), imageUrl: imageUrl };
}

let lastSentContent = "";
let scrollTimeout = null;
let videoTimer = null;
let activeVideoElement = null;
let lastSentTime = -999;

function sendToMeiling() {
    const { text, imageUrl } = safeExtractText();
    if (!text) return;

    const videoEl = document.querySelector('video');
    if (videoEl) {
        const curTime = Math.floor(videoEl.currentTime);
        if (text === lastSentContent && Math.abs(curTime - lastSentTime) < 15) {
            return;
        }
        lastSentTime = curTime;
    } else {
        if (text === lastSentContent) {
            return;
        }
    }

    console.log("[美铃感知] 正在向插件后台推送网页文本与多媒体封面图...", document.title);

    try {
        if (chrome.runtime && chrome.runtime.id) {
            chrome.runtime.sendMessage({
                action: "send_web_content",
                title: document.title,
                content: text,
                image_url: imageUrl,  // 将抓取到的封面图 JPG 地址发送给后台
                metrics: {
                    activeTime: activeTime,
                    scrollCount: scrollCount,
                    isFocused: document.hasFocus(),
                    idleTime: Math.floor((Date.now() - lastActivityTime) / 1000)
                }
            });
            lastSentContent = text;
        }
    } catch (err) {
        console.log("[美铃感知] 插件后台上下文已更新。主公请手动刷新一下本网页，即可重新恢复与美铃的连结喵~");
    }
}

// ==================== 智能视频播放监听与 25s 进程心跳 ====================
function bindVideoEvents() {
    const videoEl = document.querySelector('video');
    if (!videoEl || activeVideoElement === videoEl) return;

    activeVideoElement = videoEl;
    console.log("[美铃感知] 成功捕获到 HTML5 视频元素，开始进行底层事件监听...");

    videoEl.addEventListener('play', () => {
        console.log("[美铃感知] 原生监听：主公启动/恢复了视频播放");
        sendToMeiling();
        startVideoHeartbeat();
    });

    videoEl.addEventListener('pause', () => {
        console.log("[美铃感知] 原生监听：主公暂停了视频播放");
        sendToMeiling();
        stopVideoHeartbeat();
    });

    videoEl.addEventListener('seeked', () => {
        console.log("[美铃感知] 原生监听：主公拖拽跳转了视频进度");
        sendToMeiling();
    });

    if (!videoEl.paused) {
        startVideoHeartbeat();
    }
}

function startVideoHeartbeat() {
    if (videoTimer) clearInterval(videoTimer);
    videoTimer = setInterval(() => {
        console.log("[美铃感知] 原生心跳：主公持续观影中，同步最新播放进度...");
        sendToMeiling();
    }, 25000);
}

function stopVideoHeartbeat() {
    if (videoTimer) {
        clearInterval(videoTimer);
        videoTimer = null;
    }
}

setInterval(bindVideoEvents, 3000);

// 行为特征变量初始化
let activeTime = 0;
let scrollCount = 0;
let lastActivityTime = Date.now();

setInterval(() => {
    if (document.visibilityState === 'visible' && document.hasFocus()) {
        activeTime++;
    }
}, 1000);

window.addEventListener('scroll', () => {
    scrollCount++;
});

const updateActivity = () => { lastActivityTime = Date.now(); };
window.addEventListener('mousemove', updateActivity);
window.addEventListener('keydown', updateActivity);

setTimeout(sendToMeiling, 2500);

window.addEventListener('scroll', () => {
    if (scrollTimeout) {
        clearTimeout(scrollTimeout);
    }
    scrollTimeout = setTimeout(sendToMeiling, 3500);
});