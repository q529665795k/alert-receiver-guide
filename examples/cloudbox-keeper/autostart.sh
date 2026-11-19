#!/bin/bash
# 开机自启（案例三的第三层收尾）
#
# 机器被门铃拉起来之后，这个脚本负责把整条链路接回去。
# 关键原则：先判断，再启动。不要无脑起，否则重复进程会把机器压死。

set -u
LOG="/tmp/autostart.log"
log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

log "=== 开机自启开始 ==="

# 1. 等网络就绪（刚开机时 DNS 常常还没起来，太急会心跳全失败）
for i in $(seq 1 20); do
    if ping -c 1 -W 2 1.1.1.1 > /dev/null 2>&1; then
        log "网络就绪"
        break
    fi
    sleep 3
done

# 2. 恢复任务（断点续跑，不是从头开始）
if pgrep -f "你的任务进程关键字" > /dev/null; then
    log "任务已在跑，跳过"
else
    log "启动任务（续跑模式）"
    nohup bash -c "你的任务续跑命令" >> "$LOG" 2>&1 &
fi

# 3. 拉起看门狗（它自己也是常驻进程，别重复起）
if pgrep -f "watchdog.sh" > /dev/null; then
    log "看门狗已在跑，跳过"
else
    log "启动看门狗"
    nohup bash "$(dirname "$0")/watchdog.sh" >> "$LOG" 2>&1 &
fi

log "=== 开机自启完成 ==="
</content>
