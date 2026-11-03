# 324 集中人工步骤：新问题准入与原案例准备

实际入口已用 demo324 验证。新问题返回 201 / AUTHORIZATION_PENDING，未派发模型；原三条申请仍为 PENDING，直接复用。此包不申请新的模型、价格、预算上限或架构决定。

## 登录与账号

[登录](https://127.0.0.1:19436/api/workbench/v1/login)。业务账号 `demo324` → `human:demo323-requester`；独立审批账号 `reviewer324` → `human:demo323-approver`，均为 `s5-323-demo / isolated-real-demo`。

本机密码领取：`/Users/tristan/Documents/s5-v023-impl-324-acceptance/local-accounts-v1/demo324.password` 和同目录 `reviewer324.password`。密码未提交仓库，服务重启不重新生成；代理没有使用 reviewer324。

请保留已打开的新问题业务页，独立审批使用另一个浏览器会话，避免同浏览器切换身份清除未落库正文。当前正文仍只保存在业务页内存；刷新不重发，但不能恢复其正文。不要重新输入创建重复申请，遇到页面丢失由代理核对原对象并走正式恢复。

## 当前需要独立本人处理的正式记录

使用 reviewer324，每条“检查授权申请”后核对并决定；每条分别保存正式记录。批准不会自动执行业务。

| 记录 | 页面 | 影响 |
|---|---|---|
| 原资源申请 | [048bc8a…](https://127.0.0.1:19436/authorization-admin?request=grant-request-048bc8a3051e77383a1ef9fd11010844) | 四项精确资源的读取与审核发布资格；不是已经发布 |
| 原 Employee 申请 | [b2447ead…](https://127.0.0.1:19436/authorization-admin?request=grant-request-b2447ead173fe891b7df923fed4551e5) | 原 Employee 技术校验、审核和发布准备；不是 Human 业务审核结果 |
| 原执行准备申请 | [366a7309…](https://127.0.0.1:19436/authorization-admin?request=grant-request-366a7309c01ced50e54ac4b967b1c9f4) | 已存在 Plan/Problem/Criteria 的准备操作；不是未来 Run 执行准入 |
| 新问题草稿辅助 | [907a9386…](https://127.0.0.1:19436/authorization-admin?request=grant-request-907a9386901269b8a69bd62d13ee157c) | 实际新 invocation 的草稿请求、读取与取消 |
| 新问题精确模型调用 | [59c08d23…](https://127.0.0.1:19436/authorization-admin?request=grant-request-59c08d23163426bdd1efcd2934ffb56f) | 仅本次实际 invocation 的精确模型目标 |
| D324-5 context 准入 | [核对并独立签发](https://127.0.0.1:19436/authorization-admin?context=draft-context%3A0477d775cd85ee477a22fe465dc42419) | 点击“核对调用对象”，核对后“本人独立签发此 context”；默认一小时；仍需前两条新问题 Grant |

新 context：`draft-context:0477d775cd85ee477a22fe465dc42419`。
新 invocation：`draft-invocation:5d66b44e407f6c34c3c0346f5baad139`。
请求摘要：`4bb3668fe3df4391d4de8b2454531513f8f050faccf6c65419b82179efc75bf5`。

准入仅合成供应商问题的理解、补问与草稿。原理解模型配置摘要为 `80e9c70f3cca1120128e7140e5ad2b76b66b1df605ad3faa3ff107cd6944787d`。原账本上限 12 次 / USD 10，读回已计 5 次 / USD 0.131092，派发时重新核验，不代表预先承诺剩余额度。原规划七 UNKNOWN 的 USD 4.816896 保留；本批不重跑规划。

## 完成后代理连续办理

读回上述决定；完成技术装配/校验，将四资源与 Employee 本人审核页面集中交付。发布后形成精确窄后继并走正常确认，再生成实际独立执行准入。尚不存在的 Run 不预造、不提前签发。

原案例实际入口：[成本案例](https://127.0.0.1:19436/work?problem=59a1d736-96d5-5060-8ae3-293d82b4b74b)。原 Plan v2、Approval 和历史保持。

实际 Native、产物、标准评价、Human 结果决定及执行后的持久读回尚未完成。合成流程验证、标准通过、真实业务问题解决分别判定。324 保持未完成；PR #186 保持 Draft，不 Ready、不合并、不关闭 Session。

## 后续核查更新

已发现用户 07:36 的第二条新问题。原六条链接保留，但不能把预检对象当作用户对象。请使用 [审批与正文恢复操作包 v2](entry-recovery/human-operations-v2.md) 的精确登录返回链接；不要先打开通用登录入口。正文是否仍保留须先核实，不能盲目签发或重交。
