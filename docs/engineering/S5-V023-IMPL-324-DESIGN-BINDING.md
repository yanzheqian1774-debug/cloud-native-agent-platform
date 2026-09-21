# IMPL-324 R30逐图绑定

全部图片已通过view_image实读并与R30-MANIFEST核对SHA-256。以下为实现参考，不是Human视觉接受。路由为当前入口，Tab/区域仍需按实现映射。

| 路由 | 页面 | 实际文件 | SHA-256 | 状态与适用范围 |
| --- | --- | --- | --- | --- |
| `/work` | P08 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/P08.png` | `d3e305af349a8f92e3f993dc9ba5482a5e2dd2cf161088243743958e8f8b660f` | 参考/未验收；候选解释、能力条件、右栏缺口；不将匹配视为授权 |
| `/digital-employees` | D07 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/D07.png` | `da1517837f59cf01f2ff03fb699a2ccbd529829385492a995d8596c01c05a102` | 参考/未验收；角色/实例Tab、实例状态与运行分开 |
| `/digital-employees` | D09 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/D09.png` | `08d6061f8a4395f9dacd0467dacd1bc36bf61cd533326170cf545f892ffe89a5` | 参考/未验收；Definition、Instance、Assignment、Placement分离 |
| `/workflow-definitions` | W06 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/W06.png` | `db90e367ffc483f02a225e5a969ca6a31230c018db0f487ecf41e0ed94fc6a26` | 参考/未验收；输入输出schema和依赖映射，仅条件适用，不作为执行前置 |
| `/runtime` | R04 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/R04.png` | `369a4aae5fe3b8b6172146a06b8c9848b1af1f167d911c6a396de65cc23fb4d0` | 参考/未验收；保存分配不启动；准入缺项 |
| `/runtime` | O08 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/O08.png` | `67846469961375d4a3cc806c0f239b38980645d415bab2895d74f44c5ec65b20` | 参考/未验收；Plan/Run/Task/Attempt/Evidence空态；仅借用追踪结构，不宣称OpenClaw执行 |
| `/work` | H05 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/H05.png` | `18372bbd4048ae249b0831a875b693e1a98d3adb67491f2d38f8ca996011d62e` | 参考/未验收；执行进度、输入/输出/事件和暂停请求等待ack |
| `/work` | H06 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/H06.png` | `c690783e7cfe345c8ef1c1f9a73b660bb09347a16687d51b412280acb788e81d` | 参考/未验收；成果、标准、证据和Human决定分离；拒绝追加 |
| `/skills` | S04 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/S04.png` | `885004011133abdac2c2642e6f996ab6ccf30335e8817df37cb1bc9cc4d01fe5` | 参考/未验收；输入输出、中文schema说明、精确依赖 |
| `/skills` | S05 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/S05.png` | `c3ec5f6013b36e2aa98dbf4d6318114ac2a98075d738623178004c50441591ab` | 参考/未验收；依赖版本与用途、缺口，不归属于员工 |
| `/skills` | S06 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/S06.png` | `5e547523f921f1cefe37a2fc3754cd9585128f2fcf2d0fae6a10e815ae15475b` | 参考/未验收；只读、缺失UNKNOWN、草稿不运行 |
| `/mcp` | M07 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/M07.png` | `6200f96bff449b71b856048ebc7a98bd7a20c12cf3cd7faf8fa9e6ee9a0fea11` | 参考/未验收；工具输入输出schema、只读性质、版本/调用示例 |
| `/knowledge` | K05 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/K05.png` | `f5f0fea4b9b151c8c3f36cf1a524f73920ebf9d811f0ffed63272e073698e379` | 参考/未验收；原文预览、来源版本、元数据、不可改写原文 |
| `/knowledge` | K09 | `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/K09.png` | `2cf540bfa8026c6e9e485d18fb16b6ed77fe60d8e361cb7587657f45df5c590f` | 参考/未验收；来源定位、页码/段落/引用版本、无法定位提示 |

## 集中差异

- H05/H06旧导航与P08分组导航不一致；保留当前公共框架，仅对主链必要组件使用图内结构
- O08是OpenClaw设计，Native仅复用信息层次，不更换Runtime身份
- W06/H05/O08示例五Task不得覆盖真实四阶段六Task
- 无单一图完整覆盖对话式六Task执行闭环；相关页面不得宣称视觉已验收
- R24 P06/IAM01局部接受及IAM03非阻断结论保留

## 已实施局部：S04 / M07

2026-09-21在代码修改前再次实读上述两个原PNG。`CapabilityResourceDetails`绑定 `/skills` 的精确修订/受管operation输入输出、`/mcp` 的发现快照/tool输入及未提供输出/副作用声明缺口。采用字段表、可键盘展开的完整Schema、草稿与发布修订分离、长摘要换行及窄容器单列。未实施S04/M07全部页面布局，不冒充视觉全量接受；维持当前公共外壳。

浏览器验证使用明确标注的视图fixture，不证明PG资源就绪/权限/真实派发。首轮浏览器2项通过，包括1536×1024、125%缩放无横向页面溢出、键盘展开、零写请求。实读截图后修正窄栏字段挤压；最终复验另记实施证据。

## 续接实施绑定：H05 / H06 / P08 与 S04 / R04 / K05 / D09

本轮改动前再次实读同版 R30 原 PNG，沿用上表文件及 SHA-256，不替换为新规划图集。`/work?execution=<正式摘要>` 的 PreparedExecutionPanel 对应 H05/P08 任务依赖、身份分工、状态/资源/时间和产物，H06 对应 Criteria 与 Human 决定。`/work?resource=<精确引用>` 的 PreparedResourceReviewPanel 对应 S04/R04/K05/D09 四 owner 的精确修订、Schema、摘要、发布与缺口。保留当前外壳与持续输入区，不新建首页或重做公共框架。

实读 fixture 截图后修正窄容器布局和未准入按钮、明确技术成功与业务未定。浏览器两项通过，包括部分资源发布失败保留、刷新不发送命令、125% 缩放输入区可见。证据在同目录 324 evidence 的 `*.fixture.png`；这些是控件/布局测试，不是实际案例状态截图，也不是 Human 视觉接受。真实浏览器打开准入入口显示登录要求，受保护业务内容仍待独立授权后验证。

## D324-4 登录局部绑定

实现前实读 R30 `/Users/tristan/Downloads/Resource-Management-PC-R30/pages/IAM01.png`，SHA-256 `4f8fe71b7cd00779df1fa49c7cffa1c22a56c6631878ff5af8a161c4d9891ac7`。绑定 `/api/workbench/v1/login`，保留原 IAM01 两栏、插画、品牌与层次；仅表单改账号/密码/显示密码/中文帮助及错误，明确本地隔离测试而非 SSO。登录后现有身份区增加测试环境及退出。不采用图中企业邮箱/组织选择，不替换 R30 为 R33；实读不等于视觉验收。

## 2026-09-22 最新完整包逐页核对

实读本机 `Resource-Management-PC-R35` 的 README-R35、VERSION、index、CATALOG、CHANGELOG，并实读 IAM01、P06、P08、H05、H06、S04、R04、K05、D09 原 PNG。逐页路由/文件/摘要见 [最新映射](../evidence/s5/v0.2/s5-v023-impl-324/sep22/latest-reference-binding.json)。这九页均与 R30 字节一致；R35 是完整展示包的最新版本，不代表九张业务图本身已更新。R35 VERSION 标注七页门户待视觉审阅，index title 仍标 R34；按原业务 PNG 映射，不把门户页误作业务页新基线。

实际差异与本次处理：资源审核原先整段 JSON，现按 S04 的字段表/原文展开、R04 的期望配置与实际状态分离、K05 的来源版本及只读原文、D09 的职责边界分层；沿用 P06 对话主区与持续输入区。没有新增权限、模拟绑定或伪造执行状态。会话过期保留原对象定位但清除旧身份上下文，原对象重新读取仍受当前权限控制。

尚未宣称全页视觉验收：S04/R04/K05/D09 是独立详情设计，当前为对话中的四资源集中审核；导航/完整 Tab、图标层次与完整右栏仍有差异，不能只凭字段表或颜色称还原完成。H05/H06 的实际状态和最终截图要在正式准入、真实派发、评价以后获取。当前三条原申请仍 PENDING、资源 DRAFT，禁止用 fixture 成功图代替该实际页面验收。后续本人完成原申请后，继续同视口实际页面修正及对照，而非关闭本任务。

全新 AI 入口追加逐页实读 R35/P01、P02、P03，登录失效对应 IAM03；摘要已追加同一映射。P02/P03 消息方向按用户最新“用户靠右、系统靠左”约束。未发现 context 独立签发专用业务效果图，现有授权页追加正式操作面板，不以 IAM03 登录失效图冒充授权页面基线；该面板视觉接受仍 NOT_GRANTED。
