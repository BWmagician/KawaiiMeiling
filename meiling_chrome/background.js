// 监听来自网页注入脚本的单向推送
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "send_web_content") {
        const title = message.title;
        const content = message.content;

        console.log("[后台服务] 收到网页抓取数据，正在代表插件发起高权限直连...", title);

        // 在 background service worker 中发起 fetch，完全不受网页 CSP 规则限制！
        fetch('http://127.0.0.1:18088/web_content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                content: content
            })
        })
            .then(res => console.log("[后台服务] 成功突破网页CSP，数据已送达桌宠！"))
            .catch(err => console.log("[后台服务] 无法连接到桌宠 18088 端口。"));
    }
});