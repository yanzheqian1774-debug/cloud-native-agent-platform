# 审批入口与正文恢复验证

截图诊断 ID：workbench-request-eedff341de02d04b33daa95b。截图为审批主体 / 恢复工作区 / 404 / AUTHORIZATION_NOT_FOUND。保留日志无精确匹配；后续实际日志及源路径证明业务集合 LIST 权限拒绝，不能据此断言精确授权对象不存在。

新增隔离 PostgreSQL 登录测试 1 passed：五 Grant/context 的 returnTo 保留，业务与审批两个 Cookie 容器分离，无审批人业务集合权限。浏览器辅助入口 14 passed：只读授权零 POST、原正文原 key、刷新零重发、缺正文禁用、明确关联后继、六条审批路由、独立 fixture 审批只读。手动入口/执行展示 17 passed；前端静态契约 12 passed。前端 lint 和 live+assisted build 通过。浏览器 fixture 不代表真实 reviewer 登录或签发。

视觉截图已检查：长中文、独立滚动区、125% 等效视口、输入区始终可见。visual-review.html 记录参考/实现及未消除差异；不宣称整体视觉通过。无新基础设施、迁移、Grant 扩权、委托续期或实际模型派发。

07:36 用户 context 与 01:12 代理合成预检分开。两者正文均不在服务器保存；原标签是否还在等待用户事实确认。未创建后继或重复申请，未代签。完整 Native/评价/Human 闭环仍未完成。

首轮 make check：2121 passed / 364 skipped / 1 error。新测试独立文件复用了 PG fixture 却未继承原模块环境条件；归回 test_local_accounts_postgres.py，沿用既有专用 PG CI，不改断言、不删除验证。最终正常门禁另记。

最终 make check：2121 passed / 365 skipped / 1 warning，177.85 秒。新增 PG 用例在原专用数据库套件中定向实际执行 1 passed（5.61 秒）；默认环境跳过与原模块一致。原 deadline 失败证据保持，未更改阈值。正常提交与候选 CI 另记。
