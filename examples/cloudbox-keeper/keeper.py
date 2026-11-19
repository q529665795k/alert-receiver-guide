"""门铃服务（案例三的第二层）。

职责只有两件事：
  1. 接收云主机定时发来的心跳 GET /ping
  2. 接收云平台的回收事件 POST /hook，然后反过来把机器开起来

为什么需要这一层：机器被回收后，机器上的看门狗也跟着死了，
必须有一个「永远醒着」的东西从外部观察和拉起。
"""
import os
import time
import hashlib
import hmac
import json
import urllib.request
from flask import Flask, request, jsonify

app = Flask(__name__)

# 最后一次心跳时间（内存即可，重启丢一次不影响判断）
LAST_BEAT = 0.0


@app.get("/ping")
def ping():
    """云主机上的看门狗每 N 分钟敲一次。"""
    global LAST_BEAT
    LAST_BEAT = time.time()
    return jsonify({"ok": True, "ts": int(LAST_BEAT)})


@app.get("/status")
def status():
    """自己看状态：最后一次心跳距今多久，超过阈值就说明机器凉了。"""
    age = time.time() - LAST_BEAT if LAST_BEAT else None
    return jsonify({
        "last_beat_ago_sec": None if age is None else int(age),
        "alive": bool(age is not None and age < 1800),
    })


def start_machine() -> dict:
    """调云平台 API 把机器开起来。

    各平台接口不同，这里给一个通用骨架：
      POST {CLOUD_API_BASE}/machines/{id}/start
      Authorization: Bearer {CLOUD_API_KEY}
    换成你用的平台实际接口即可。
    """
    base = os.environ["CLOUD_API_BASE"].rstrip("/")
    machine = os.environ["CLOUD_MACHINE_ID"]
    key = os.environ["CLOUD_API_KEY"]

    req = urllib.request.Request(
        f"{base}/machines/{machine}/start",
        data=b"{}",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return {"status": resp.status,
                    "body": resp.read()[:200].decode("utf-8", "ignore")}
    except Exception as e:
        # 幂等：机器已经在跑时接口可能返回 409/400，这不算失败
        return {"error": str(e)}


@app.post("/hook")
def hook():
    """接收云平台的实例回收 / 关机事件。

    两个坑：
      1. 立即返回 200，不要等开机动作完成 —— 平台几秒内没回应就当失败重投
      2. 校验签名，否则别人也能调你的开机接口
    """
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if secret:
        sig = request.headers.get("X-Signature", "")
        body = request.get_data()
        expect = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return jsonify({"error": "bad signature"}), 401

    event = {}
    try:
        event = request.get_json(silent=True) or {}
    except Exception:
        pass

    print(f"[hook] 收到事件：{json.dumps(event, ensure_ascii=False)[:200]}")

    result = start_machine()
    print(f"[hook] 开机结果：{result}")

    return jsonify({"received": True}), 200


if __name__ == "__main__":
    # 免费 PaaS 通常给一个 PORT 环境变量
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
</content>
