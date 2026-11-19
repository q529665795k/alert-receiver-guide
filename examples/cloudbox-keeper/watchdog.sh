#!/bin/bash
# 门铃看门狗（案例三的第一层，跑在云主机上）
#
# 干什么：
#   1. 每 5 分钟向门铃服务敲一次心跳 —— 让外部知道"我还活着"
#   2. 每次心跳顺便检查任务进程，死了就拉起来
#
# 不干什么：
#   它不负责重启整台机器。机器死了它自己也没了，
#   所以机器层面的恢复必须靠门铃从外部拉起。

set -u

KEEPER_URL="${KEEPER_URL:-你自己的门铃地址}"
TASK_PATTERN="${TASK_PATTERN:-你的任务进程关键字}"
TASK_CMD="${TASK_CMD:-你的任务启动命令}"
INTERVAL="${INTERVAL:-300}"
LOG="${LOG:-/tmp/watchdog.log}"

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

beat() {
    if curl -sf -m 10 "$KEEPER_URL/ping" > /dev/null; then
        log "心跳 ok"
    else
        log "心跳失败（门铃不通或网络问题）"
    fi
}

ensure_task() {
    if pgrep -f "$TASK_PATTERN" > /dev/null; then
        log "任务在跑"
    else
        log "任务不在了，拉起来"
        # 注意用 nohup + & 让它脱离当前会话，
        # 否则看门狗一退出任务跟着死
        nohup bash -c "$TASK_CMD" >> "$LOG" 2>&1 &
    fi
}

log "看门狗启动，间隔 ${INTERVAL}s"
while true; do
    beat
    ensure_task
    sleep "$INTERVAL"
done
