"""Load the main React routes in headless Chrome and capture browser errors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


DEFAULT_ROUTES = [
    ("candidate", "/"),
    ("candidate", "/graph"),
    ("candidate", "/diagnosis"),
    ("candidate", "/learning"),
    ("candidate", "/recommendations"),
    ("candidate", "/settings"),
    ("enterprise", "/recruitment"),
    ("enterprise", "/candidates"),
    ("enterprise", "/signals"),
    ("enterprise", "/jd-quality"),
    ("enterprise", "/graph"),
    ("enterprise", "/settings"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/demo_lightweight_validation_20260904/frontend_browser_smoke.json"),
    )
    args = parser.parse_args()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    rows = []
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(args.base_url)
        for workspace_role, route in DEFAULT_ROUTES:
            driver.execute_script(
                "window.localStorage.setItem('workspaceRole', arguments[0])",
                workspace_role,
            )
            driver.get(f"{args.base_url.rstrip('/')}{route}")
            WebDriverWait(driver, 30).until(
                lambda browser: browser.execute_script(
                    "return document.querySelector('#root')?.childElementCount > 0 "
                    "&& !document.body.innerText.includes('正在加载工作台')"
                )
            )
            severe = [
                entry["message"]
                for entry in driver.get_log("browser")
                if entry.get("level") == "SEVERE"
            ]
            rows.append(
                {
                    "workspace_role": workspace_role,
                    "route": route,
                    "final_url": driver.current_url,
                    "title": driver.title,
                    "body_text_length": len(driver.find_element("tag name", "body").text.strip()),
                    "severe_console_errors": severe,
                }
            )
    finally:
        driver.quit()

    report = {
        "status": "passed" if all(row["body_text_length"] and not row["severe_console_errors"] for row in rows) else "failed",
        "base_url": args.base_url,
        "routes": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
