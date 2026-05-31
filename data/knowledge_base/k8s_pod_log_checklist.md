# Kubernetes Pod 日志排查清单

## 排查清单

1. 确认 Pod 重启次数和最近事件
2. 检查 CPU、内存和磁盘压力
3. 核对滚动发布时间窗口
4. 对比健康 Pod 与异常 Pod 的日志差异
5. 使用 trace id 或 request id 串联相关事件
