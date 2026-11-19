"""案例二：盯一个站点/接口是否活着，状态变化才推。

核心不是「每次都告诉我它活着」，而是「挂了推一次，恢复也推一次」。
中间正常的时间段保持沉默，这才是能长期用的通知。
"""
import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

from wecom_group_bot import push

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".health.json")


def probe(url: str, timeout: int = 10) -> tuple[bool, int, float]:
    """返回 (是否正常, 状态码, 耗时毫秒)。"""
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "health-watch/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            return (200 <= code < 400), code, (time.time() - start) * 1000
    except urllib.error.HTTPError as e:
        return False, e.code, (time.time() - start) * 1000
    except Exception:
        # 超时、DNS 失败、连接被拒都算挂
        return False, 0, (time.time() - start) * 1000


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_once(url: str, dry_run: bool = False) -> str | None:
    ok, code, ms = probe(url)
    state = load_state()
    prev = state.get(url, {}).get("ok")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    state[url] = {"ok": ok, "code": code, "checked_at": now}
    save_state(state)

    # 第一次检查只登记状态，不上来就推
    if prev is None:
        print(f"首次检查：{'正常' if ok else '异常'}（{code}, {ms:.0f}ms）")
        return None

    # 没变化就闭嘴
    if prev == ok:
        return None

    if ok:
        msg = f"✅ 已恢复\n{url}\n{now}（{code}, {ms:.0f}ms）"
    else:
        msg = f"🔴 挂了\n{url}\n{now}（状态码 {code}，耗时 {ms:.0f}ms）"

    if dry_run:
        print("[dry-run]", msg)
        return msg

    push(msg)
    return msg


def main() -> None:
    url = os.environ.get("TARGET_URL", "")
    if not url:
        raise SystemExit("缺少 TARGET_URL")
    interval = int(os.environ.get("CHECK_INTERVAL", "300"))

    print(f"开始监控 {url}，间隔 {interval}s")
    while True:
        try:
            check_once(url)
        except Exception as e:
            print(f"检查失败：{e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
