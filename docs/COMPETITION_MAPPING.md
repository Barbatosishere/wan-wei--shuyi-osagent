# 赛题映射

| 需求 | 功能 | 代码位置 | 测试位置 |
|---|---|---|---|
| 可证明删除 | 五处验证、PDF 证书 | `backend/app/memoryos/governance.py` | `test_memoryos_certificate.py` |
| 防止复活 | 生命周期状态机 | `backend/app/memoryos/lifecycle.py` | `test_memoryos_lifecycle.py` |
| 审计追溯 | append-only 账本、Provenance | `backend/app/memoryos/governance.py` | `test_memoryos_governance.py` |
| 偏好治理 | Policy Gate、EGPM、Preference Graph | `backend/app/memory_runtime/preference_graph.py` | `test_preference_graph.py`、`test_preference_evolution.py`、`test_preference_conflict.py`、`test_preference_retrieval.py` |
| 知识冲突与演化 | Knowledge Evolution + TKE 双时态 | `backend/app/memory_runtime/knowledge_evolution.py`、`temporal_knowledge.py` | `test_knowledge_conflict.py`、`test_knowledge_evolution.py`、`test_temporal_knowledge.py`、`test_knowledge_timeline.py`、`test_freshness_scoring.py` |
| 知识检索 | FTS5/向量通道 | `backend/app/memory_runtime/` | `test_retrieval.py`、`test_local_embedding.py` |
| 麒麟适配 | 原生 SDK 桥接（常驻 bridge） | `native/kylin-sdk-bridge/` | `test_kylin_native_sdk.py` |
| 身份与属主隔离 | owner key 注册门槛、跨属主请求按 404 处理、数据库身份指纹 | `backend/app/security/auth.py`、`backend/app/db.py` | `test_identity_layer.py`、`test_db_identity.py`、`test_pr215_identity_boundaries.py` |
| 属主隔离（资源面） | agent/team/run、provider、workflow/audit、移动文件按 owner 隔离 | `backend/app/` 各资源模块 | `test_agent_run_owner_isolation.py`、`test_provider_owner_isolation.py`、`test_spaces_owner_isolation.py`、`test_mcp_owner_isolation.py`、`test_automation_owner_isolation.py`、`test_pr215_owner_isolation.py` |
| 安全远程会话 | LAN 一次性配对 token + 独立短期凭证、SSRF 双段校验 | `backend/app/security/` | `test_security_baseline.py`、`test_security_followup.py`、`test_security_hardening_l1l8.py` |
| 发布与交付合规 | staging 打包、发布预检、RPM/DEB 双包 | `scripts/release_preflight.py`、`desktop/packaging/` | `test_pr215_release_staging.py`、`desktop/tests/test_linux_packaging.cjs` |
| 版权头合规 | 全仓自有源码木兰 PSL v2 头 + CI 校验（`scripts/license_header.py --check`） | `scripts/license_header.py`、`.github/workflows/ci.yml` | CI 门禁（非单元测试） |
