# 麒麟验证

**最新一轮为 2026-09-08 银河麒麟桌面操作系统 V11 虚拟机内当日连续采集**，索引见 [09-麒麟 VM 全指标实测证据](09-vm-evidence.md)，原始文件在 [reports/kylin-vm-evidence-20260908/](../reports/kylin-vm-evidence-20260908/)（SHA256SUMS 覆盖 33 个入库文件）。

## 实测环境

| 项 | 值 |
|---|---|
| 操作系统 | 银河麒麟桌面操作系统 V11（Build 20260212，buildid 83681，KYLIN_RELEASE_ID=2603） |
| 内核 | 6.6.0-63-generic #63-KYLINOS SMP PREEMPT_DYNAMIC x86_64 |
| 虚拟化 | Hyper-V，4 vCPU（AMD Ryzen 9 7845HX）/ 7.8 GiB RAM |
| Python | 3.12.3（V11 系统自带，venv 自建未被 KSAF/KYSEC 拦截） |
| 麒麟向量引擎 | `kylin-ai-vector-engine` 常驻；bridge `/usr/local/bin/wanwei-kylin-sdk-bridge` |
| 嵌入模型 | 生产路径 `ensemble-embd_gte-base_uint8-text`（768 维）；回退 bge-small-zh（512 维） |

## 检索与延迟

- **麒麟原生 embedding+vector SDK 常驻 bridge 端到端检索：p50 27.51ms、p95 92.675ms、max 115.393ms**（30 次计时 + 1 次预热剔除，全部请求 `backend=kylin_native`，`06-kylin-sdk-latency.json`）。相对 2026-07 旧证据的 one-shot 冷启动口径（p50 195.320ms / p95 246.473ms，`reports/kylin-native-sdk-evidence/latency.json`），常驻 bridge 把模型加载移出请求路径，端到端 p95 由 246.5ms 降至 92.7ms。
- v1.0.0 验收口径（宿主机，2026-09-05）：HTTP 全链路 p50 29ms / p95 83ms，SDK 单次 15ms。
- 规模曲线（1k/10k/50k × 冷热 × 50 中文 query）：纯 FTS 词面通道冷态 p95 6.0 / 53.2 / 224.6ms；全栈回退链 50k 档 p95 2785ms（语义 brute-force 余弦万条以上退化，HNSW 为既定优化方向）。

## 后端在 V11 原样运行（issue #206-D/E 回传）

- **CI 等价配置全量后端回归：1870 passed / 2 failed / 7 skipped**（`07b-pytest-ci-config.txt`）。唯二失败为 `test_pr215_release_staging` 两例——该测试读取 git 提交档案，而证据树是 tarball 解包无 `.git`，与麒麟无关。
- **全能力配置回归：1866 passed / 9 failed / 4 skipped**（`07-pytest-backend.txt`）。9 例失败逐条归因：7 例是目标机具备而 CI 不具备的能力（真实 bridge、本地语义模型）导致测试假设不成立（例：`test_semantic_recall_without_shared_words` 期望走本地通道，实际麒麟 SDK 通道先命中——生产路径表现优于测试预期）；2 例同上 `.git` 问题。**无一是产品在麒麟上的功能回归。**

## 真实场景全链路（赛题要求 ≥1 个应用案例）

`09c-*` —— 麒麟 VM 内以生产配置（检索后端实测 `kylin_native`）运行后端，完成：明文口令写入被 Policy Gate S3 硬拦截 → 可治理敏感内部知识入库 → 跨会话检索召回 → 自然语言驱动遗忘 → 主表 / FTS / 图边 / 向量引用 / 遗留表五处残留取证全零 → 导出含审计编号的 PDF 删除证明证书（`09c-demo-governance.txt` / `09c-deletion-certificate.pdf`）。

## V11 环境行为观测

detached（`nohup` 脱离 SSH 会话）的 Python 进程访问本机回环端口报 `EPERM`，**同批 curl 不受影响**；attached 会话内 curl / venv python / 系统 python 三个客户端均返回 200，**不复现**（detached 侧复现 3 次，`09-*` / `09b-*`）。这是 V11 的环境行为观测，非产品缺陷。部署建议：桌面常驻服务由 systemd 用户单元拉起（有会话归属），避免纯 `nohup` 脱离会话运行 Python 客户端。

## 桌面端形态

采用 Electron，支持 XDG 用户目录、UKUI 主题、托盘、防睡眠，以 **deb 与 rpm 双包**交付（v1.0.0 起含 RPM 发版流水线，PR #212）。原生向量 SDK 不可用时回退 FTS5，检索响应的 `retrieval.backend` 字段如实标注当前通道（`kylin_native` / `fts_fallback`）。145 项手机 API 麒麟实机验收通过（PR #215 实机验收记录：两轮 145/145，2026-09-07；该轮为 VM 内一次性验收脚本，未入库为可复跑脚本，仓库内手机相关测试套件 30 条）。当前项目为**单节点形态（v1.0.0 已发布）**，不宣称生产级高可用。

兼容性验证清单见 Issue #206。
