"""最小可用的企业微信群机器人推送。

只有一个函数：把一段话发到群里。
所有密钥从环境变量读，代码里不留任何真实地址。

用法：
    export WECOM_WEBHOOK='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx'
    python wecom_group_bot.py "服务已恢复"
"""
import os
import sys
import time
import json
import urllib.request


def push(text: str, webhook: str | None = None, retries: int = 3) -> bool:
    """推一条纯文本消息。返回是否成功。

    平台本身不限制你发多少条。这里加节流和重试，纯粹是自我保护：
    程序出 bug 的时候可能一口气推几十条，把群刷成垃圾场，
    也容易触发平台侧的风控。所以宁可慢一点。
    """
    url = webhook or os.environ.get("WECOM_WEBHOOK", "")
    if not url:
        raise SystemExit("缺少 WECOM_WEBHOOK，先 export 或者写进 .env")

    payload = json.dumps(
        {"msgtype": "text", "text": {"content": text}},
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("errcode") == 0:
                    return True
                # 限流，等一下再试
                if body.get("errcode") == 45009:
                    time.sleep(3)
                    continue
                print(f"推送失败：{body}", file=sys.stderr)
                return False
        except Exception as e:
            # 网络抖动，退避后重试
            if attempt == retries - 1:
                print(f"推送异常：{e}", file=sys.stderr)
                return False
            time.sleep(2 ** attempt)

    return False


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "测试消息：通道正常"
    ok = push(msg)
    print("成功" if ok else "失败")
    # 记得去手机上确认真的收到了，别只看退出码
</content>
