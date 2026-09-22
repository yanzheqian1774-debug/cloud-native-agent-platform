# 审批入口与正文恢复验证

截图诊断 ID：workbench-request-eedff341de02d04b33daa95b。截图为审批主体 / 恢复工作区 / 404 / AUTHORIZATION_NOT_FOUND。保留日志无精确匹配；后续实际日志及源路径证明业务集合 LIST 权限拒绝，不能据此断言精确授权对象不存在。

新增隔离 PostgreSQL 登录测试 1 passed：五 Grant/context 的 returnTo 保留，业务与审批两个 Cookie 容器分离，无审批人业务集合权限。浏览器辅助入口 14 passed：只读授权零 POST、原正文原 key、刷新零重发、缺正文禁用、明确关联后继、六条审批路由、独立 fixture 审批只读。手动入口/执行展示 17 passed；前端静态契约 12 passed。前端 lint 和 live+assisted build 通过。浏览器 fixture 不代表真实 reviewer 登录或签发。

视觉截图已检查：长中文、独立滚动区、125% 等效视口、输入区始终可见。visual-review.html 记录参考/实现及未消除差异；不宣称整体视觉通过。无新基础设施、迁移、Grant 扩权、委托续期或实际模型派发。

07:36 用户 context 与 01:12 代理合成预检分开。两者正文均不在服务器保存；原标签是否还在等待用户事实确认。未创建后继或重复申请，未代签。完整 Native/评价/Human 闭环仍未完成。

首轮 make check：2121 passed / 364 skipped / 1 error。新测试独立文件复用了 PG fixture 却未继承原模块环境条件；归回 test_local_accounts_postgres.py，沿用既有专用 PG CI，不改断言、不删除验证。最终正常门禁另记。

最终 make check：2121 passed / 365 skipped / 1 warning，177.85 秒。新增 PG 用例在原专用数据库套件中定向实际执行 1 passed（5.61 秒）；默认环境跳过与原模块一致。原 deadline 失败证据保持，未更改阈值。正常提交与候选 CI 另记。

64d5eb4 CI：320 四场景因旧通用 details 定位同时匹配原文/技术事实而失败；319 同类定位一起改为精确“技术事实”，未改断言。完整本地 HTTPS 319 回归通过；320 三项通过，预算场景在第六次预期派发前遇 503/TRANSPORT_AMBIGUOUS（trace 2291.818ms，mock dispatchCount=5），不是已证实的模型超时。失败报告与 trace 保留于 /tmp/s5-324-entry-fixed-320，未重跑掩盖、未删除断言、未扩大额度或清理实际案例。此次 disposable test 数据库按既有 fixture 正常释放，真实 323/324 数据未使用。后续最终 CI 分开报告。

定位修正的正常提交首次被既有规划 deadline 挡住：valid 与 oversized 均 TOTAL_DEADLINE/STARTUP，1.001178s / 1.000695s，端点 calls=[]，2119 passed/365 skipped/2 failed。单独诊断原四场景 4 passed：decision 0.514/0.496/0.498/0.365s，均到 VALIDATE_RESPONSE 且 reaped=True；原阈值不变。记录显示启动时序波动，未证明根因已经修复；宿主当时多进程高 CPU 仅为相关现象，不能当作确定因果。日志 /tmp/s5-324-entry-selector-commit.log 和诊断 XML /tmp/s5-324-entry-deadline-diagnostic.xml 保留。仅在诊断后再走一次正常完整门禁，不抹掉失败结果。

诊断后的第二次正常提交仍被门禁拒绝：Kimi cumulative 场景为 CONNECT_DEADLINE（1.013282s），断言要求 TOTAL_DEADLINE，2120 passed / 365 skipped / 1 failed。未修改断言或 deadline，停止重复门禁。语义定位修正及本次记录保留为未提交差异；远端/运行候选仍 64d5eb4，CI 10 SUCCESS / 2 FAILURE（319/320 的定位失败）。不能声称最终候选全绿或合并就绪。日志 /tmp/s5-324-entry-selector-commit-v2.log 保留。

## 同案验收修订与集中预检（2026-09-22，未完成）

最终口径已改为同一问题贯通理解、目标/标准、计划、资源、Native、产物评价及Human接受；两种资源条件分别留证，A/B仅内部诊断。见原计划附属CLOSURE-MATRIX，不新建Session或Plan。

本轮新增精确READ保护的只读readiness投影，逐次检查当前Grant/context，不调用resolve/prepare/admit。前端核验成功显示等待继续，缺正文优先提示恢复限制；审批exact URL自动GET并显示申请人、当前审批人、scope及精确操作。长卡片初始定位顶部，workspace grid不再被430px最小高度撑出输入区；右栏显示当前调用与下一步。实际派发仍走原权限、准入和预算重验。

定向Python 44 passed（BFF与草稿），前端lint通过，assisted-entry构建及14项浏览器验证通过；包括只读查询零派发、正文缺失正式后继、六类精确登录返回、100%/125%可见性。截图为fixture工程证据，非实际AI/Native或视觉接受；完整门禁另记。读取R30 P02/IAM03/IAM07，摘要见integrated-preflight-design.json，未改R36基线。

12:02上海实际TLS握手证书有效期09-22 09:42:45至10-22 09:42:45，SHA256 70:4F:5D:F8:44:8A:EC:AE:A3:48:C9:10:77:76:04:E0:C3:30:93:E8:36:0B:63:3A:E2:AA:39:40:DB:3E:6A:7C；同一时刻内置浏览器仍ERR_CERT_DATE_INVALID。不能把浏览器错误解释为当前服务器证书已过期，未绕过提示或改系统信任。

最新只读PG：26张保护表的原行保持；两context仍AUTHORIZATION_PENDING、独立决定0、新模型预留0、七Grant PENDING。原理解账本5/12，规划19/8，预算上限均USD10，次数/历史未修改。新问题规划需要正式可用路径；原成本计划不能代替同案证据。尚未交付新的本人签发请求，先解决可提前发现的技术/范围阻塞。

本轮make check实际通过2122 passed/365 skipped/1 warning（171.56秒）；不把一次通过当deadline根因消除。新增主要操作滚动可达断言通过1项：按钮完整位于消息流与输入区之间。首个定向命令误在仓库根使用另一Playwright runner，未收集测试；改为frontend既有runner后通过，保留失败事实。实际浏览器、Native和标准评价仍未完成。
