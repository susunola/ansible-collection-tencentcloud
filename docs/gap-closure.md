# Gap closure plan — 与行业顶尖 Collection 的差距追差

> 依据：`docs/capability-map.html` 的 INDUSTRY BENCHMARK 区块（Galaxy 已发布产物实拉，2026-09-02）。
> 对比对象：amazon.aws 11.4.0 / azure.azcollection 4.0.0 / google.cloud 1.14.0。
> 状态图例：✅ 已闭合 · 🔄 在途 · ⏸ 排队/等待外部 · 📋 待启动 · ❌ 明确不追（有意取舍）。

## 差距总览

| ID | 差距维度 | 本库实测 | 行业最优实测 | 判定 | 状态 |
|---|---|---|---|---|---|
| G1 | 集成测试深度 | 21 targets / 62 yml | amazon 160 targets / 690 yml（google 115 targets / 468 yml） | 落后 ~8x（按 target） | 🔄 待启动独立集成计划 |
| G1b | 单测广度（write 面） | write 模块 222/313 无单测 | 覆盖率 60.9%（目标 70） | 广度缺口 | 🔄 roadmap #57 在途 |
| G2 | 生态信任与下载 | 0（2026-09 首发） | amazon 90.5M | 差距巨大 | ⏸ #89 inclusion 评审中 |
| G3 | ansible-core 门槛 | ≥ 2.19 | ≥ 2.16 / 2.17 | 声明更高 | ❌ 有意取舍，不追 |
| G4 | 维护资源 | 个人维护 | 厂商 + Red Hat/社区团队 | 结构性差距 | 📋 缓解型动作 |

> 口径修正（2026-09-02 晚）：集成测试原按 yml 数对比（62 vs 690，得 ~11x），
> 但各家 target 内 yml 组织密度不同（amazon 690 yml 属 160 个 target；本库 62 yml
> 属 21 个 target，其中 1 个是 coverage.yml），按 target 数对比更公平：
> 21 vs 160 vs 115 ≈ 落后 ~8x（对 google 为 ~5.5x）。google 集成测试实为
> 115 targets / 468 yml（此前误记 504，那是全仓库含单测的 yml 数）。

## G1 集成测试深度 — 📋 需独立计划（不要把 #57 误记为集成驱动）

**现状**：21 targets / 62 yml（`tests/integration/targets/`）。与 amazon 160 / google 115
的差距按 target 数约 8x / 5.5x。**关键盲区**：13 个旗舰 write 模块（cvm_instance、vpc、
subnet、cdb_instance、redis_instance、tke_cluster、clb_load_balancer、cos_object、
scf_function、ckafka_instance、cbs_disk、eip、nat_gateway）全部无集成 target ——
旗舰面集成覆盖为零。

> ⚠️ 逻辑修正（2026-09-02）：roadmap #57 是**单元测试覆盖驱动**（针对 write 模块
> 语句覆盖率，已由 G1b 承接），**不是**集成测试驱动，不能记在 G1 名下。G1 需要
> 单独的集成计划。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G1-a | 为旗舰 write 模块建集成 target 骨架（cvm_instance 起步，复用 amazon `tests/integration/targets/` 布局；先容器化/假云认证，再接真实环境 job） | 无 | 2026-09-16 | 📋 |
| G1-b | 定义集成测试的可信执行环境（真实腾讯云账号 + 资源清理策略，或 ansible-test cloud 插件） | G1-a | 随首批 | 📋 |
| G1-c | 目标：集成 target 21 → 30+（先覆盖 13 个旗舰中的 5 个） | G1-a/b | 2026-10 | 📋 |

**验收**：cvm_instance / vpc / cdb_instance / redis_instance / tke_cluster 至少进入
集成套件；集成 target ≥ 30。

## G1b 单元测试广度（write 面）— 🔄 在途（roadmap #57，唯一持续缩小项）

**现状**：313 个 write 模块中 222 个无专属单测文件（coverage-batching 结构扫描；
其中 175 个共享同一 helper 骨架，组 A 20 waiter-CRUD + 组 B 155 纯 CRUD）。
语句覆盖率 ~60.9%（gate 55），目标把 write 面推回 70% 基线。批次 1-11 已把
单模块从 1-2h 压到 20-40min（lever-1 骨架生成器待实现）。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G1b-a | 先实现 `--module-test` 骨架生成器（coverage-batching.md lever 1） | 无 | 下一批前 | 📋 |
| G1b-b | batch 12+：按 per-file miss 报告从高到低逐模块写测试 | G1b-a 可并行，不阻塞 | 每周 1-2 批 | 🔄 |
| G1b-c | 每批 commit + CI 全绿（sanity 矩阵 + coverage gate 55 不破） | G1b-b | 随批 | 🔄 |

**验收**：write 模块语句覆盖率从 ~51% 推回 70% 基线（222 个无单测模块逐步收口，gate 55 全程不破）。

## G2 生态信任 — ⏸ 半被动（inclusion #89 评审中）

**现状**：inclusion 申请已提交（discussion #89，2026-09-02），自查评论已贴（discussioncomment-18250641），仓库已有 v1.0.0 tag。评审者尚未回复。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G2-a | 按官方流程评审 1 个排队中的他人 collection（README step 1：先评审别人可提升自身优先级） | 官方 README 排队清单 | 2026-09-09 | 📋 |
| G2-b | 每周五检查 #89 是否有评审反馈并回复 | 无 | 每周 | ⏸ |
| G2-c | 保持 devel 每周测试 + release 节奏（devel.yml/release.yml 已在跑） | 无 | 持续 | ✅ 已自动化 |

**验收**：#89 进入正式 review；Galaxy 周下载量 > 0。

## G3 ansible-core 门槛 — ❌ 不追（有意取舍，改表述）

**事实核查**：2.16 EOL 2025-07、2.17 EOL 2025-11、2.18 EOL 2026-05 —— 三家官方声明的 ≥2.16/≥2.17 是历史包袱，其 CI 实际也只测最新几版；本库从 v1.0.0 就以 ≥2.19 起步、CI 矩阵 2.19/2.20/2.21 + 每周 devel 测试，是主动对齐 ansible-core 演进的选择，不是落后。降到 EOL 版本只会背上"声明支持但不测"的合规债。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G3-a | **维持** `requires_ansible: >=2.19.0` 不变 | 无 | — | ✅ 决策 |
| G3-b | 修正 capability-map.html 差距卡 G3 措辞（见下），避免"门槛更高 = 更差"的误导 | 无 | 随 HTML commit | 📋 |

**能力图差距卡措辞调整（G3 原文 → 新文）**：
> ▼ 原文："ansible-core 门槛：要求 ≥2.19，高于三家的 ≥2.16/≥2.17，会拒绝一部分旧控制节点用户。"
> ▲ 新文："ansible-core 门槛：≥2.19 起步（2.16–2.18 已 EOL；三家 ≥2.16/≥2.17 为历史声明，实际 CI 只测最新版）—— 主动对齐演进，换取旧控制节点用户覆盖的部分代价。"

## G4 维护资源 — 📋 结构性，缓解型动作

**现状**：个人维护。已有底子比差距卡显示的好：CONTRIBUTING.md（105 行）、MAINTAINERS.md、SECURITY.md、issue/PR 模板齐全；生成式治理（spec 生成 + 禁止手改）已把个人维护的人均负担压到最低。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G4-a | CONTRIBUTING.md 补"如何成为 co-maintainer"一节，明确加入路径与权限边界 | 无 | 2026-09-30 | 📋 |
| G4-b | inclusion 通过后招募 1-2 名 co-maintainer（在 #89 评审期间同步观察社区反馈） | G2 通过 | 评审后 | ⏸ |
| G4-c | 能力图差距卡 G4 措辞从"个人维护"改为"个人维护（贡献/加入路径见 CONTRIBUTING.md）" | G4-a | 随 HTML commit | 📋 |

**验收**：issue 首响 < 48h 的可记录 SLA；至少 1 名外部 contributor 合入 PR。

## 待批准执行清单

1. G1-a 集成 target 骨架（旗舰 cvm_instance 起步，2026-09-16 前，需确认执行环境策略：容器化 mock vs 真实账号）
2. G1b-a 单测骨架生成器（下批前，纯本地，1 commit）
3. G1b-b 继续 batch 12（每周节奏，不需特批）
4. G2-a 评审 1 个他人 collection（2026-09-09 前，需你指定目标或我从官方清单挑）
5. G3-b + G4-c capability-map.html 差距卡措辞修正（1 commit，随 benchmark 区块）
6. G4-a CONTRIBUTING.md 补 co-maintainer 路径（2026-09-30 前，低优先级）

---

_本计划由 docs/capability-map.html INDUSTRY BENCHMARK 区块派生 · 2026-09-02 · 数据均为 Galaxy 产物实拉_
