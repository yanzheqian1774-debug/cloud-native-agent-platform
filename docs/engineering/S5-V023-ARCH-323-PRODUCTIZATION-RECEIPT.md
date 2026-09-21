# 323 主链路产品化实施回执

Session OPEN。本文对应原计划§27，后续Draft分支`codex/s5-323-productization`。受控结果、历史真实结果和本轮新增真实验证分别登记，不将功能通过视为视觉接受或执行验收。

## 已完成的首批集成

| PR | 精确来源 | 普通merge | 结果 |
|---|---|---|---|
|181|97b8603e8a8507eea719099e465e559b81240925|a6dfbe317c7ae968bbb13cfecb75a4fd3d8d05b2|正式门禁后Ready/merge|
|183|295e0ecbf7d853060df4800cf12fe67f6da1d058|bcf2defe8c2a6900b1bbba94ad7931c91db1b26b|正式门禁后Ready/merge|
|182|e5fa882a0b18dfbf3465cc6fb17a663f83228db7|已为main祖先|仅关闭冗余PR，来源分支保留|

main bcf2def的CI 35551586800与Employee Identity Chain 35551586836成功。保护规则未修改，未强推/管理员绕过；其他七个PR不变。合并不关闭Session，不代表全链路业务/视觉验收。

## 产品行为与限度

- 新规划页面显式使用`planning-suggestion.zh-CN.v1`；旧请求/策略/摘要保持。结构、准确引用、typed操作与依赖、标准覆盖及有限中文检测共同生效。
- 服务端默认最多3次、总180秒、单次60秒、回收2秒；每次独立键、原始调用身份、前驱和计量保留。精确错误位置反馈；重复无进展/不可安全修正/失败/UNKNOWN停止。打开、刷新、重复root不自动调用。
- 语言修正保持非目标字段、数字、日期、引用；有限启发式不能判断所有自然语言矛盾，也不能证明账单/归因真实。真正需要选择时仅渲染模型明确的2–3项，保留自由输入，选择不自动提交。
- 历史成本英文方案增加人工中文展示：原proposal `5ad74afd-a6bf-4b04-b395-34d18d01c3b6` revision1、digest `fee868ba76ca9917141332e344ba0f1ca28567d5b847aa0554c8d54bff299d62`精确绑定。提供原文、来源及译文摘要，不写Plan/Approval，不重确认、不触发模型。
- 登录沿用nonce/bootstrap身份边界，中文错误不回显凭据；返回路径只允许本地读页面，401遮蔽业务内容，重新登录不自动重发。组织只展示真实tenant/security domain，不虚构组织名称或SSO。
- 独立审批复用既有精确Grant申请/检查/决定接口。新增正式任务委托只读呈现；无正式待审批Task申请接口的集中任务签发，不伪造可用按钮。
- 资源快照保持owner授权读，明确exact版本/权限/发布核验与I/O/运行可用性的区别。未选择资源为缺失；无读权限/不可用/未知分别记录。现有owner无授权候选发现/Workflow匹配端口时明确缺口，不接入以客户端身份header信任的内部预览catalog。历史采购v2标记需要后继契约；成本v3仅typed声明可校验，`execution_eligible=false`。

## 原案例和账本保护

只读回执`real-demo/timeout-revision/productization-audit.json`与原`integration-audit-pg.json`的attempts、plans、approvals、settlements、pendingReservations、historicalHashes、executionCounts逐项一致。全表hash比较与历史排除新增成本记录的hash方法不同，不能混比；已按原审计相同过滤方法复核。

成本保持四阶段六任务、8,000元、排除试验项目、账单/归集缺口；原采购固定语义不符合结论保留。七条UNKNOWN、USD4.816896预留及16条结算原记录不变，未知费用不计零。Assignment/Run/TaskRun/Attempt仍全零。本轮尚无新增真实模型调用。

## 图集与同视口对照

实际完整包`/Users/tristan/Downloads/Resource-Management-PC-R24`；VERSION/index/CATALOG实读为R24，176当前+104历史，280图摘要均核对。README历史章节不冒充当前版本。逐文件SHA256、路径、页面ID与目录元数据见[基线清单](../evidence/s5/v0.2/s5-v023-arch-323/productization/design-baseline.json)。

|参考|实际与差异修正|验收边界|
|---|---|---|
|P01–P04|既有理解/目标组件、持续输入与右栏；中文固定字段标签|历史理解证据复用；本轮不重跑旧真实理解|
|P05/P06|实际4阶段6任务的分组表格；中文展示/原文；紧凑底部输入与独立右栏|1536×1024同视口截图；数据、人物和品牌来自实现，不用示例任务数量|
|P07|区分失败、UNKNOWN、校验失败；无自动重发|沿用组件，不伪造执行能力|
|P12–P14|明确选项、持续输入与修订历史|R23待审草案，不扩大既有视觉接受|
|IAM01/IAM03/IAM07|真实bootstrap登录、过期返回、独立精确Grant决定和任务授权读回|草案SSO/组织编辑/Task待审批模型未实现，不伪装|

受控截图来自真实React页面与受控API响应，成本内容源于保留的真实响应；不能冒充本轮真实Kimi/正式PG页面验证。截图目录位于`/Users/tristan/Documents/s5-v023-arch-323-acceptance/productization/`，最终清单随候选登记。长中文/滚动/发送按钮/右栏在标准桌面及125%等效CSS布局视口验证；CSS style.zoom测试曾暴露视口单位不缩放，保留失败记录，最终使用浏览器缩放对应的布局视口验证，不称作实际投影测试。实际投影尚未做。

## 唯一实际恢复机制阻塞：需要G2决定的精确内容

读取事实：两名原主体的凭据均过期。原0028委托绑定generation/recovery_epoch；active()拒绝跨代次。0028同task、subject、root和ledger有唯一性；0031只允许精确read期限修订。现有API没有委托代次恢复或一般profile策略修订。新会话不能令过期凭据有效，也不能复用失效Grant。

建议决定：允许仅323隔离实例追加独立签发的“原委托连续性修订”，绑定原delegation/digest、原/新generation、保持不变的recovery_epoch、原requester/独立issuer、原scope/cases/ledgers及全部UNKNOWN/预留摘要。新代次由现有部署operator正式激活；原记录不变、不重新登记case、不创建新账本。恢复不继承已撤销权限，不跳过当前精确Grant；相关请求经现有正式机制重新取得当前有效授权。新中文理解profile如改变configuration digest，必须在同一签发中精确列明旧/新profile及策略摘要，只允许已审定中文策略与原Kimi、额度计量及技术边界，不允许泛化provider/资源权限变更。

受影响owner：authority foundation（仍唯一身份权威）、task delegation/development、配置摘要读取、BFF恢复入口。兼容：旧二进制对新增恢复版本必须拒绝；旧签名/Plan/Approval/预算行不变；新effective代次仅来自独立签发。恢复前后逐表/对象/hash及无执行断言、旧代次拒绝、自批拒绝、撤销优先和同ledger串行必须验证。

替代：保持旧实例只读、交付受控候选，待正式机制补齐后真实验证。不可选：改generation-1文件延长expiry、忽略active代次校验、直接改委托行、换主体/新ledger规避、调用方登录approver代签。

依据[Architecture Gates](ARCHITECTURE_GATES.md) G2原文“authentication architecture”需架构决定；当前未实现该语义变更。该阻塞不是重新申请模型或费用授权。决定后把实现/测试/入口预检/身份恢复/必要独立签发合并为一次具体操作包，随后续接成本中文新生成与有界修正验证，不重做理解/标准/案例登记。

## 未完成事项

真实新增中文生成与修正、正式页面完整旅程需上述恢复；理解新策略尚未实际加载。资源候选发现与I/O/runtime可用性owner接口不足明确保留，不称作资源执行就绪。D2/D3/增量二定义沿原计划，不实施D3、ReAct、分工或业务执行。视觉接受与投影均不自动授予。新Draft PR及Session保持开放。


## 验证记录

首轮完整make check：2204通过、201跳过、1失败及关联teardown错误；原因是对frozen装配依赖赋值，改用dataclasses.replace，BFF装配/资源/循环21项补验通过。正常提交7f37ca7的Ruff和完整pytest hooks通过。未削弱断言、未跳过hook。随后共享ConsoleShell回归发现过期遮蔽越过主链路，已限定问题工作台/审批页并恢复外围既有导航契约；9项浏览器回归通过，新增规划PG测试21项通过。首轮失败与修复日志保留，不能将受控测试称作新真实模型质量验证。

同视口对照页：`/Users/tristan/Documents/s5-v023-arch-323-acceptance/productization/visual-comparison.html`。截图、执行日志及SHA清单在同目录。正常后继提交及最终PR/CI精确身份由该目录交付回执追加登记，不将运行旧服务59224af冒充新候选。

后续 Draft PR 为 #184。首轮远端候选811f066：Quality Gates、Frontend Quality Gates及身份链三项通过；浏览器失败分别定位为中文登录仍使用旧英文按钮定位、旧视觉测试仍使用原卡片DOM、过期身份提示旧文案。保留失败产物后同步准确中文按钮与新表格/资源区定位，不删除职责、角色、UNKNOWN、确认次数、身份消失/恢复等断言。布局1500/1366、资源UNKNOWN/版本不符、导航隔离4项补验通过。最终提交与CI身份继续记录在外部交付回执，不把首轮失败标为通过。

第二候选035223a的核心、前端、主浏览器、理解交互、身份链、资源准备/组合及Kimi mock门禁通过；310场景进入登录POST后暴露默认Location兼容性。已将无returnTo登录表单恢复到原`/workbench`，显式原对象安全返回不变，保留原Location断言。BFF22项通过；使用专用64332测试库、独立20443/20444端口完整运行原HTTPS工作台场景通过，不使用原演示库或真实provider。最终修复另经正常提交门禁。
