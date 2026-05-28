const BLACKLIST_KEYWORDS = ['login', 'signin', 'bank', 'checkout', 'pay', 'password', 'wallet', 'mail.google'];

function isSensitivePage() {
    const url = window.location.href.toLowerCase();
    return BLACKLIST_KEYWORDS.some(keyword => url.includes(keyword));
}

function safeExtractText() {
    if (isSensitivePage()) {
        console.log("[美铃感知] 检测到敏感页面，已自动停用抓取以保护主公隐私。");
        return null;
    }

    const textElements = document.querySelectorAll('p, h1, h2, h3, article, section');
    let combinedText = "";

    for (let el of textElements) {
        if (el.offsetWidth > 0 && el.offsetHeight > 0) {
            combinedText += el.innerText.trim() + " ";
        }
        if (combinedText.length > 800) {
            break;
        }
    }
    return combinedText.trim();
}

function notifyBackground() {
    const text = safeExtractText();
    if (!text) return;

    console.log("[美铃感知] 正在向插件后台推送数据以绕过网页CSP阻拦...");

    // 单向发送给后台 background.js，极其稳定且不被网页安全机制拦截
    chrome.runtime.sendMessage({
        action: "send_web_content",
        title: document.title,
        content: text
    });
}

// 页面载入 1.2 秒后执行抓取
setTimeout(notifyBackground, 1200);