"""案例一：盯一个 GitHub 仓库，有新提交就推企微。

不调 GitHub API（有速率限制），读 commits.atom 订阅源，免认证。
只在最新 commit 的 sha 变化时推送，避免每次检查都刷屏。
"""
import os
import re
import json
import time
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error

from wecom_group_bot import push

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".state.json")
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_latest(repo: str, branch: str = "") -> dict:
    """取最新一条提交。私有仓库需要自行加 token，这里只处理公开仓库。

    branch 留空 = 用仓库默认分支（推荐）。
    这一点很关键：很多老仓库默认分支叫 master 不叫 main，
    写死 main 会直接 404，而 404 不会告诉你到底是仓库名错了还是分支名错了。
    """
    path = f"commits/{branch}.atom" if branch else "commits.atom"
    url = f"https://github.com/{repo}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "repo-watch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(
                f"404：找不到 {repo} 的分支「{branch or '默认'}」。"
                f"去仓库首页看一眼默认分支到底叫 main 还是 master。"
            ) from e
        raise

    entries = root.findall(f"{ATOM}entry")
    if not entries:
        raise RuntimeError("atom 里没有 entry，检查仓库名或分支名")

    first = entries[0]

    # atom 的 <id> 不是裸 sha，长这样：tag:github.com,2008:Grit::Commit/<40位hex>
    # 直接拿来当 sha 会得到 "tag:git" 这种垃圾，比对永远不相等，也就永远不推送
    raw_id = first.findtext(f"{ATOM}id", "").strip()
    m = re.search(r"([0-9a-f]{40})", raw_id)
    sha = m.group(1) if m else raw_id

    link_el = first.find(f"{ATOM}link")
    link = link_el.get("href") if link_el is not None else ""
    if not m and link:
        tail = link.rstrip("/").split("/")[-1]
        if re.fullmatch(r"[0-9a-f]{7,40}", tail):
            sha = tail

    title = (first.findtext(f"{ATOM}title", "") or "").strip()
    updated = first.findtext(f"{ATOM}updated", "") or ""
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


def check_once(repo: str, branch: str = "", dry_run: bool = False) -> str | None:
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
    branch = os.environ.get("GH_BRANCH", "")   # 留空=用仓库默认分支
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
