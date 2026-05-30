## 写在前面
图的画师是sseun_3，感觉超级萌ww

想做这个东西是因为在b站刷到了【[【3分钟oc教程】智能对话ai多功能桌宠，零基础也能一键个性化制作！](https://www.bilibili.com/video/BV1MaSeBPEus/?spm_id_from=333.1391.0.0)这个视频，感觉思路很好，就直接做了一个

还让ai写了个google的插件，直接开开发者模式在extension里面加入meiling_chrome这个文件夹就行了。考虑到一些隐私问题，抓取网页可能是最合适的交互方式了，如果要读取电脑的全部信息，或所有输入信息感觉还是有点危险，毕竟用的是api。

你可以在刷新页面之后看inspect里的console有没有出现“ 红美铃”的字样，来测试这个插件有没有生效。

我之前怕加了个捕获页面会很烧token，我就加了一个本地的ollama当中间人压缩信息量，~~虽然可能会很慢，所以用了千问0.5b的迷你模型。~~ gamma4.0 更好用，更强，跑的也不慢

具体的，你可以在config里修改这些信息，默认用了deepseek的api，可以用其他的。~~更详细的信息其实ai比我知道的更清楚~~

## 关于gen1

目前只有一个很蠢的chrome插件抓取信息和duckduckgo的搜索，说实话准确度非常不尽人意ww，但是陪你瞎掰应该没啥问题了hh


# 红美铃（Hong Meiling）智能桌面助手说明文档

这是一个基于 **PyQt5** 框架，采用 **本地轻量级大模型（Ollama） + 云端大模型（DeepSeek） 混合编排架构** 开发的跨平台桌面助理宠物。项目以《东方Project》中红魔馆的门番——**红美铃** 为角色设定，具备极高的系统级感知、环境自适应避让和长期记忆存储能力。

---

## 📂 模块架构与分工

项目采用“脑、体、件（Widgets）三分离”的设计模式进行模块化解耦，保证了各部分的独立调试与极致的运行效率：

1.  **`oc.py`（物理身体）**：
    *   负责 PyQt5 无边框、透明视窗的渲染与事件分发。
    *   控制物理滑行动画、位置避让算法、双端自启动注入。
    *   管理防打扰冷却时钟、主动交互休眠计时器。
    *   在 Windows 启动时自动调用本地二进制 PNG 净化器，剥离脏数据以消灭 `libpng` 警告。
2.  **`brain.py`（中央大脑）**：
    *   管理常驻后台的 HTTP 本地服务（`18088` 端口），接收浏览器插件发来的网页数据。
    *   调度异步工作线程（`QThread`），规避主线程阻塞，保证打字输入和回车递茶零卡顿。
    *   调用本地 Ollama API 进行脱敏和提炼总结。
    *   调用云端 DeepSeek 兼容接口，并解析返回结果中的 `[ACTION]`、`[MOVE]`、`[PIN]` 标签。
3.  **`widgets.py`（国风组件库）**：
    *   封装了 `GuofengTextEdit`（支持回车发送、Shift+回车换行的自适应高度文本框）。
    *   封装了 `HistoryWindow`（“红魔馆门番交往日志”），支持无边框鼠标拖动，以古风卷轴界面动态还原 memory.json 中的对话往来记录。
4.  **`config.json`（静态配置）**：保存系统级密钥、网络接口及运行阈值。
5.  **`memory.json`（长期记忆）**：保存美铃对主公的用户画像描述、唤醒计数（好感度）和滚动对话上下文。
6.  **`Meiling-Senser/`（Chrome 插件）**：
    *   `content.js` 负责在网页加载完成后，自动安全嗅探非敏感静态段落文本。
    *   `background.js` 通过浏览器高特权 Service Worker 发起本地回环请求，彻底绕过各大网站的 CSP（内容安全策略）拦截限制。

---

## ⚙️ 可调控变量与参数说明

项目将所有易变、敏感和控制体验相关的变量提取为配置，您可以无损调节以下参数：

### 1. `config.json` 核心业务参数
*   **`deepseek_api_key`** (String): 云端大模型的 API Key。
*   **`deepseek_api_url`** (String): 云端大模型的通信端点（全面兼容原生 DeepSeek、硅基流动 SiliconFlow、OpenRouter 等所有符合 OpenAI 格式的接口）。
*   **`deepseek_model`** (String): 云端调用的具体模型 ID。例如：DeepSeek 官方为 `"deepseek-chat"`；硅基流动可设为 `"deepseek-ai/DeepSeek-V3"` 或 `"deepseek-ai/DeepSeek-R1"`。
*   **`ollama_api_url`** (String): 本地 Ollama 的网关地址，默认为 `"http://localhost:11434/api/generate"`。
*   **`ollama_model`** (String): 本地决策小模型的 ID，推荐使用极速的 `"qwen2.5:0.5b"`（300M大小，毫秒级响应）或 `"qwen2.5:1.5b"`。
*   **`idle_sleep_timeout_seconds`** (Int): 闲置休眠超时阈值（单位：秒，默认 120 秒）。当主公在指定时间内没有任何主动交互，美铃就会倚着长枪睡着。

### 2. `oc.py` 控制台与视窗参数
*   **`os.environ["QT_SCALE_FACTOR"]`** (Float): Windows 专属一键全局无损缩放系数（默认为 `"1.3"`，即放大 1.3 倍）。可按需微调为 `1.4`、`1.5` 等，UI 排版和图片会自动无损放大，解决高分屏字小、模糊的问题。
*   **被动感知冷却时间** (`now - self.last_comment_time < 10`): 限制被动感知（剪贴板复制、网页刷新）的最小时间间隔（单位：秒，默认 10 秒），防止高频刷屏打扰。
*   **打字机打印字延迟** (`self.typewriter_timer.start(80)`): 字符逐字打印的间隔时间（单位：毫秒，默认 80毫秒）。
*   **嘴巴摆动间隔** (`self.mouth_timer.start(180)`): 说话时口型切换频率（单位：毫秒，默认 180毫秒）。

### 3. `brain.py` 模型参数
*   **Ollama 提速选项 (`options`)**：
    *   `"num_predict": 80`: 本地小模型最大生成字符数。强行限制出字长度，既保障了 JSON 括号闭合的安全富余，又将本地决策时间死死卡在毫秒级。
    *   `"temperature": 0.1`: 降低小模型生成的随机性，使其决策逻辑更干脆。
*   **DeepSeek 限制**：
    *   `timeout=10` (Int): 设定云端请求 10 秒超时，防止因云端服务拥堵导致桌宠无限期卡死。

---

## 🏷️ 大模型自主控制标签规范（Label System）

在大脑提示词中，我们为美铃构建了一套完整的**“物理自主权指令集”**。云端 DeepSeek 生成文本时，会智能在句尾附带以下格式的闭合指令，桌宠客户端解析后会自动执行相应的物理控制：

### 1. 表情姿态控制 `[ACTION: {state}]`
*   `[ACTION: idle]`：切换至标准闭嘴看门立绘（`action1.png`）。
*   `[ACTION: talk]`：切换至张嘴大笑立绘（`action2.png`）。
*   `[ACTION: sleep]`：切换至闭眼酣睡立绘（`action4.png`），自动屏蔽后续所有的网页和剪贴板感知骚扰，进入静音浅睡状态。

### 2. 物理位移控制 `[MOVE: {position}]`
*   `[MOVE: top_left]`：平滑飞奔至屏幕左上角。
*   `[MOVE: top_right]`：平滑飞奔至屏幕右上角。
*   `[MOVE: bottom_left]`：平滑飞奔至屏幕左下角。
*   `[MOVE: bottom_right]`：平滑飞奔至屏幕右下角。
*   `[MOVE: center]`：平滑飞奔至屏幕中央。

### 3. 视窗固定/浮动控制 `[PIN: {state}]`
*   `[PIN: lock]`：自动激活置顶模式，将美铃视窗死死固定在所有窗口的最前面。
*   `[PIN: float]`：自动解除置顶模式。允许主公自由拖拽她到处移动，或方便她在执行 `[MOVE]` 指令时顺利飞越屏幕。

*(注：这三套指令标签完全相互独立且支持并发，例如美铃可以生成：`“主公让我去左上角巡逻，我这就飞过去！[ACTION: idle][PIN: float][MOVE: top_left]”`)*

---

## ⚡ 双端一键部署与运行

为了杜绝 Windows 批处理文件常见的 ANSI 乱码问题，项目全部采用 **PowerShell (`.ps1`)** 脚本进行部署与启动：

### 1. 极简本地沙箱部署（Win/Mac 通用）
1.  在项目根目录下，按住 `Shift` 键并在空白处点击鼠标右键，选择 **“在此处打开 PowerShell 窗口”**。
2.  输入并执行以下命令解锁执行权限：
    ```powershell
    Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
    ```
3.  运行极简安装脚本：
    ```powershell
    .\install.ps1
    ```
    *（安装程序会自动在本地为您建立隔离的 `.venv` 虚拟环境，自动调用您的系统编译器将 `PyQt5` 和 `requests` 安装到沙箱中，不污染任何全局系统环境；如果本地运行了 Ollama，还会为您一键拉取极速的 0.5B 本地小模型。）*

### 2. 一键极速运行
在解锁了权限的同一个 PowerShell 窗口中，直接输入以下命令即可完成自适应启动：
```powershell
.\run.ps1
```

### 🛠 故障自排查手册（Troubleshoot）
1. 气泡弹出“气路阻塞 (错误码: 503)”：
    原因：DeepSeek 官方服务器当前处于请求过载状态，拒绝了服务。
    解决：这属于云端波动。由于我们已经将模型剥离到外部配置，如果您有第三方代理商密钥，可以直接打开 config.json，将 API URL 改为代理商端点，将 Model 改为代理商的模型名（如硅基流动的 DeepSeek 模型），即可绕过官方拥堵。
2. 气泡弹出“风沙太大... (详情: Read timed out)”：
    原因：请求云端时网络握手超时（超过 10 秒限制）。
    解决：请检查您的科学上网代理状态，确保云端接口 api.deepseek.com 没有被防火墙拦截。
3. 本地 Ollama 卡死或超时：
    原因：小模型第一次被加载时需要从磁盘读取至内存，容易超过 25 秒限制。
    解决：请在电脑终端手动运行一次 ollama run qwen2.5:0.5b "你好" 来预热载入模型。