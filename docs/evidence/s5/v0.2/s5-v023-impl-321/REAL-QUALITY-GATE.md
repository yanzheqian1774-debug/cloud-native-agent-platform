# Separate real-model quality gate — NOT AUTHORIZED / NOT MEASURED

The G1 implementation authorization permits deterministic engineering validation,
not real provider dispatch. No applicable independent call authorization has been
received. No real credential was read; 319 windows, budgets and credentials cannot
be inherited.

Frozen cases: `console/backend/tests/fixtures/s5_321_quality_cases.json`.
Use the 16 human-review oracles in the G1 plan. Maximum proposed comparison: old v1
and new v2, 16 cases each, at most two dispatches per case (64 total), no retry or
provider fallback. Input at most 16384 UTF-8 bytes per invocation, output at most
1024 tokens. These are proposed caps, not authority to call or a monetary budget.

Before execution, Human must fix candidate source/tree, exact model/provider/
endpoint/profile revisions and digests, adapter revision and policy digest,
dataset digest, credential reference, current authorization window, numerical
currency/cost cap and pricing authority, timeout/cancellation bounds, provider
retention/training/region policy, and raw-output review/retention permissions.
All these provider-specific values are PENDING; they must not be guessed.

Review both versions against fixed case oracles without repairing outputs before
scoring. Record raw counts for repeated questions, unsupported atomic facts,
missing required facts, semantic edits, user sends and confirmations. Unknown,
timeout, refusal and budget failures remain in the denominator. Model factual
claims cannot gain platform authorization. A supported sourceRef proves only an
input reference exists; semantic entailment requires review.

Stop on unauthorized dispatch, content persistence, authorization leakage, cap or
window exhaustion. Quality hard failures remain failures. Engineering tests,
manual corrections and formal Problem creation never upgrade model-quality status.

## 2026-09-17 固定候选审阅：原参数表增补（未授权真实dispatch）

本段覆盖上文笼统的全部PENDING；上文作为历史保留。Human已要求准备真实对比，
但尚未批准本次新窗口及预算。费用承担、凭据owner、操作/审批/质量评审均沿用Human本人，
仅合成数据及既有已披露的数据条件继续有效，不重复索取姓名或重批相同条件。
此处是321现有质量门禁内的参数表，不修改319的参数或运行环境。

### 固定对比与公平性

- 候选source `4001b412340398ea42d813efd7f7f5f2cf9bf01d`，tree
  `846e7b5536ebd68d2e12d31d907d0e32a6195a70`，原PR181/Draft；复用12/12成功。
- 原版source `e51334aa9780291b3d077a1edb698dca630a6b3f`，tree
  `535fdd12cd11e4f2a029f03170f2a100e0fd8b49`。原Kimi v1 instructions与候选保留的v1逐字一致。
- v1 policy digest `feba097dab6895e982949377a33b9846e6456ca766251dbc58e64876b8f00728`；
  v2 `3a0a6f45193595d221119f1394a36daf8f0bf83b979a5241860217653ab54723`。
  v1/v2输出schema分别为 `problem-draft-assistance-output.v1/v2`。
- 数据集仍是原G1的16例，不改输入/oracle：SHA256
  `e789ee7e010b8e08c38afb475c73e36f8a5d50b7dcbd3d90dace88f63d88c58d`。
  逐例空结果位于 `quality-comparison-preflight.json`，32个版本结果均NOT_MEASURED。
- 原产品v1首轮送原文，只有NEEDS_CLARIFICATION且尚无草稿才按
  `原content + \n\n用户补充： + 新输入`继续；DRAFT_READY后的纠正只作为本页补充。
  不给旧版暗装v2上下文，也不强制制造原产品不会发出的后续请求。记录
  PATH_UNSUPPORTED/未采用纠正及零后续dispatch，而非模型拒绝或质量PASS。
- 新版按真实 `problem-understanding-context.v1` 包含消息、字段修改、currentDraft、
  previousUnderstanding、previousQuestion及uiRevision。Q13在第一份草稿存在时应用原fieldEdit；
  不存在则记前置不满足，不人工伪造模型草稿。两版都是相同冻结用户轮次，无额外临场补料。
- 单轮用例4个、双轮12个，每版最多28次，共最多56次；不沿用旧10次或拟议100次，
  也不把历史建议64次变成授权。按Q01→Q16、奇数例v1先/偶数例v2先交错，串行执行。
  不追加样例、重试或fallback，不因某版早早出稿而丢弃其后续纠正失败。
- 同endpoint、native model、reasoning、输出/超时/预算限额；没有模型评委调用。
  此设计测整个原版/新版产品链（Prompt+context+UI）效果，不能单独归因于Prompt。
  托管 `kimi-k3` 是服务别名，底层不可变权重版本未知；记录可获得的版本标识，
  不能把同别名当作绝对同权重。每例一次对比不是统计显著性证明。

### 参数、凭据与精确绑定

| 项 | 本次具体提案/已核实状态 |
|---|---|
| Provider / model / endpoint | Moonshot中国区 / kimi-k3 / `https://api.moonshot.cn/v1/responses`，KIMI_RESPONSES_V1；两版相同 |
| 推理与采样 | reasoning.effort=low；不显式设置temperature/top_p；无工具、网络搜索、后台执行 |
| 长度 | 应用输入≤16384 UTF-8 bytes；含instructions/schema完整请求字节作为保守token上界≤32768；输出≤1024 tokens（包括provider计入上限的推理）；响应≤65536 bytes |
| 超时 | connect/read/total=5/30/60秒；沿用现有A05监督与worker回收，不新增重试 |
| 数据 | store=false、background=false；仅原16例合成数据。沿用不强制ZDR及留存/缓存TTL/删除SLA未知的已接受条件，不能宣称零留存 |
| 凭据定位 | `kind-agentos-dev / agent-workloads / model-credentials / api-key`；当前只输出UID `23a20259-1aea-41a8-8a45-f11189a96c7d`、resourceVersion `122913`，匹配既有引用；未输出或物化Key |
| 可用性边界 | Secret存在已核实；不是当前账号余额、K3资格、Responses权限或Key有效性的证明。无独立付费探针；获批后的第一条计入56次及费用，失败保留并停止核对 |
| 受控接线 | 321独立评测目录0700；获批后由指定Secret受控物化owner-only 0400普通文件，exact-file-resolver/v1，校验UID/RV、owner/mode、非symlink；不复用319的文件、ledger、DB或服务 |
| 治理绑定 | `quality-comparison-preflight.json`列出两版明确model/provider/endpoint/connection/profile revision IDs、schema和policy digest；状态NOT_REGISTERED。proposalManifestSha256仅为提案身份，绝不是已登记治理对象digest或批准回执 |
| 启动前绑定门禁 | 独立321评测存储中正常登记上述精确对象，取得真实domain digest与eligibility，固定两版Profile及resolver；当前Human授权下逐invocation的Draft/Model exact grant仍须current admission；不伪造已批准状态 |
| Ledger | 提议唯一`kimi-real-s5-321-quality-round-1`，两版共用56次/USD8总帽；创建前查重/核对本轮历史。不是重置旧ledger；原321 fixture ledger及319账本都不动 |

32768完整请求上界高于旧319的4096；1024输出沿用321原G1而低于旧319的4096。
二者均是本次待接受的不同参数，不继承旧真实成功请求的兼容/充分性结论。
结构化v2可能在1024截断；记FAILURE/TRUNCATED并停下，不自动增限重跑。

### 新预算与窗口建议（必须Human明确后才启动）

2026-09-17读取官方[价格Markdown](https://platform.kimi.com/docs/pricing/chat.md)：
kimi-k3未命中输入CNY20/M、输出CNY100/M；不使用缓存折扣计上界。
[中行报价](https://www.boc.cn/sourcedb/whpj/) 2026-09-17 13:43:38，USD现汇买入669.73 CNY/100USD，
采用6.6973 CNY/USD并沿用已批准的10%保守余量/向上舍入方法。
输入3284906、输出16424530 microusd/M。单次最坏预留124459 microusd；
56次合计6969704 microusd = **USD6.969704**。建议新的应用预算帽 **USD8 / 最多56次**。
它不是provider实账或账户硬封顶；有新增附加费、价格上涨到超帽或资格变化时停止。
启动前刷新报价，低于此上界可沿相同保守方法，高于需重新收口。

建议新绝对窗口：**2026-09-17 14:30:00—22:30:00 Asia/Shanghai (UTC+08:00)**，
即06:30:00—14:30:00Z。未批准，不以准备完成或沉默视为生效。
若批准时起点已过，不自动顺延，需明确新的绝对8小时窗口；旧窗口已到期且不复活。

Human一次决定项：接受上述固定对比/两版绑定提案和共同参数；批准本次56次/USD8帽；
确认绝对窗口（或给出替代8小时起止）。费用owner及既有合成数据条件无需重填。
本轮仅准备；即便取得这些决定，也须先完成尚未激活的精确治理接线验证，再dispatch。

### 逐例记录、评分和停止规则

每例/版本保留：原用户输入、精确请求版本/上下文（仅受限合成评测附件），
模型最终answer JSON原文、人工修改单列、最终确认文本单列（未确认=null）；不保存思维链，
不把人工补全文本回填成原输出。记录来源/版本、invocation/turn、结果类型、调用次数、
端到端与transport耗时、input/output usage；未知usage=null，绝非0。

按原oracle逐条判断事实忠实性、无依据原子事实数、已答/明确未知的重复补问数、
关键事实遗漏数、纠正采用、人工语义修改数/字符改动量、用户发送轮数、确认次数。
模型失败、拒绝、超时、截断、结构化错误、路径不支持、无法判断分别标注，保留16例分母；
未执行项NOT_MEASURED，无输出项无法评分。人工修改量在评审修改实际发生前也是null。
每例展示v1/v2差异和退化；Human作语义接受判断，不以sourceRef存在或结构测试计PASS。
不为评测16例创建正式Problem；真实后端创建能力复用原唯一对象证据。

首次provider错误/OUTCOME_UNKNOWN、预算或窗口耗尽、身份/绑定变化、非合成内容、正文进入
辅助持久表、越权、未知成本超出保守预留、截断或异常结束均停止后续dispatch并报告。
失败计入本轮调用/保守占用，不返还或改ledger，不自动重试/换模型/加预算。
原始评测答案仅放321受限目录0700/文件0600用于本次Human评审；不写公共CI日志、
canonical Evidence正文或Git。原失败历史与人工修订证据独立保留，不自动清理。


### 后继候选门禁

准备完成后的截图审阅发现补问被误标为草稿生成，已进入本轮授权的最小修复。
4001b412仍为原审阅对象；实际评测须绑定后继提交及其完整tree/新检查结果，不能沿用旧CI。
两版policy/schema/上下文策略未被该文案修复改变，参数/预算/窗口提案保持待Human决定。
即便批准参数，也不将其解释为接受尚未交付的新代码候选；最终身份见原PR181更新回执。
