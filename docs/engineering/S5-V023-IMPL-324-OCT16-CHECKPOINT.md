# 324 检查点 A/B（2026-10-16，候选验证，不提交）

## 入口与边界

工作树 `/Users/tristan/.codex/worktrees/3096/cloud-native-agent-platform`，分支 `codex/s5-v023-impl-324-native-readonly`，HEAD `092b4a5e274f91d52b54f3d35a6c227fff8f037a`。本地 Registry 为 ACTIVE / AUTHORIZED；GitHub REST 读回 PR186 OPEN/DRAFT，同一分支和 HEAD。未改 Registry、261/323、PR 状态或业务运行环境。

原三个暂存文件完整保留；原暂存补丁 SHA256 `1204a15f5128238c859041a87f8884b817483895f368138375a5f746186abf73`。本轮新增修改只留工作区，未提交、推送或重新暂存。原 /tmp 门禁日志已缺失；以下历史失败说明来自原检查点及会话证据，不冒称现存日志原件。

## A：三项历史失败

| 失败 | 证据与分类 | 与锁补丁关系 | 本轮处理 |
|---|---|---|---|
| stalled phase body | 历史实际为 IPC 阶段约1秒 CONNECT_DEADLINE，而预期已进入 READ_BODY 后 TOTAL_DEADLINE。启动未到达注入阶段，属于测试阶段前置条件与环境启动耗时交互；具体历史调度原因无法确定 | 该测试不访问任务授权或预算 PostgreSQL | 原断言/期限原样保留；首次隔离复现通过 |
| invalid-json | 历史为 STARTUP 的 TOTAL_DEADLINE，无预期输出验证；不能据此认定 JSON 处理坏了 | 测试走本地 HTTPS/显式 fixture，不走 D7 任务锁 | 首次隔离复现通过；不放宽1秒期限 |
| oversized | 同样未进入输出检查就耗尽启动期限；不是超大响应被误接受的证据 | 同上 | 首次隔离复现通过；不删除容量保护 |

三项首次复现合计3 passed /5.62秒。有环境变化后通过，不证明历史时序问题永久消失；完整候选门禁结果另记。

共享锁修复保留：current读校验使用共享任务根锁，签发/撤销仍排他。进一步收敛正式规划派发：授权守卫把所持事务连接交给预算守卫，预算守卫在借用连接时不提交/关闭它。原因是排他写者已排队时，跨连接的第二次共享读锁仍可能被排队写者挡住；仅改共享锁不充分。预算校验、账号/配置校验、历史预留、幂等与 UNKNOWN 拒绝均保留。无 schema/public Contract 改动。

新增 PostgreSQL 验证覆盖：写者排队后的同事务再入、正常/异常退出释放、撤销后拒绝、保留21条预留与零新增结算。现有历史并发预算/漂移/金额上限测试同时保留。当前历史PG端口连接被拒绝，Docker daemon不可用，未启动原环境；新增PG用例尚未通过。本轮无法将A标为全部通过。

## B：20/21分开恢复，仅方案

| 对象 | 第20次 | 第21次 |
|---|---|---|
| invocation | f078a876-eef8-4cb5-ae69-83bf6cfccd42 | e630dcd1-f03b-4228-b01e-0d3393d576fb |
| context | 88be41bf-ea20-47c4-89c7-b11b349f99c6 | 6fa28c51-ee84-47ff-8266-0d8c12fce552 |
| 已有证据 | 9月22日08:18:33 UTC，provider receipt记录 WAIT_HEADERS、30.734561秒、TIMEOUT、worker已回收、measurement空；持久终态OUTCOME_UNKNOWN | 本地锁等待/阻塞PID与SQL快照；1条invocation，无持久终态行、无provider receipt；正式GET投影UNKNOWN/NO_DURABLE_TERMINAL_RESULT_DO_NOT_REDISPATCH |
| 供应商事实 | 已进入发送/等待响应阶段；是否处理/计费仍UNKNOWN。平台receipt不是供应商成功凭证 | 锁栈指向provider.suggest前；这不能代替正式的零派发/零费用裁决，也不能据缺少receipt改写历史 |
| 预留 | USD0.688128，无settlement | USD0.688128，无释放；账本快照累计21条，结算及预留USD6.644500 |
| 幂等键 | s5-324-delivery-planning:f028d39a-657e-4a7e-a514-4faedc3b88a5 | s5-324-d7-delivery-planning-v1 |

第20次原件：`docs/evidence/s5/v0.2/s5-v023-impl-324/sep22/delivery-criteria/planning-real-outcome.json`。第21次原件在本机acceptance/context-admission-v1/d7-runtime：`call-blocking-evidence.json`、`blocked-call-pg-readback.json`、`blocked-call-formal-recovery.json`。本轮只读文件，数据库不可达，所以这些不是10月16日数据库实时状态。

现有GET `/planning-v2/requests/{request_key}`及`/planning-v2/invocations/{id}`是查询恢复；没有终态时投影UNKNOWN，不生成成功/失败事实。现有POST continue不是UNKNOWN重发许可：claim命中原幂等记录后返回原记录；不能更换正文、键或直接finish/settle绕过守卫。

建议顺序：先完成A的独立PG验证；之后如获准恢复业务只读环境，重新核对两条原记录、预留、账号、签发及配置。第20次只在供应商支持且另获许可时查询可归属结果/用量；无记录不是未执行。第21次准备追加式工程事件证据及正式owner裁决方案，保留原记录与预留，不将本地证据直接折算零费用。

若仍需新模型尝试：原policy8、D6累计20、D7累计21均不可改写；目前没有剩余次数。需单独批准精确后继恢复机制与最多一次次数增量（候选累计22，不是本轮授权），继续累计全部历史和UNKNOWN、原USD10不变；金额可用量必须当时原子计算，旧快照余量不能作为实时授权。还需新实际对象的任务/配置与模型独立签发，不能复活9月已过期签发。先给出完整差异再请求，不在本轮实施或发起。

## 下一步最小依赖

只需要可用的独立临时PostgreSQL测试端点（允许测试fixture创建/删除其随机命名测试库），不需要模型额度或业务签发。不要为测试启动/切换原业务服务。测试环境恢复前，A保持未完成；B是审阅方案，不是批准或执行记录。

## 本轮门禁结果与候选绑定

`make check`串行执行通过：2170 passed、389 skipped、1 warning，150.57秒。skip是既有环境条件跳过，未添加用于绕过本轮风险的skip；新增PG测试同样未执行，不能据全量绿灯宣称并发/回滚验收已通过。原三项失败在全量门禁亦未复现。本轮不涉及前端改动，未重复前端/截图验收。

初次PG验证为2 passed /10 setup errors，原因是历史端点连接拒绝，未执行数据库断言；没有重新启动环境或重复尝试。测试fixture按源码会使用随机命名独立库，不写业务库。日志已脱敏。

证据目录 `/Users/tristan/Documents/s5-v023-impl-324-acceptance/checkpoint-20261016/`：`three-failures-baseline.log`、`pg-locks.log`、`make-check.log`、`original-staged.patch`、`candidate-manifest.json`。manifest将HEAD、原index补丁及当前文件摘要绑定；本轮候选不是新commit或CI候选。A结论：常规门禁通过，PG关键验证受环境阻塞，未完成。B结论：方案已形成，未执行恢复。
