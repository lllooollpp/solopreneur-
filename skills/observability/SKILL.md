---
name: observability
description: "可观测性与可靠性技能。用于 SLI/SLO 建模、告警策略、发布后健康检查与故障处置建议。"
metadata: {"nanobot":{"emoji":"📈","always":false}}
---

# 可观测性与可靠性技能

## 四大黄金信号

1. 延迟（Latency）
- P50/P95/P99 响应时间

2. 流量（Traffic）
- QPS、吞吐、请求分布

3. 错误（Errors）
- 4xx/5xx 比例、异常堆栈趋势

4. 饱和度（Saturation）
- CPU、内存、连接池、队列积压

## SLO 模板

```markdown
- SLI: 接口成功率
- SLO: 30天窗口 >= 99.9%
- Error Budget: 0.1%
- 观测来源: APM + 日志 + 指标
```

## 发布后验证清单

- [ ] 关键 API 错误率无显著上升
- [ ] P95 延迟在基线阈值内
- [ ] 无新增高优先级告警
- [ ] 业务关键漏斗无明显下滑
- [ ] 容量边界仍有余量

## 处置建议模板

- 立即动作（0-1h）
- 短期动作（24h）
- 长期动作（1-2 周）
