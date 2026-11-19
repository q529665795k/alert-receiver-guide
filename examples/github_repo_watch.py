"""案例一：盯一个 GitHub 仓库，有新提交就推企微。

不调 GitHub API（有速率限制），读 commits.atom 订阅源，免认证。
只在最新 commit 的 sha 变化时推送，避免每次检查都刷屏。
"""
import os
import json
import time
import xml.etree.ElementTree as ET
import urllib.request

from wecom_group_bot import push

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".state.json")
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_latest(repo: str, branch: str = "main") -> dict:
    """取最新一条提交。私有仓库需要自行加 token，这里只处理公开仓库。"""
    url = f"https://github.com/{repo}/commits/{branch}.atom"
    req = urllib.request.Request(url, headers={"User-Agent": "repo-watch/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        root = ET.fromstring(resp.read())

    entries = root.findall(f"{ATOM}entry")
    if not entries:
        raise RuntimeError("atom 里没有 entry，检查仓库名或分支名")

    first = entries[0]
    sha = first.findtext(f"{ATOM}id", "").strip()
    title = (first.findtext(f"{ATOM}title", "") or "").strip()
    updated = first.findtext(f"{ATOM}updated", "") or ""
    link_el = first.find(f"{ATOM}link")
    link = link_el.get("href") if link_el is not None else ""
    author = first.findtext(f"{ATOM}author/{ATOM}name", "") or ""

    return {"sha": sha, "title": title, "updated": updated,
            "link": link, "author": author}


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_once(repo: str, branch: str, dry_run: bool = False) -> str | None:
    """检查一次。返回推送内容，没新提交返回 None。"""
    latest = fetch_latest(repo, branch)
    state = load_state()
    old = state.get(repo, {})

    # 第一次运行：只登记，不推送。否则会把你拉进来那一刻的历史提交全推一遍
    if not old:
        state[repo] = latest
        save_state(state)
        print(f"[{repo}] 首次登记：{latest['sha'][:7]} {latest['title']}")
        return None

    if old.get("sha") == latest["sha"]:
        return None

    state[repo] = latest
    save_state(state)

    msg = (
        f"📦 {repo} 有新提交\n"
        f"提交：{latest['title']}\n"
        f"作者：{latest['author']}\n"
        f"时间：{latest['updated']}\n"
        f"{latest['link']}"
    )
    if dry_run:
        print("[dry-run]", msg)
        return msg

    push(msg)
    return msg


def main() -> None:
    repo = os.environ.get("GH_REPO", "")
    if not repo:
        raise SystemExit("缺少 GH_REPO，形如 owner/repo")
    branch = os.environ.get("GH_BRANCH", "main")
    interval = int(os.environ.get("CHECK_INTERVAL", "600"))

    print(f"开始监控 {repo}（分支 {branch}），间隔 {interval}s")
    while True:
        try:
            check_once(repo, branch)
        except Exception as e:
            print(f"检查失败：{e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
</content>
