# 324 审批与正文恢复操作包（原包修订）

**请直接打开下面的“登录并返回该审批对象”，不要先用无 returnTo 的通用登录页。** 独立账号 reviewer324，密码在本机 `/Users/tristan/Documents/s5-v023-impl-324-acceptance/local-accounts-v1/reviewer324.password`。业务账号 demo324 的密码在同目录 demo324.password。代理未登录实际审批账号。

审批须在独立浏览器配置/隐私窗口进行。同浏览器新标签共用 Cookie，不构成身份隔离。若原业务页仍开着，请保留，不刷新、不切换身份。本包不要求重建对话或重复申请。

## 原操作包的六条链接：全部保留

| 对象 | 登录入口 | 已登录后的只读核对入口 |
|---|---|---|
| 原资源准备 | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Frequest%3Dgrant-request-048bc8a3051e77383a1ef9fd11010844) | [核对原对象](https://127.0.0.1:19436/authorization-admin?request=grant-request-048bc8a3051e77383a1ef9fd11010844) |
| 原 Employee 准备 | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Frequest%3Dgrant-request-b2447ead173fe891b7df923fed4551e5) | [核对原对象](https://127.0.0.1:19436/authorization-admin?request=grant-request-b2447ead173fe891b7df923fed4551e5) |
| 原执行准备（不是执行准入） | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Frequest%3Dgrant-request-366a7309c01ced50e54ac4b967b1c9f4) | [核对原对象](https://127.0.0.1:19436/authorization-admin?request=grant-request-366a7309c01ced50e54ac4b967b1c9f4) |
| 01:12 合成预检草稿申请 | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Frequest%3Dgrant-request-907a9386901269b8a69bd62d13ee157c) | [核对原对象](https://127.0.0.1:19436/authorization-admin?request=grant-request-907a9386901269b8a69bd62d13ee157c) |
| 01:12 合成预检模型申请 | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Frequest%3Dgrant-request-59c08d23163426bdd1efcd2934ffb56f) | [核对原对象](https://127.0.0.1:19436/authorization-admin?request=grant-request-59c08d23163426bdd1efcd2934ffb56f) |
| 01:12 合成预检 context | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Fcontext%3Ddraft-context%253A0477d775cd85ee477a22fe465dc42419) | [核对原对象](https://127.0.0.1:19436/authorization-admin?context=draft-context%3A0477d775cd85ee477a22fe465dc42419) |

## 新发现的用户实际请求：不能与预检案例混用

数据库在 07:36（上海）记录了第二条 context/invocation，草稿/模型申请各一条。原包中的 01:12 对象属于代理合成预检，不是这条用户新问题。全部原记录保留，没有替换摘要或重新申请。

| 对象 | 登录入口 | 已登录后的只读核对入口 |
|---|---|---|
| 07:36 用户新问题草稿申请 | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Frequest%3Dgrant-request-8fa548ec39f8e7c88daa2b36e27ec9a3) | [核对原对象](https://127.0.0.1:19436/authorization-admin?request=grant-request-8fa548ec39f8e7c88daa2b36e27ec9a3) |
| 07:36 用户新问题模型申请 | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Frequest%3Dgrant-request-6d60339044f901ee99ceb661730b4c76) | [核对原对象](https://127.0.0.1:19436/authorization-admin?request=grant-request-6d60339044f901ee99ceb661730b4c76) |
| 07:36 用户新问题 context | [登录并返回该审批对象](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fauthorization-admin%3Fcontext%3Ddraft-context%253A668f2fc674e0a88ddebb2020594c4652) | [核对原对象](https://127.0.0.1:19436/authorization-admin?context=draft-context%3A668f2fc674e0a88ddebb2020594c4652) |

业务原对象：[demo324 登录并返回原调用](https://127.0.0.1:19436/api/workbench/v1/login?returnTo=%2Fwork%3Finvocation%3Ddraft-invocation%253Ae2dd245b7ddc93a5299b245bc470649b)。登录只定位；“读取原调用事实（只读）”依然要求有效 READ Grant，缺权限时不会绕过。

## 正文与下一步

服务器对两条调用都只保存 CONTENT_NOT_RETAINED 元数据/HMAC。无法从自然语言重建带随机消息 ID 的原始 JSON，更不能修改旧摘要。当前原浏览器标签未能取回，正在确认用户是否仍保留原页；因此尚未判断所有副本确已丢失。

若原页正文还在：先核对实际 invocation 与原申请，独立签发对应两 Grant/context；随后代理通过单独的“使用已保留正文继续 AI 调用”进行原对象重交，服务端校验原 HMAC。新标签不改变旧页内存。

若原页已关闭：不签发无正文可续接的模型调用来假装恢复。先复用原草稿 READ 申请，通过正常读取恢复原 context/turn/invocation；代理按已授权的明确合成变体准备并提交关联后继，保留原对象/摘要/申请；不会把新内容冒充原文。后继形成后，新的精确调用 Grant 必须由独立本人签发，不预造编号，不复用旧模型许可。

“查看授权状态（只读）”只发 GET，不重交正文；刷新/登录返回不会自动派发。正文不可用时没有原正文继续按钮，填写关联后继本身不创建对象，明确发送才走原 begin/parent 机制。

本人决定后优先新问题真实 AI 回复与补问验证，再继续原三项资源/Employee/执行准备、本人审核发布、窄后继确认和独立 Native 准入。批准准备资格不等于资源已发布，不等于 Run 已获准执行。原成本案例与 323 历史保持；324 未完成。

## 当前真实浏览器限制（候选 64d5eb4 后）

旧本地 HTTPS 证书在 2026-09-22 09:32:44（上海）到期。已在本机独立路径续期至 2026-10-22，服务器握手已核对，旧证书/密钥历史保留、系统信任未改。内置浏览器仍报 ERR_CERT_DATE_INVALID，尚不能宣称真实登录预检通过。本人需处理浏览器证书信任提示；代理不能绕过。此项不改变业务权限，处理后仍须在独立审批会话使用上述精确 returnTo 链接。
