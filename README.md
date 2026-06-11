# Auto Form 社区志愿活动自动报名辅助工具

这是一个面向社区志愿活动报名场景的自动化辅助工具。它可以根据配置打开活动报名表单，填写固定个人信息，识别当前可报名的活动项，并在确认活动可选后自动提交。

项目的核心目标是减少重复填写表单的机械操作，同时避免误报已满活动。脚本不会依赖 `field_4`、`field_10` 这类会随链接变化的内部编号，而是按页面标题定位字段，例如“姓名”“学号”“活动项”“学院名称”。

## 1. 从零开始准备运行环境

以下命令以 Windows PowerShell 为例。

### 1.1 安装 uv

`uv` 是本项目使用的 Python 环境和依赖管理工具。第一次使用时先安装它：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

如果系统已经安装了 `winget`，也可以使用：

```powershell
winget install --id=astral-sh.uv -e
```

安装完成后，关闭并重新打开 PowerShell，然后验证：

```powershell
uv --version
```

### 1.2 获取项目代码

如果还没有下载项目：

```powershell
git clone https://github.com/callme110/Auto_Form.git
cd Auto_Form
```

如果已经在项目目录中，可以跳过这一步。

### 1.3 安装项目使用的 Python

项目根目录里已经包含 `.python-version`，当前使用 Python 3.13。可以让 `uv` 自动安装并管理这个 Python 版本：

```powershell
uv python install 3.13
```

确认 Python 可用：

```powershell
uv run python --version
```

### 1.4 创建虚拟环境并安装依赖

在项目根目录运行：

```powershell
uv sync
```

这一步会根据 `pyproject.toml` 和 `uv.lock` 创建 `.venv` 虚拟环境，并安装 Playwright 等 Python 依赖。

### 1.5 安装 Playwright 浏览器

Playwright 依赖安装好后，还需要安装实际用于自动化操作的浏览器。项目只需要 Chromium：

```powershell
uv run playwright install chromium
```

### 1.6 检查脚本是否能启动

```powershell
uv run python main.py --help
```

能看到命令行帮助信息，就说明基础环境已经准备好。

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
  "building": "你的楼栋",
  "college": "你的学院",
  "student_source": "内招生",
  "political_status": "共青团员"
}
```

说明：

- `form_url`：每次活动的新表单链接。
- `building`：所住楼栋，例如 `T1`、`T12`、`锦溪苑`。
- `student_source`：表单里的“生源类别”，例如 `内招生` 或 `外招生`。
- `political_status`：表单里的“政治面貌”，必须和页面选项文字一致。

`config.json` 包含个人信息，已经被 `.gitignore` 忽略，不会上传到 GitHub。

## 3. 测试填写但不提交

测试新链接时，先运行：

```powershell
uv run python main.py --dry-run
```

如果活动项已满或被禁用，脚本会停止并输出原因，不会提交。

## 4. 正式运行并提交

确认 dry-run 没问题后运行：

```powershell
uv run python main.py
```

脚本会自动：

1. 打开 `config.json` 里的表单链接。
2. 填写姓名、学号、手机、楼栋、学院、生源类别、政治面貌。
3. 在“活动项”或“活动项目”字段里选择第一个可报名活动。
4. 点击“提交”。

## 5. 常见情况

如果看到类似提示：

```text
没有可报名的活动项目: xxx(名额已满，请等待下次志愿活动)
```

表示页面里的活动项已经满额，底层 radio 通常也是 `disabled=true`，脚本不会强行提交。
