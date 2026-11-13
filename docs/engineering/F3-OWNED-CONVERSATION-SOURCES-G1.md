G1 原会话资料发现与只读恢复（基线 e226db0）
现象与已核原因
初始模型 SUCCEEDED/NEEDS_DATA。GET conversation-sources 被入口 BUSINESS_PROBLEM LIST business-problem:collection 拦截，逐条知识 READ 失败本应跳过并返回空/部分列表；现证据不能区分 collection grant 从未授予或到期，不声称已核过期。
source_input.source_reader 选取资料后仍复用同 collection LIST，必须同包修。planningRequest 通用失败文案将资料读取错误说成规划/理解失败。source-discovery pending 被保留，刷新没有独立 GET 恢复分支。
实施边界
独立 work/f3-owned-source-discovery 基于 e226db0。新增私有 owned conversation 资料 GET；以原主体拥有且未归档会话、当前初始理解准入 policy/account/session/generation/ledger/期限核验目录资格，逐 exact KNOWLEDGE READ 与真实 published snapshot 验证。旧 legacy catalogue 继续原 collection LIST。不给业务问题全局 LIST，不发首次资源 READ，不升级 USE/START，不动预算/执行。复用同一 owner transaction + generation barrier，不允许 empty-grants 绕过现 authorizer.execute。
选定资料 source reader 使用同 bounded reader；未满足 owned policy 时原路径保持（development/旧获授权入口）。不以客户端选项证明权限。当前准入失效必须拒绝，不静默回退借其他主体。
前端 source-discovery 全部走带 conversation 精确身份的新读取接口；错误写资料读取失败、原问题已保存。失败/刷新显式重新读取可用资料仅 GET；保留原 draft/invocation/message/用户文本，不重发模型、不新问题、不执行业务。维持固定补充入口，补充是用户显式新发送；资料重读与补充不混成自动重理解。
所有权
本代理独占新helper、conversation_sources/source_input读取hunk、Journey source-discovery和API helper及定向tests。understanding 已确认不改 Journey/source hunk；其 owned business owner/A-F/0066/bootstrap接线需按小hunk协调，资源执行adapter由 recovery代理负责。
验收
真实隔离PG owner/BFF：本人准入成功/跨主体/跨域/归档/过期policy/停用账号/撤销session/旧generation拒绝；零exact资源READ返回空；仅exact被授权版本可见；旧入口仍需LIST；selected digest/version不匹配拒绝；无权限写入/预算预留/模型。
浏览器：原 SUCCEEDED NEEDS_DATA+pending/error刷新，GET恢复同会话；失败文案/重读按钮/补充输入；点击仅一次GET，不POST model/adopt/execute；原问题/draft/message不变；无资源明确提示；切账号/会话不串读。
完整hook由根排队，真实原会话由根唯一验证；本包不访问实际DB/平台/模型。无新表/冻结契约变更。
