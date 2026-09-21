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
