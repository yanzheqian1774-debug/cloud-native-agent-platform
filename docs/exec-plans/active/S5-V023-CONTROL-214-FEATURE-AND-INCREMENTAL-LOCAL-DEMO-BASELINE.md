# S5-V023-CONTROL-214 — v0.2.3 Feature and Incremental Local Demo Control Baseline

## Decision record

| Field | Value |
| --- | --- |
| Session | `S5-V023-CONTROL-214` |
| Type | `CONTROL / PRODUCT_DELIVERY_GOVERNANCE` |
| Human Checkpoint A | `PASS_WITH_MANDATORY_EXECUTION_AMENDMENTS` |
| Final status | `V0_2_3_FEATURE_AND_INCREMENTAL_LOCAL_DEMO_CONTROL_BASELINE_ACCEPTED` |
| Baseline inspected | `9a0e9b50b7d47a055ac2df3879f1b02224d9d966` |
| Contract status | Internal v0.2.3 delivery-control baseline; not a frozen public Contract |
| Release status | No complete v0.2.3, Public Preview, Formal Release, certification, Agent Fleet, or production-readiness claim |

This document is the Human-accepted execution-control baseline for the v0.2.3
Product increment. It reconciles durable source and test evidence with accepted
product and architecture direction. Source and tests remain authoritative for
implemented behavior; accepted architecture decisions remain authoritative for
architecture.

`S5-V023-CONTROL-214` is a Human-approved one-time namespace exception because
suffix `214` lies in the implementation band. The exception MUST NOT establish
a repeatable allocation pattern. Every future identifier requires a fresh
global suffix audit and normal task-type routing.

## Completion and claim rules

A schema, migration, repository, API, resource card, published Definition,
fixture, declared binding, or focused test is not a complete Product capability.

A Level-2 capability is eligible for `LOCAL_HUMAN_ACCEPTED` only after it has,
where applicable:

1. durable backend behavior;
2. authoritative persistence and restart readback;
3. a real Product API and deterministic bootstrap;
4. truthful Product UI;
5. real data;
6. required real invocation or execution;
7. canonical Evidence and Outcome;
8. real-browser acceptance;
9. the Chinese-first language gates; and
10. explicit local Human acceptance.

Use only these completion classifications:

`NOT_STARTED`, `ARCHITECTURE_ONLY`, `FOUNDATION_COMPLETE`,
`APPLICATION_COMPLETE`, `API_ASSEMBLED`, `UI_AVAILABLE`,
`REAL_DATA_PROVEN`, `REAL_EXECUTION_PROVEN`, `LOCAL_HUMAN_ACCEPTED`,
`PUBLIC_PREVIEW_ACCEPTED`, `FORMAL_RELEASE_ACCEPTED`, `BLOCKED`, and
`DEFERRED`.

## Evidence-weighted baseline

The percentages are delivery-control estimates, not release acceptance. They
measure durable domain behavior, persistence, application, API/bootstrap, UI,
real data, required real execution, and Evidence/browser/Human acceptance.

| Level-1 capability | Baseline completion | Highest defensible state |
| --- | ---: | --- |
| Workbench and Business Entry | 44% | `UI_AVAILABLE` |
| Digital Employee Management | 43% | `APPLICATION_COMPLETE` |
| Workflow and Work Execution | 46% | `APPLICATION_COMPLETE` |
| Skill, MCP and Knowledge | 58% | `REAL_DATA_PROVEN` |
| Runtime and Provider Operations | 46% | `APPLICATION_COMPLETE` |
| Evidence, Outcome and Governance | 55% | `REAL_DATA_PROVEN` |
| Product Experience | 34% | `UI_AVAILABLE` |
| Demo and Delivery | 21% | `FOUNDATION_COMPLETE` |
| **Weighted v0.2.3 total** | **43%** | **`FOUNDATION_COMPLETE`** |

Work in open or active tasks is excluded until durably integrated and accepted.

## Durable implementation mapping

| Authority or delivery | Durable identity | Current meaning |
| --- | --- | --- |
| ARCH-201 / REL-202 | PR #129, merge `caea10a` | Product capability, interaction, and acceptance architecture |
| IMPL-210 / REL-205 | PR #130, merge `6e8ebf7` | Execution application-service foundation |
| ARCH-204 / REL-206 | PR #132, merge `b1808df` | Workflow Operations, managed resources, and fleet-ready addendum |
| IMPL-230 / REL-207 | PR #131, merge `090ff05` | Native/OpenClaw provider factory and adapter assembly |
| ARCH-208 / REL-209 | PR #135, merge `89d8c2a` | Plan, approval, and intervention persistence authority |
| IMPL-220 / REL-211 | PR #134, merge `7392a4f` | Digital Employee Instance, Assignment, and Placement services |
| IMPL-221 / REL-212 | PR #137, merge `4d1d448` | Workflow-control persistence |
| IMPL-222 / REL-213 | PR #139, merge `9a0e9b5` | Workflow-control atomic Unit of Work extension |
| IMPL-223 | active at Checkpoint A | Digital Employee API/bootstrap; not yet durable |
| IMPL-224 | active at Checkpoint A | Workflow-control successor/Evidence/Outcome contract completion; not yet durable |
| IMPL-240 | `BLOCKED` | Resume only after accepted, durable IMPL-224 handoff |

IMPL-223 and IMPL-224 SHOULD proceed in parallel while their exact path sets
remain disjoint. Their durable integrations MUST be serialized against a fresh
`main`. IMPL-240 depends on the accepted IMPL-224 handoff.

## Level-1 and Level-2 feature matrix

Every row records its owner, dependency, real-data proof, real-execution proof,
and mandatory local milestone. Suggested future task numbers are not allocated
by this document.

| ID | 中文 / English | Owning implementation task | Dependency | Required real-data proof | Required real invocation/execution proof | Local milestone |
| --- | --- | --- | --- | --- | --- | --- |
| WB-01 | 业务问题与计划 / Business Intake and Planning | shared Product assembly owner | A–F accepted | governed Business Problem, success criteria, and Plan | downstream orchestration consumes the exact Plan | G |
| WB-02 | 精确计划审批 / Exact Plan Approval | IMPL-224 then resumed IMPL-240 | IMPL-221/222 and accepted 224 | immutable Plan version and digest | zero effect before approval; approved execution after | E, G |
| WB-03 | 任务与待办中心 / Task and Attention Center | Workflow Product Experience owner | live IMPL-240 APIs | real pending Task/Intervention | browser action changes governed state | E, G |
| WB-04 | 跨视图业务上下文 / Cross-view Business Context | serialized assembly owner | stable feature DTOs | byte-equal identities in all projections | exact invocation/execution Evidence navigation | A–G |
| DE-01 | 数字员工定义 / Digital Employee Definition | existing domain plus IMPL-223 and Employee UI owner | resource lifecycle services | exact published revision and digest | Definition creates a real Instance | A |
| DE-02 | 数字员工实例 / Digital Employee Instance | IMPL-223 backend; Employee UI owner | durable IMPL-220 | PostgreSQL Instance restart readback | Instance participates in Assignment and execution | A |
| DE-03 | 工作分配 / Assignment | IMPL-223 backend; Employee UI owner | DE-02 and approved work | durable scoped Assignment | Assignment feeds real Placement/execution | A, E |
| DE-04 | 执行放置与就绪 / Placement and Readiness | IMPL-223, IMPL-240, Runtime UI owner | Assignment and provider readiness | durable Placement and observation | placed Attempt executes; unavailable target rejects | A, F |
| WF-01 | 工作流定义与计划 / Workflow Definition and Plan | IMPL-224, IMPL-240, Workflow UI owner | existing Workflow lifecycle | exact Definition and Plan versions | approved Plan creates a real Run | E |
| WF-02 | 执行层级 / Execution Hierarchy | IMPL-210 plus IMPL-240 and Workflow UI owner | approval, Placement, provider | Run, Task Run, Attempt hierarchy | terminal real Attempt | E, F |
| WF-03 | 人工干预与控制 / Human Intervention and Control | resumed IMPL-240; Workflow UI owner | accepted/durable IMPL-224 | durable commands, transitions, and replay history | pause, input, resume, retry, rerun, or cancel effect | E |
| WF-04 | 修正与后继比较 / Correction and Successor Comparison | IMPL-224 then IMPL-240 and Workflow UI owner | successor Plan and atomic fact creation | immutable predecessor/successor Plans | successor executes and produces comparable Outcome | E, G |
| CAP-01 | Skill 生命周期 / Skill Lifecycle | existing Skill domain plus governed-use owner | stable Attempt identity | exact published Skill revision/digest | Skill is really invoked by the exact Attempt | B |
| CAP-02 | MCP 端点、发现与调用 / MCP Endpoint, Discovery and Invocation | dedicated MCP capability owner | approved callable endpoint and stable Attempt | endpoint config and exact discovery snapshot | real authorized MCP operation call | C |
| CAP-03 | Knowledge 生命周期与检索 / Knowledge Lifecycle and Retrieval | existing Knowledge domain plus governed-use owner | PostgreSQL, Qdrant, stable Attempt | real revision and derived index snapshot | real retrieval with exact citation | D |
| CAP-04 | Attempt 范围资源使用 / Attempt-scoped Resource Use | governed resource-use owner | stable IMPL-240 Attempt/control path | exact binding and authorization decision | Attempt-scoped Skill, MCP, and Knowledge consumption | B–E |
| RT-01 | Runtime Profile 与 Provider Factory | IMPL-230 plus serialized assembly owner | exact compatibility data | exact Profile/provider/config | factory selects and creates the working provider path | F |
| RT-02 | Native Runtime 操作 / Native Runtime Operations | Runtime Operations owner | IMPL-057/210/230 and stable control | real Runtime/Agent Instance observation | terminal Native Platform task | F |
| RT-03 | OpenClaw Runtime 操作 / OpenClaw Runtime Operations | Runtime Operations owner plus assembly | exact approved OpenClaw version | provider instance, health, readiness, freshness | terminal OpenClaw Platform task | F |
| RT-04 | 受管 Runtime 组合 / Managed Runtime Portfolio | Runtime Operations owner | RT-01–03 facts | generations, commands, observations | stop, re-observe, bounded replacement | F |
| GOV-01 | 事件与执行证据 / Events and Execution Evidence | IMPL-240/resource-use owners plus assembly | sole PostgreSQL writer | durable ordered Events/Evidence | Evidence originates from each real effect | B–G |
| GOV-02 | Outcome 与 Feedback / Outcome and Feedback | IMPL-224 then IMPL-240 and Workflow UI owner | atomic Outcome contract | immutable Outcome and feedback history | Outcome cites terminal execution Evidence | E, G |
| GOV-03 | 授权、隔离与审计 / Authorization, Isolation and Audit | every domain owner; independent acceptance | scoped principal/effect boundary | real scoped resources and decisions | denial produces zero lookup/call/effect | A–G |
| GOV-04 | 使用与运营指标 / Accounting and Operational Metrics | Runtime Operations owner | real provider/resource execution | usage and latency or explicit `NOT_MEASURABLE` | metrics originate from real execution | F, G |
| UX-01 | 中文优先信息架构 / Chinese-first Information Architecture | shared language-foundation predecessor; feature UI owners | stable glossary/navigation foundation | real resource labels and content | Chinese actions operate real capability | A–G |
| UX-02 | 真实状态与限制 / Truthful States and Limitations | each feature UI owner; UX hardening owner | backend error taxonomy | real empty, denied, stale, unavailable states | real failed/unavailable operation | A–G |
| UX-03 | 响应式与无障碍 / Responsive and Accessibility | UX hardening owner | stable feature surfaces | same real data at both viewports | keyboard/touch performs real action | A–G |
| UX-04 | 四视图一致性 / Product, Operations, Technical, Evidence Consistency | Runtime/assembly owners | canonical identity and Evidence | same objects in all projections | execution/invocation reachable from each view | A–G |
| DL-01 | 真实数据引导 / Real-data Bootstrap | future ASSEMBLY owner | accepted feature APIs | deterministic isolated real-service data | bootstrap enables real A–F effects | A–G |
| DL-02 | 增量本地验收 / Incremental Local Acceptance | future ACCEPT owners | each feature gate ready | per-gate provenance manifest | per-gate real effect report | A–F, P1–P3 |
| DL-03 | v0.2.3 黄金场景 / v0.2.3 Golden Scenario | future ASSEMBLY then ACCEPT owners | A–F `LOCAL_HUMAN_ACCEPTED` | complete canonical scenario | end-to-end resolution and successor | G |
| DL-04 | Preview 与发布控制 / Preview and Release Control | future release owner | G accepted at exact commit/tree | build/deployment provenance | deployed acceptance re-execution | after G |

## Capability-first delivery gates

Before complete Business Problem orchestration, independently establish and
locally demonstrate managed capability completeness for:

| Gate | Capability | Mandatory real proof |
| --- | --- | --- |
| A | Digital Employee Management | Definition, lifecycle, revision, configuration, Instance, Assignment, Placement/readiness, execution participation, Evidence, Product UI, denied/unavailable state |
| B | Skill Management and Invocation | lifecycle, exact Skill revision, configuration/test/publication, binding, real Attempt invocation, result/failure Evidence, Product UI, incompatible/denied/unavailable state |
| C | MCP Endpoint, Discovery and Invocation | Human-approved project-owned or explicitly approved callable endpoint, real discovery, authorization, invocation, canonical Evidence, Product UI, unreachable/schema-mismatch/denied state |
| D | Knowledge Ingestion, Retrieval and Citation | durable source/revision, real ingestion, exact index snapshot, binding, real retrieval, exact citation, Evidence, Product UI, denied/stale/unavailable/no-result state |
| E | Workflow Execution and Intervention | Definition/Plan, exact approval, bindings, real hierarchy, intervention, immutable correction successor, atomic Evidence/Outcome, Product UI, conflict/failure/recovery state |
| F | Runtime Provider Operations | Profile/version/config, Runtime/Agent Instance lifecycle, health/readiness/freshness, Placement, real Native and OpenClaw execution, Evidence, UI, unavailable/incompatible/stale/unknown/recovery state, stop/re-observe/replacement |
| G | Complete Business Problem Resolution | exact Business Problem and success criteria → approved Plan → real execution and resource use → Evidence → Outcome that determines whether the original criteria were satisfied → feedback/correction/successor comparison |

A localhost, test, embedded, or synthetic MCP fixture validates protocol behavior
only. It MUST NOT satisfy gate C. Gate C requires a Human-approved,
project-owned or explicitly approved callable MCP endpoint plus real discovery,
authorization, invocation, and canonical Evidence.

G MUST NOT start its acceptance claim until A–F are each
`LOCAL_HUMAN_ACCEPTED`. G consumes canonical A–F Product APIs; it MUST NOT add
demo-only authority or substitute synthetic success.

## Non-final integration progress demonstrations

These progress demonstrations expose integration risk early. They do not
replace A–F acceptance and do not establish Golden Demo completion.

| Gate | Included integration | Required observation |
| --- | --- | --- |
| P1 | Digital Employee + Knowledge + governed resource binding | exact employee/resource revisions, authorized binding, real retrieval/citation, Evidence, truthful unavailable state |
| P2 | Digital Employee + Skill + Workflow + Human Intervention | exact Instance/Assignment/Skill/Plan, real Skill use, governed intervention, successor/history visibility |
| P3 | MCP + Native/OpenClaw + Evidence/Outcome | approved MCP endpoint, real discovery/invocation through Native and OpenClaw path where applicable, canonical Evidence, terminal Outcome |

Route progress assembly under a freshly audited `ASSEMBLY` Session and
independent Human review under a freshly audited `ACCEPT` Session. `DEMO` MUST
NOT be used as a `TASK_TYPE`.

## Chinese-first Product language contract

Contract identity: `V023_PRODUCT_LANGUAGE_ZH_CN_V1`.

The shared terminology, enum-state mapping, navigation hierarchy, and bilingual
layout foundation MUST be implemented before the feature UI wave. English is
secondary explanatory text where useful. Backend identifiers, stored enums,
field names, revisions, digests, and protocol values remain byte-exact.

Display mapping is deterministic:

```text
stored/API value
→ shared frontend display mapping
→ Chinese primary label
→ optional English secondary explanation
→ exact raw value in expanded technical detail
```

### Normative terminology glossary

| Canonical term | Primary Chinese | Permitted secondary English |
| --- | --- | --- |
| Business Problem | 业务问题 | Business Problem |
| Success Criteria | 成功标准 | Success Criteria |
| Digital Employee Definition | 数字员工定义 | Digital Employee Definition |
| Digital Employee Instance | 数字员工实例 | Digital Employee Instance |
| Assignment | 工作分配 | Assignment |
| Placement | 执行放置 | Placement |
| Skill | 技能 | Skill |
| MCP | MCP | Model Context Protocol |
| Knowledge | 知识 | Knowledge |
| Workflow | 工作流 | Workflow |
| Plan | 执行计划 | Plan |
| Workflow Run | 工作流运行 | Workflow Run |
| Task Run | 任务运行 | Task Run |
| Attempt | 执行尝试 | Attempt |
| Human Intervention | 人工干预 | Human Intervention |
| Evidence | 执行证据 | Evidence |
| Outcome | 业务结果 | Outcome |
| Runtime | 运行时 | Runtime |
| Provider | 提供方 | Provider |
| Desired State | 期望状态 | Desired State |
| Observed State | 观测状态 | Observed State |
| Managed Resource Portfolio | 受管资源组合 | Managed Resource Portfolio |

### Normative state mappings

| Stored value | Primary Chinese display |
| --- | --- |
| `DRAFT` | 草稿 |
| `VALIDATED` | 已验证 |
| `TESTED` | 已测试 |
| `HUMAN_REVIEWED` | 已完成人工审查 |
| `PUBLISHED` | 已发布 |
| `MATCHABLE` | 可匹配 |
| `DEPRECATED` | 已弃用 |
| `PENDING` | 等待处理 |
| `RUNNING` | 运行中 |
| `SUCCEEDED` | 已成功 |
| `FAILED` | 已失败 |
| `PAUSED` | 已暂停 |
| `CANCELLED` | 已取消 |
| `UNKNOWN` | 状态未知 |
| `STALE` | 状态已过期 |
| `RECOVERY_REQUIRED` | 需要恢复处理 |
| `REQUESTED` | 已请求 |
| `APPLIED` | 已应用 |
| `REJECTED` | 已拒绝 |
| `EXPIRED` | 已过期 |
| `NOT_MEASURABLE` | 当前无法度量 |
| `UNAVAILABLE` | 当前不可用 |
| `DENIED` | 无权访问 |
| `INCOMPATIBLE` | 不兼容 |

Mappings MUST be exhaustive for supported Product states. Unknown values render
a safe Chinese primary label while retaining the exact value in technical
detail. Color or icon alone never conveys state.

Information hierarchy is:

```text
业务视图 → 运营视图 → 技术详情 → 证据视图
```

Every A–G acceptance result MUST independently report:

- `CHINESE_FIRST_UI`;
- `ENGLISH_SECONDARY_ONLY`;
- `TERMINOLOGY_CONSISTENCY`;
- `MOBILE_DUAL_LANGUAGE_LAYOUT`; and
- `BUSINESS_FIRST_INFORMATION_HIERARCHY`.

Any failure prevents `LOCAL_HUMAN_ACCEPTED`. A predominantly English primary
journey is capped at its lower technical delivery classification.

## Shared-path and delivery ownership

| Path or concern | Sole owner rule |
| --- | --- |
| Digital Employee backend routes/schema/bootstrap | IMPL-223 only |
| Workflow-control contracts | IMPL-224 only until stable handoff |
| Workflow-control application behavior | resumed IMPL-240; consume, do not redefine, IMPL-224 |
| Skill/MCP/Knowledge Attempt-scoped use | one governed resource-use owner with endpoint-specific review |
| Feature-local UI pages | respective capability Product Experience owner |
| Shared terminology, enum mapping, navigation hierarchy, bilingual layout | one language-foundation predecessor before feature UI |
| Backend application bootstrap and dependency wiring | one serialized ASSEMBLY owner |
| Global frontend route/navigation/shared DTO wiring | one serialized ASSEMBLY owner |
| Provider registration | provider implementation remains provider-local; global registration belongs to ASSEMBLY |
| Progress and capability review | independent ACCEPT owners |
| CI, deployment, cutover, Preview, release | later separately authorized owner |

At most two heavy feature writers run concurrently. Shared assembly starts only
after their exact path sets are frozen and accepted for integration.

## Dependency and critical path

```text
IMPL-223 ───────────────────────────────────────────────┐
IMPL-224 → durable handoff → resumed IMPL-240 ─────────┼─→ governed resource use
IMPL-230 and existing resource foundations ────────────┘
        ↓
shared Chinese-first language/navigation foundation
        ↓
feature-local capability UI and real-service closure
        ↓
A, B, C, D, E, F independent local acceptance
        ↓
P1, P2, P3 progress evidence as useful; never substitution
        ↓
serialized ASSEMBLY
        ↓
G independent local Human acceptance
        ↓
separately authorized Preview and release gates
```

The highest technical uncertainty is a real exact-version OpenClaw task through
the assembled Platform path. The highest external capability uncertainty is a
Human-approved callable MCP endpoint. The highest coordination risk is
concurrent mutation of shared bootstrap, routes, DTOs, navigation, language
mappings, and provider registration.

## v0.2.2 forward adaptation

No maintenance-branch merge or direct cherry-pick is authorized.

| Lesson or artifact | Disposition |
| --- | --- |
| Chinese-first navigation, primary actions, and coherent journey | `REIMPLEMENT_ON_V023` |
| Digital Employee → resources → Assignment → Workflow → execution → Evidence → Outcome flow | `REIMPLEMENT_ON_V023` |
| Canonical Product/Technical/Evidence navigation and resource workbenches | `ALREADY_IN_MAIN`; extend, do not duplicate |
| Controlled empty, denied, unavailable, and failure states | `ALREADY_IN_MAIN`; extend and reaccept |
| Template-only Employee, Definition-only Workflow, declaration-only Runtime Profile layouts | `DESIGN_REFERENCE_ONLY` |
| v0.2.2 maintenance bootstrap and embedded MCP fixture | `V022_ONLY` |
| English-dominant primary shell | `SUPERSEDED` |
| synthetic identifiers, fixture success labeled live, UI-only approval evidence | `REJECTED` |
| maintenance merge or direct cherry-pick | `REJECTED` |

## Deferred and prohibited scope

v0.2.4 retains Enterprise Model Catalog, evaluation, governed selection,
Human override, exact model binding, and evidence-backed fallback.

Complete Runtime/Fleet Manager, Tenant/Organization administration, centralized
enterprise policy/RBAC, Marketplace, full FinOps, HA, autoscaling, failover,
generalized recovery, multi-cluster/region/cloud placement, certification, and
production readiness remain v0.3.x or separately approved future scope.

This baseline prohibits:

- public Agent/Task/Workflow CRD or API-group changes;
- a Digital Employee CRD;
- replacement of Kubernetes as current Control Plane authority;
- silent Native fallback for OpenClaw;
- Provider, Pod, or session identifiers as Product identity;
- fixture or prerecorded output presented as live capability proof;
- gate C acceptance from any local/test/embedded/synthetic MCP fixture;
- `DEMO` as a task type;
- a complete v0.2.3, Preview, release, certification, Agent Fleet, or
  production-readiness claim from this control decision.

## Human Checkpoint A result

```text
PASS_WITH_MANDATORY_EXECUTION_AMENDMENTS /
V0_2_3_FEATURE_AND_INCREMENTAL_LOCAL_DEMO_CONTROL_BASELINE_ACCEPTED
```

This Human decision accepts the feature matrix, capability-first sequence,
progress demonstrations, Chinese-first Product language contract, ownership
boundaries, and dependency plan. It grants no implementation completion,
deployment, Public Preview, Formal Release, certification, or
production-readiness status.
