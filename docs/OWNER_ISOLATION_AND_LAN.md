# 身份隔离、LAN 会话与升级说明

本文说明 PR #215 的身份与远程访问约束。完整源码保留手机伴侣；Linux 发布安装包通过 staging 清理移动入口，见 [桌面构建说明](../desktop/README.md)。

## 身份与资源归属

- 配置的 owner key 首次使用时可以注册身份；陌生 key 不会因查询或请求而注册。其他身份必须由受控流程显式提供，不存在公开自助注册接口。
- `identity_id` 是稳定的资源 owner。轮换 API key 后，新 key 继续访问同一身份的数据，旧 key 失效。一个 key hash 只能属于一个身份。
- agent、team、run、浮动会话、provider、model gateway、workflow、audit 和移动文件按请求身份隔离。浮动会话的关联 run 被清理后，仍检查会话自身的 owner。
- 后台执行与定时工作流使用持久化 run/flow 的 owner 记录审计，不依赖已经结束的 HTTP 请求上下文。
- 无 owner 的旧记录仅按各模块的兼容规则归属配置 owner。删除 Provider 配置会同时移除该 owner 可见的旧兼容副本，保留其他 owner 的配置。
- 审计读取 fail-closed：请求身份不可用或为空时返回空结果，不会退化为读取全部审计记录，空 owner 也不能选中未认领的旧记录。
- Provider catalog 同一 ID 的跨 owner 首次创建仍沿用现有访问规则，可能返回 404；本次修复没有扩展为新的多租户注册接口。

身份注册、轮换、撤销和 LAN 凭证写入使用独立事务，并检查数据库文件身份。业务调用方的事务不会被凭证写入提交；数据库缺失、替换或无法访问时不得返回写入成功。

## 身份 API 的错误约定

请求仍通过 `X-API-Key` 认证，不要在 URL、日志或命令历史中保存真实凭据。

| 操作 | 输入或状态 | 响应 |
| --- | --- | --- |
| `POST /memory/identity/rotate` | `new_key` 不是字符串或不满足现有强度规则 | 422 |
| 同上 | 新 key 已被占用或与当前 key 相同 | 409，不透露其他身份信息 |
| 同上 | 当前 key 在事务执行前已失效 | 401 |
| `POST /memory/identity/revoke` | `api_key` 不是非空字符串，或请求撤销自身正在使用的 key | 422 |
| 同上 | 目标不属于当前身份或不存在 | 相同的 404 响应 |
| 同上 | 当前身份自己的目标 key 已失效 | 409 |

轮换时，`new_key` 至少 32 个 ASCII 字符，仅允许字母、数字、`_`、`-`，且至少包含三种不同字符。应使用安全随机生成的 key；接口的格式检查不等同于随机性检查。

## 源码版 LAN 配对与失效

1. 桌面 owner 启用 LAN 并生成一次性配对 token。token 有效期为 15 分钟。
2. 手机通过 `POST /platform/system/lan/verify` 兑换独立 session credential；该路由只接受配对 token，不向手机返回桌面主 API key。
3. session credential 的有效期为 15 分钟，只能访问明确允许的移动任务、文件等接口，不能用来轮换 key 或管理 LAN。
4. 关闭或重新开启 LAN 会撤销旧 session。身份没有任何活跃 key 时，关联 session 也不能继续认证；同一身份的正常 key 轮换保留其 session 至有效期结束。
5. 手机会话清理会中止在途请求并重置界面状态。旧会话的响应、错误和结束回调不能改变新配对的数据、凭证或忙碌状态。
6. 携带新配对 token 的链接优先于本地缓存的旧会话：页面复用（仅 hash 变化的导航）或重新打开时都会先清理旧会话再兑换新 token，被撤销的旧 session 不会继续展示。

移动文件按 owner 授权；单文件上限为 50 MiB，请求正文另有 multipart 开销限额。文件数量与总容量在登记事务内检查；上传中断、写入失败或登记失败会尝试清理未登记文件，清理失败会记录告警。

Electron 冷启动会先撤销旧 LAN session、清理旧配对状态并核对本地绑定。撤销发生数据库错误时，启动核对必须失败，不能继续报告安全状态已恢复。

LAN 来源仍须通过 Host 与 Origin 校验。Origin 的端口按后端实际监听配置判断，命令行 `--port` 优先于 `WANWEI_PORT`。

## MCP 出站边界

MCP SSE 的初始 URL 与服务端返回的 endpoint 分别校验目标地址，并分别设置固定目标 IP、Host 与 TLS SNI。配置主机白名单时只加入确实受信的目标；初始连接通过校验不代表后续 endpoint 自动获准。

## 升级与回滚

升级前停止后端和桌面进程，备份实际使用的数据库、平台配置和文件存储目录；数据库路径以 `WANWEI_MEMORY_DB` 或桌面运行时配置为准。不要只复制正在写入的 SQLite 主文件而遗漏 WAL 中的数据。

启动初始化会为审计增加 owner 列，创建 LAN session 表，并将 identity key hash 改为全局唯一。旧库如包含重复 key hash，迁移按活跃记录优先、创建时间优先保留一个归属；升级前应核对备份中的异常重复身份及关联数据。移动文件表会按需补充 owner 列。正常升级不需要重新分配已有资源 owner。

回滚应在停止全部进程后恢复升级前备份，并运行与该备份匹配的源码。不要在运行中替换数据库文件；身份指纹保护会拒绝继续写入。只回退本轮评审修复提交不会改变数据结构，但会恢复对应缺陷，不建议作为常规处理方式。

## 验证入口

在仓库根目录使用已安装项目依赖的 Python 执行：

```bash
python -m pytest backend/app -q -rs
python -m pytest backend/app/tests/test_pr215_identity_boundaries.py backend/app/tests/test_pr215_owner_isolation.py backend/app/tests/test_pr215_remote_sessions.py backend/app/tests/test_pr215_release_staging.py -q
node --test desktop/tests/test_fix_w13_desktop.cjs desktop/tests/test_linux_packaging.cjs
npm --prefix frontend/console-vue run test:security
npm --prefix frontend/console-vue run test:contracts
npm --prefix frontend/console-vue run build
python scripts/release_preflight.py --tag v1.0.0
```

前端命令需要先在 `frontend/console-vue` 执行 `npm ci`。Node 合同测试和 staging 补丁验证不等同于真实桌面启动或安装包验收；Linux 构建命令及其依赖见桌面文档。
