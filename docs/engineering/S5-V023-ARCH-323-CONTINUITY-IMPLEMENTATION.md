# 323 已批准身份连续性与视觉修正实施回执

Session OPEN / PR #184 Draft。G2 v1已获Human批准；实现和运行独立签发仍为不同证据。本轮未扩大身份权威、资源发布、D3或执行对象。

## 实现与验证

0032追加可信代次事件、连续性链和撤销事实。Foundation受信operator事务保存旧/新配置关联，去除credential secret/hash；原委托/Grant/调用/账本不改写。原独立issuer以当前session/CSRF及精确static GRANT_ADMIN签发；旧新凭据逐一同主体/scope、fresh secret、撤销优先。原case/config/read55/ledger摘要绑定，技术期最多8小时且受双方凭据期限约束。治理锁→active_generation→委托/control→连续性，链头CAS及规范payload幂等。新Grant需正式exact请求，不自动继承旧Grant；撤销权限不得重授。无连续性的旧路径保持代次严格匹配。

受控PG：53项连续性/委托/开发授权回归通过；后续14项连续性（含新exact Grant/期限/撤销）及1项旧Grant撤销保护分别通过。正常make check 2,099通过/327专用环境未配置跳过；本次新增PG测试已加入既有CI专用PostgreSQL job。前端lint/build及6项页面回归通过。实际旧b923二进制读取升级后的独立测试库拒绝`AUTHORITY_SCHEMA_INCOMPATIBLE`。

集中脚本`scripts/acceptance/s5_323_identity_continuity.py`先在独立64332数据库/19438 HTTPS服务演练：原合成数据库只读导出→受控副本迁移→可信代次激活→新服务健康/认证检查→受控独立签发→持久读回；全程零provider dispatch。第一次签发后读回发现datetime规范化差异，修复后按已有签发恢复，未重复签发。原失败日志与原签名保留。再次重入复用代次/签名，原20集合摘要不变。该证据不是原实例激活。

最终复核补齐owner事务入口的治理锁顺序，避免先持control读取锁再进入active()与独立撤销反向等待；专用并发测试观察撤销在治理锁等待后，owner事务继续绑定并提交，再完成撤销。激活入口另核对host control与数据库epoch、旧/新代次及databaseFingerprint，拒绝无关恢复状态。受控新subject已沿正式exact申请/委托签发读回原成本Problem、Criteria、Plan与历史，旧Grant保持。

## 视觉差异

R24 P06/IAM01/IAM03实际打开查看，index/CATALOG/页/契约摘要追加design-baseline.json。P06持久业务卡进入持续对话；请求携带历史上下文标为“已保存的规划输入”，不伪造为新消息；历史缺失明确提示。实际PG副本显示的长历史技术补充默认折叠，原文/时间可展开，避免占满方案首屏；不覆盖原消息，不发起模型翻译。对话补充仅影响新建议，正式标准修改独立链接，方案确认独立按钮。历史译文来源/原文入口/摘要保留。

IAM01恢复产品介绍、图文层次、插画和间距；正式名称与真实凭据入口保留，明确SSO/组织选择未接入。参考插画用原始IAM01图的SVG视口呈现，无示例登录操作。IAM03继续隐藏过期业务内容、同源安全返回、零自动重发。

便携包`/Users/tristan/Documents/s5-v023-arch-323-acceptance/productization/R24-323-visual-review-v3/visual-comparison.html`包含参考/前/后同视口及长中文/缩放截图；打开/切换/刷新无模型调用。视觉接受与实际投影测试仍未完成，不以截图或受控测试替代。

## 运行交接与停止边界

原实例仍运行59224af，原两Plan/Approval、七UNKNOWN、预留USD4.816896及16结算不变。新中文理解策略未加载，不增加理解资源发布权限。待最终候选正常hooks/CI和入口只读预检通过后交付一次Human独立激活包；调用方不使用issuer凭据代签。

脚本逐阶段保存备份、凭据创建、旧writer回收、迁移、代次、服务就绪、签名与读回回执。HTTP先校验status/content-type再解析，启动45秒、单次健康请求最多2秒；失败保留定位信息。恢复先读DB/进程/签发，禁止盲目重发。原私密generation/credential/runtime配置文件保留，新runtime使用独立文件；旧writer不再访问升级schema。回退为兼容候选只读维护，不恢复备份覆盖新审计。

真实中文Kimi后继生成、页面确认和PG同Plan/Approval读回必须在正式激活后继续；当前不宣称完成。首轮成功不人为制造失败，受控修正与真实修正分别记载。后续六事项已补充原计划§26的A/B/C包，保留D2/D3及增量二归属。
