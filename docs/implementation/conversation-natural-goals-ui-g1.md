# 同一会话自然问题与精确工作切换 G1

基线为 source47 (tree 0adb9190) 叠加已冻结后端39文件 (tree 4137364f)。本包只改前端；不修改后端冻结输入、0077迁移或任何实际环境。

固定目标 BOUND 的普通输入由服务端 capability 显式开放，仍从现底部输入进入原单次 C1。无周期焦点时使用服务端 neutral 上下文，不将旧 PLAN 当作当前问答目标。DIRECT_ANSWER 和明确 ANSWER 澄清仅保留回复；仅同次响应 INDEPENDENT + intent TASK + 三种任务结果可采用原结果。缺意图不猜测，不再调用 root 理解。

采用前重新读取当前 chat head，将原 messageId/requestKey/expectedConversationVersion/稳定 commandId 持久写入并读回，再调用正式 adoption。失联只 GET 原命令；NOT_RECORDED 不自动重发，不换 key。采用完成只提供明确查看入口，不抢用户正在阅读的旧工作。

右栏目录仅展示服务器返回的已创建业务工作，未创建/澄清中的私有目标经服务器消息 goalId 或采用回执入口读取。选择按 exact goalId/digest，重名用原 createdAt 区分，不按标题猜。目标 journal 必须具有相同 goalId/digest/rootMessageId 与 INDEPENDENT_GOAL，不能携旧 fixedWorkSource。读取失败不能回退默认 journal。旧 BOUND、每周期、每工作输入和滚动上下文分别保存。

普通会话既有路径保留；本包不实现必要 ANSWER 委托，也不修改固定安排。模型产生 AMBIGUOUS 时只保留真实澄清，不擅自选择同名工作。READ 与工作选择不构成执行题回答权限。

验证使用受控浏览器协议响应，不是实际模型或自然周期验收。后端39的真实owner证据独立引用，不用前端fixture代替。具体终态与未通过日志见交付 HANDOFF。
