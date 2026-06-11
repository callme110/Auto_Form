# Auto Form 自动填表脚本

这个项目用于自动打开金数据/金数据新版表单链接，填写固定个人信息，自动选择可报名的活动项，并提交表单。

脚本不会依赖 `field_4`、`field_10` 这类会随链接变化的内部编号，而是按页面标题定位字段，例如“姓名”“学号”“活动项”“学院名称”。

## 1. 安装依赖

项目使用 `uv` 管理依赖：

```powershell
uv sync
```

首次运行 Playwright 时，需要安装浏览器：

```powershell
uv run playwright install chromium
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
