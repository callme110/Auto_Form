import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


FULL_ACTIVITY_HINTS = ("名额已满", "等待下次", "已结束", "不可报名")
FIELD_SELECTOR = ".ant-form-item, [class*='FormField'][class*='root']"
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


def load_config(path: str) -> dict[str, str]:
    config_path = Path(path)
    if not config_path.exists():
        raise RuntimeError(f"配置文件不存在: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    missing = [key for key in REQUIRED_CONFIG if not config.get(key)]
    if missing:
        raise RuntimeError(f"配置文件缺少字段: {', '.join(missing)}")

    return config


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="自动填写并提交金数据志愿活动表单")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只填写，不提交")
    parser.add_argument("--headless", action="store_true", help="不显示浏览器窗口")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        config = load_config(args.config)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=args.headless)
            page = browser.new_page()

            try:
                selected_activity = fill_form(page, config)
                print(f"已选择活动: {selected_activity}")

                if args.dry_run:
                    print("dry-run 模式：已填写，但未提交。")
                    return

                page.get_by_role("button", name=re.compile(r"^提交$")).click()
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeoutError:
                    pass

                print("表单已提交。")
            finally:
                browser.close()
    except RuntimeError as error:
        print(f"错误: {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
