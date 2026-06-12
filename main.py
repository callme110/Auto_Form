import argparse
import asyncio
import html
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


FULL_ACTIVITY_HINTS = ("名额已满", "等待下次", "已结束", "不可报名")
FIELD_SELECTOR = ".ant-form-item, [class*='FormField'][class*='root']"
DEFAULT_ONEBOT_WS = "ws://127.0.0.1:3001/"
TARGET_GROUP_CONFIG_KEY = "target_group"
QQ_NUMBER_CONFIG_KEY = "qq_number"
URL_PATTERN = re.compile(r"https?://[^\s<>\[\]\"'）)】》]+")
TRAILING_URL_CHARS = ".,;:!?，。；：！？、)]}）】》"
RECONNECT_DELAY_SECONDS = 5.0
REQUIRED_CONFIG = (
    "form_url",
    "name",
    "student_id",
    "phone",
    "building",
    "college",
    "student_source",
    "political_status",
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def load_config(
    path: str,
    *,
    require_form_url: bool = True,
    require_target_group: bool = False,
    require_qq_number: bool = False,
) -> dict[str, str]:
    config_path = Path(path)
    if not config_path.exists():
        raise RuntimeError(f"配置文件不存在: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    required = list(REQUIRED_CONFIG if require_form_url else REQUIRED_CONFIG[1:])
    if require_target_group:
        required.append(TARGET_GROUP_CONFIG_KEY)
    if require_qq_number:
        required.append(QQ_NUMBER_CONFIG_KEY)

    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError(f"配置文件缺少字段: {', '.join(missing)}")

    return config


def parse_int_config(value: object, key: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise RuntimeError(f"配置字段 {key} 必须是数字: {value}") from None


def resolve_target_group(args: argparse.Namespace, config: dict[str, str]) -> int:
    value = args.target_group if args.target_group is not None else config.get(TARGET_GROUP_CONFIG_KEY)
    if value in (None, ""):
        raise RuntimeError(f"配置文件缺少字段: {TARGET_GROUP_CONFIG_KEY}")

    return parse_int_config(value, TARGET_GROUP_CONFIG_KEY)


def resolve_notify_user(args: argparse.Namespace, config: dict[str, str]) -> int | None:
    if args.no_notify or args.dry_run:
        return None

    value = args.notify_user if args.notify_user is not None else config.get(QQ_NUMBER_CONFIG_KEY)
    if value in (None, ""):
        return None

    return parse_int_config(value, QQ_NUMBER_CONFIG_KEY)


def find_field(page: Page, *titles: str) -> Locator:
    fields = page.locator(FIELD_SELECTOR)

    for index in range(fields.count()):
        field = fields.nth(index)
        labels = field.locator(".ant-form-item-label label").all_inner_texts()
        label_texts = {clean_text(label) for label in labels}
        field_text = clean_text(field.inner_text(timeout=1000))

        if any(title in label_text for title in titles for label_text in label_texts):
            return field

        if any(field_text.startswith(title) for title in titles):
            return field

    raise RuntimeError(f"没有找到字段: {' / '.join(titles)}")


def wait_for_field(page: Page, *titles: str, timeout: int = 30000) -> None:
    pattern = re.compile("|".join(re.escape(title) for title in titles))
    page.locator(FIELD_SELECTOR).filter(has_text=pattern).first.wait_for(timeout=timeout)


def fill_input(page: Page, title: str, value: str) -> None:
    find_field(page, title).locator('input:not([type="radio"]), textarea').first.fill(value)


def select_dropdown(page: Page, title: str, value: str) -> None:
    field = find_field(page, title)
    combobox = field.locator("input[role='combobox']")

    if combobox.count() > 0:
        combobox.first.click()
    else:
        inputs = field.locator("input")
        buttons = field.locator("button")
        if inputs.count() > 0:
            inputs.first.click()
        elif buttons.count() > 0:
            buttons.first.click()
        else:
            field.click()

    page.wait_for_timeout(800)

    option = page.locator(".ant-select-item-option, [role='option']").filter(
        has_text=re.compile(rf"^{re.escape(value)}$")
    )

    if option.count() == 0:
        box = field.bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] - 20, box["y"] + box["height"] - 20)
            page.wait_for_timeout(800)
            option = page.locator(".ant-select-item-option, [role='option']").filter(
                has_text=re.compile(rf"^{re.escape(value)}$")
            )

    if option.count() == 0:
        raise RuntimeError(f"下拉选项不存在: {value}")

    option.first.click()


def click_radio(page: Page, title: str, value: str) -> None:
    field = find_field(page, title)
    option = field.locator('label:has(input[type="radio"])').filter(
        has_text=re.compile(rf"^{re.escape(value)}$")
    )

    if option.count() == 0:
        raise RuntimeError(f"单选项不存在: {value}")

    radio = option.first.locator('input[type="radio"]').first
    if radio.is_disabled():
        raise RuntimeError(f"单选项不可选: {title} -> {value}")

    option.first.click()


def choose_activity(page: Page) -> str:
    activity_field = find_field(page, "活动项", "活动项目")
    options = activity_field.locator('label:has(input[type="radio"])')
    skipped: list[str] = []

    for index in range(options.count()):
        option = options.nth(index)
        radio = option.locator('input[type="radio"]').first
        text = clean_text(option.inner_text())

        if radio.is_disabled() or any(hint in text for hint in FULL_ACTIVITY_HINTS):
            skipped.append(text)
            continue

        option.click()
        return text

    detail = "；".join(skipped) if skipped else "未读取到活动选项"
    raise RuntimeError(f"没有可报名的活动项目: {detail}")


def fill_form(page: Page, config: dict[str, str]) -> str:
    page.goto(config["form_url"], wait_until="domcontentloaded", timeout=60000)
    wait_for_field(page, "姓名")

    fill_input(page, "姓名", config["name"])
    fill_input(page, "学号", config["student_id"])
    fill_input(page, "手机", config["phone"])
    select_dropdown(page, "所住楼栋", config["building"])

    selected_activity = choose_activity(page)

    fill_input(page, "学院名称", config["college"])
    click_radio(page, "生源类别", config["student_source"])
    click_radio(page, "政治面貌", config["political_status"])

    return selected_activity


def get_message_text_parts(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]

    if not isinstance(value, list):
        return []

    parts: list[str] = []
    for segment in value:
        if not isinstance(segment, dict):
            continue

        data = segment.get("data")
        if isinstance(data, str):
            parts.append(data)
            continue

        if isinstance(data, dict):
            for key in ("text", "url", "content"):
                item = data.get(key)
                if isinstance(item, str):
                    parts.append(item)

    return parts


def extract_urls_from_event(event: dict[str, object]) -> list[str]:
    parts: list[str] = []
    raw_message = event.get("raw_message")
    if isinstance(raw_message, str):
        parts.append(raw_message)

    parts.extend(get_message_text_parts(event.get("message")))

    urls: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for match in URL_PATTERN.findall(html.unescape(part)):
            url = match.rstrip(TRAILING_URL_CHARS)
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

    return urls


def is_target_group_message(event: dict[str, object], target_group: int) -> bool:
    try:
        group_id = int(event.get("group_id", 0))
    except (TypeError, ValueError):
        return False

    return (
        event.get("post_type") == "message"
        and event.get("message_type") == "group"
        and group_id == target_group
    )


def run_form(config: dict[str, str], *, dry_run: bool, headless: bool) -> tuple[str, bool]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            selected_activity = fill_form(page, config)
            print(f"已选择活动: {selected_activity}")

            if dry_run:
                print("dry-run 模式：已填写，但未提交。")
                return selected_activity, False

            page.get_by_role("button", name=re.compile(r"^提交$")).click()
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except PlaywrightTimeoutError:
                pass

            print("表单已提交。")
            return selected_activity, True
        finally:
            browser.close()


def build_notify_message(config: dict[str, str], selected_activity: str, form_url: str) -> str:
    name = config.get("name", "用户")
    return f"{name} 提交成功，已获取名额。活动：{selected_activity}。链接：{form_url}"


async def send_private_message(
    websocket: object,
    user_id: int,
    message: str,
    *,
    timeout: float = 5.0,
) -> None:
    echo = f"notify-{uuid.uuid4().hex}"
    request = {
        "action": "send_private_msg",
        "params": {
            "user_id": user_id,
            "message": message,
        },
        "echo": echo,
    }

    await websocket.send(json.dumps(request, ensure_ascii=False))

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        raw_response = await asyncio.wait_for(websocket.recv(), timeout=remaining)
        try:
            response = json.loads(raw_response)
        except json.JSONDecodeError:
            continue

        if not isinstance(response, dict) or response.get("echo") != echo:
            continue

        if response.get("status") == "ok" or response.get("retcode") == 0:
            print(f"已发送成功通知给 QQ {user_id}")
            return

        raise RuntimeError(f"通知发送失败: {response}")

    raise RuntimeError("通知发送超时")


async def listen_onebot(args: argparse.Namespace, config: dict[str, str]) -> None:
    import websockets

    seen_urls: set[str] = set()
    onebot_token = args.onebot_token or os.environ.get("ONEBOT_TOKEN")
    headers = {"Authorization": f"Bearer {onebot_token}"} if onebot_token else None

    while True:
        try:
            async with websockets.connect(args.onebot_ws, additional_headers=headers) as websocket:
                print(f"已连接 NapCat OneBot WebSocket: {args.onebot_ws}")
                print(f"只处理群号: {args.target_group}")

                async for raw_message in websocket:
                    try:
                        event = json.loads(raw_message)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(event, dict):
                        continue

                    if not is_target_group_message(event, args.target_group):
                        continue

                    urls = extract_urls_from_event(event)
                    if args.url_pattern:
                        urls = [url for url in urls if re.search(args.url_pattern, url)]

                    for url in urls:
                        if url in seen_urls:
                            continue

                        print(f"发现目标群链接: {url}")

                        link_config = dict(config)
                        link_config["form_url"] = url

                        try:
                            selected_activity, submitted = await asyncio.to_thread(
                                run_form,
                                link_config,
                                dry_run=args.dry_run,
                                headless=args.headless,
                            )
                        except RuntimeError as error:
                            print(f"处理链接失败: {error}", file=sys.stderr)
                            continue
                        except Exception as error:
                            print(f"处理链接异常: {error}", file=sys.stderr)
                            continue

                        if submitted and args.notify_user and not args.no_notify:
                            notify_message = build_notify_message(config, selected_activity, url)
                            try:
                                await send_private_message(websocket, args.notify_user, notify_message)
                            except Exception as error:
                                print(f"通知发送失败: {error}", file=sys.stderr)

                        seen_urls.add(url)

                        if args.once:
                            return

            print("NapCat OneBot WebSocket 已断开，准备重连。", file=sys.stderr)
        except OSError as error:
            print(f"无法连接 NapCat OneBot WebSocket: {args.onebot_ws} ({error})", file=sys.stderr)

        await asyncio.sleep(args.reconnect_delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="自动填写并提交社区志愿活动报名表单")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只填写，不提交")
    parser.add_argument("--headless", action="store_true", help="不显示浏览器窗口")
    parser.add_argument("--listen-onebot", action="store_true", help="监听 NapCat OneBot 群消息链接")
    parser.add_argument("--onebot-ws", default=DEFAULT_ONEBOT_WS, help="NapCat OneBot WebSocket 服务端地址")
    parser.add_argument("--onebot-token", help="NapCat OneBot 访问 token，也可用 ONEBOT_TOKEN 环境变量")
    parser.add_argument("--target-group", type=int, help="覆盖 config.json 中的 target_group 目标群号")
    parser.add_argument("--notify-user", type=int, help="覆盖 config.json 中的 qq_number 通知对象")
    parser.add_argument("--no-notify", action="store_true", help="提交成功后不发送 QQ 私聊通知")
    parser.add_argument("--url-pattern", help="只处理匹配这个正则表达式的链接")
    parser.add_argument("--once", action="store_true", help="监听模式下成功处理一个链接后退出")
    parser.add_argument("--reconnect-delay", type=float, default=RECONNECT_DELAY_SECONDS, help="监听断开后的重连等待秒数")
    parser.add_argument("--keep-listening", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        config = load_config(
            args.config,
            require_form_url=not args.listen_onebot,
            require_target_group=args.listen_onebot and args.target_group is None,
            require_qq_number=(
                args.listen_onebot
                and not args.dry_run
                and not args.no_notify
                and args.notify_user is None
            ),
        )
        if args.listen_onebot:
            args.target_group = resolve_target_group(args, config)
        args.notify_user = resolve_notify_user(args, config)

        if args.listen_onebot:
            asyncio.run(listen_onebot(args, config))
            return

        run_form(config, dry_run=args.dry_run, headless=args.headless)
    except RuntimeError as error:
        print(f"错误: {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
