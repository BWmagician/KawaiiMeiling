chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "send_web_content") {
        const title = message.title;
        const content = message.content;
        const imageUrl = message.image_url;  // 提取封面图链接
        const metrics = message.metrics;

        console.log("[后台服务] 收到网页抓取与多媒体特征数据，正在代表插件发起高权限直连...", title);

        fetch('http://127.0.0.1:18088/web_content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                content: content,
                image_url: imageUrl,  // 将封面图打包在 body 中一并发送给桌宠本地服务器
                metrics: metrics
            })
        })
            .then(res => console.log("[后台服务] 成功突破网页CSP阻拦，多媒体特征数据已安全送达桌宠！"))
            .catch(err => console.log("[后台服务] 无法连接到桌宠 18088 端口。"));
    }
});