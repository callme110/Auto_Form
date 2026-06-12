# Auto Form 社区志愿活动自动报名辅助工具

这是一个面向社区志愿活动报名场景的自动化辅助工具。它可以根据配置打开活动报名表单，填写固定个人信息，识别当前可报名的活动项，并在确认活动可选后自动提交。

项目支持两种运行方式：

- 单次表单填写：从 `config.json` 读取 `form_url`，直接打开并填写表单。
- NapCat 常驻监听：通过 OneBot WebSocket 监听指定 QQ 群消息，从新消息中提取表单链接，自动填写并提交，提交成功后给指定 QQ 好友发送通知。

脚本按页面字段标题定位输入项，例如“姓名”“学号”“活动项目”“学院名称”，不会依赖 `field_4`、`field_10` 这类会随链接变化的内部编号。

## 1. 准备环境

以下命令以 Windows PowerShell 为例。

### 1.1 安装 uv

`uv` 是本项目使用的 Python 环境和依赖管理工具。

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

如果系统已经安装 `winget`，也可以使用：

```powershell
winget install --id=astral-sh.uv -e
```

安装后重新打开 PowerShell，并验证：

```powershell
uv --version
```

### 1.2 安装依赖

在项目根目录运行：

```powershell
uv sync
```

然后安装 Playwright 使用的 Chromium：

```powershell
uv run playwright install chromium
```

检查脚本是否能启动：

```powershell
uv run python main.py --help
```

## 2. 创建本地配置

复制示例配置：

```powershell
Copy-Item .\config.example.json .\config.json
```

然后修改 `config.json`：

```json
{
  "form_url": "https://example.com/form",
  "name": "你的姓名",
  "student_id": "你的学号",
  "phone": "你的手机号",
  "target_group": "你的QQ群号",
  "qq_number": "接收通知的好友QQ号",
  "building": "你的楼栋",
  "college": "你的学院",
  "student_source": "内招生",
  "political_status": "共青团员"
}
```

字段说明：

- `form_url`：单次填写模式使用的表单链接。监听模式会用群消息里的链接临时覆盖它。
- `target_group`：只监听这个 QQ 群的消息。
- `qq_number`：提交成功后接收 QQ 私聊通知的好友 QQ 号。
- `building`：所住楼栋，例如 `T1`、`T12`、`锦溪苑`。
- `student_source`：表单里的“生源类别”，例如 `内招生` 或 `外招生`。
- `political_status`：表单里的“政治面貌”，必须和页面选项文字一致。

`config.json` 包含个人信息，已经被 `.gitignore` 忽略，不会提交到 GitHub。

## 3. 单次表单填写

测试新链接时，先 dry-run，只填写但不提交：

```powershell
uv run python main.py --dry-run
```

确认 dry-run 没问题后正式提交：

```powershell
uv run python main.py
```

脚本会自动：

1. 打开 `config.json` 里的 `form_url`。
2. 填写姓名、学号、手机、楼栋、学院、生源类别、政治面貌。
3. 在“活动项”或“活动项目”字段里选择第一个可报名活动。
4. 点击“提交”。

## 4. NapCat 常驻监听

如果新表单链接来自 QQ 群消息，可以让 NapCat 负责接收消息，让本脚本负责过滤目标群、提取链接、填写表单和发送成功通知。

### 4.1 配置 NapCat WebSocket

在 NapCat WebUI 里进入网络配置，新建并启用一个 `WebSocket 服务端`（正向 WS）：

- 监听地址：本机使用 `127.0.0.1`；需要局域网访问时再使用 `0.0.0.0`。
- 端口：例如 `3001`。
- 消息格式：`array` 或 `string` 都可以，脚本会同时读取 `message` 和 `raw_message`。
- 本机使用可以不设 token；公网或局域网暴露时应设置 token 并限制访问。

### 4.2 dry-run 测试监听

先只监听和填写，不提交，也不发送成功通知：

```powershell
uv run python main.py --listen-onebot --dry-run --onebot-ws ws://127.0.0.1:3001/
```

### 4.3 正式常驻监听

确认 dry-run 没问题后运行：

```powershell
uv run python main.py --listen-onebot --onebot-ws ws://127.0.0.1:3001/
```

也可以使用项目里的启动脚本：

```powershell
.\start-listener.ps1
```

监听模式启动后会常驻运行。每当 `target_group` 指定的群出现新链接，脚本会尝试填写并提交表单。提交成功后，脚本会通过当前 NapCat 登录的 QQ，给 `qq_number` 指定的好友发送私聊通知：

```text
你的姓名 提交成功，已获取名额。活动：xxx。链接：xxx
```

### 4.4 常用监听参数

临时覆盖配置里的目标群：

```powershell
uv run python main.py --listen-onebot --target-group 123456789 --onebot-ws ws://127.0.0.1:3001/
```

临时覆盖配置里的通知对象：

```powershell
uv run python main.py --listen-onebot --notify-user 123456789 --onebot-ws ws://127.0.0.1:3001/
```

暂时不发送成功通知：

```powershell
uv run python main.py --listen-onebot --no-notify --onebot-ws ws://127.0.0.1:3001/
```

如果 NapCat 设置了访问 token：

```powershell
$env:ONEBOT_TOKEN = "你的 token"
uv run python main.py --listen-onebot --onebot-ws ws://127.0.0.1:3001/
```

调整 WebSocket 断开后的重连间隔：

```powershell
uv run python main.py --listen-onebot --onebot-ws ws://127.0.0.1:3001/ --reconnect-delay 10
```

只想成功处理一个链接后退出：

```powershell
uv run python main.py --listen-onebot --once --onebot-ws ws://127.0.0.1:3001/
```

如果群里会出现其他无关链接，可以加正则过滤：

```powershell
uv run python main.py --listen-onebot --url-pattern "kdocs|wj|ivolunteer|qq.com" --onebot-ws ws://127.0.0.1:3001/
```

启动脚本也支持覆盖参数：

```powershell
.\start-listener.ps1 -TargetGroup 123456789 -NotifyUser 123456789
```

## 5. Windows 登录后自动监听

如果希望 Windows 登录后自动启动监听，可以把下面这条命令放进任务计划程序。路径需要改成本机项目位置：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "C:\path\to\auto_form\start-listener.ps1"
```

自动监听需要同时满足：

- NapCat 已启动并登录 QQ。
- NapCat 的 OneBot WebSocket 服务端已启用。
- 本项目的监听脚本正在运行。
- 电脑和网络不会在关键时间休眠或断开。

## 6. 常见情况

如果看到类似提示：

```text
没有可报名的活动项目: xxx(名额已满，请等待下次志愿活动)
```

表示页面里的活动项已经满额，底层 radio 通常也是 `disabled=true`，脚本不会强行提交。

如果提交成功但没有收到 QQ 通知，优先检查：

- `config.json` 的 `qq_number` 是否是当前登录 QQ 的好友。
- NapCat OneBot WebSocket 是否允许发送 action 请求。
- 控制台是否出现“通知发送失败”或“通知发送超时”。
