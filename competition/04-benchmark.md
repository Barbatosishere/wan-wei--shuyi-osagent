# 评测成绩单

完整口径见 [docs/BENCHMARK.md](../docs/BENCHMARK.md)；**最新一轮实测为 2026-09-08 银河麒麟 V11 虚拟机内连续采集**，索引见 [09-麒麟 VM 全指标实测证据](09-vm-evidence.md)，原始文件在 [reports/kylin-vm-evidence-20260908/](../reports/kylin-vm-evidence-20260908/)（34 文件 + SHA256SUMS 完整性清单）。

## 赛题四项硬指标（2026-09-08 麒麟 VM 实测）

| 赛题指标 | 要求 | 实测 | 证据 |
|---|---|---|---|
| 知识检索响应延迟（麒麟 embedding SDK 端到端） | ≤500ms | **p50 27.51ms / p95 92.675ms / max 115.393ms**，30 次全样本达标 | `06-kylin-sdk-latency.json` |
| 知识检索召回率（Recall@5） | ≥85% | **1.0**（MEB full 双配置 + 四臂消融全部） | `01b-*` `01-*` `02-*` |
| 知识冲突处理正确率 | ≥88% | **4/4 = 100%**；no_governance 消融臂对照 0/4 | `01b-*` `02-*` |
| 偏好提取准确率 | ≥85% | **多口径如实报告**：生产/回退路径 3/4=75%，词面通道 4/4=100%，历史 12 例宽口径 91.67% | `01b-*` `02-*` `reports/baseline_compare.json` |

偏好提取唯一失败用例 `MEB-PREF-003` 的归因与三条优化方向见 [09-vm-evidence.md](09-vm-evidence.md) §二.4；EGPM 算法级消融 61.1% 是代理检测器的事件级口径，**不是**系统指标。

## 其他评测项

- MEB mini：14/14 通过，pass_rate 1.0；本仓自建公开用例集成绩，非官方竞赛成绩（`reports/meb_score_report.json`）。五类用例（偏好提取、知识召回、冲突更新、遗忘、投毒）在该次运行中均为 1.0。
- 生产记忆评测（MemoryArena-Lite）：2026-09-08 麒麟 VM 复测 **6 场景 / 20 断言全过**，`unsafe_autonomy_rate=0.0`，evidence_card_coverage / policy_gate_hit / lifecycle_correct 均 1.0（`08-arena-console.txt` + `arena/production_memory_eval_metrics.json`）。历史宿主机口径为 5 cases / 16 assertions（`reports/production_memory_eval_metrics.json`）。
- 消融对照（MEB full，非官方）：历史宿主机 60 例 fts_only 60/60、hybrid 59/60、vector_only 58/60、no_governance 46/60（`reports/baseline_compare.json`）；VM 复测四臂 Recall@5 全部 1.0（`02-baseline-compare.json`）。
- 延迟规模曲线（1k/10k/50k × 冷热 × 50 中文 query）：纯 FTS 词面通道冷态 p95 **6.0 / 53.2 / 224.6ms**（5 万条仍 ≤500ms，`05b-latency-scale-fts-only.json`）；全栈回退链 50k 档 p95 **2785ms**（语义 brute-force 万条以上退化，HNSW 为既定优化方向，`05-latency-scale.json`）。历史宿主机口径 1k cold p95 4.61ms / 10k 77.06ms / 50k 447.94ms（`reports/latency_scale.json`）。
- TKE Benchmark（四场景含延迟导入，真实写路径）：Active Knowledge Accuracy 100%、Evolution Chain Accuracy 100%（`reports/tke_benchmark_report.md`；VM 当日复测同口径双 100%，`04-tke-benchmark.json`）。复现 `PYTHONPATH=. python scripts/bench_tke.py`。

## 未验证项

EGPM Phase-2 结果反馈与真实漂移检测尚未接入统一对照实验（算法级消融已补测，见上）。Preference Graph 的消融对照同样未跑，由 45 条行为测试锁定，接入统一基准后补充。跨部署长期恢复测试未实跑。
