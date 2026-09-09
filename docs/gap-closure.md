# Gap closure plan — 与行业顶尖 Collection 的差距追差

> 依据：`docs/capability-map.html` / `docs/panorama.html` 的 INDUSTRY BENCHMARK 区块
> （本库源码 main HEAD 实测 + 对比方 Galaxy 产物实拉；2026-09-02 初版，2026-09-08 随 P0-12 同步刷新，
> 2026-09-09 随 P0-03/04 同步 G1 集成口径至 26 targets / 77 yml）。
> 对比对象：amazon.aws 11.4.0 / azure.azcollection 4.0.0 / google.cloud 1.14.0（版本未变，沿用 09-02 核验）。
> 状态图例：✅ 已闭合 · 🔄 在途 · ⏸ 排队/等待外部 · 📋 待启动 · ❌ 明确不追（有意取舍）。

## 差距总览

| ID | 差距维度 | 本库实测 | 行业最优实测 | 判定 | 状态 |
|---|---|---|---|---|---|
| G1 | 集成测试深度 | 26 targets / 77 yml | amazon 160 targets / 690 yml（google 115 targets / 468 yml） | 落后 ~6x（按 target；google ~4.4x） | 🔄 在途（P0-01/02 已落 5 旗舰 target） |
| G1b | 单测广度（write 面） | 无专属单测 write 模块 222 → 111（440 中 25%，2026-09-08） | 覆盖率 81.44%（gate 80，2026-09-08） | 广度缺口缩小 | ✅ 里程碑达成，收口持续 |
| G2 | 生态信任与下载 | 0（2026-09 首发） | amazon 90.5M | 差距巨大 | ⏸ #89 inclusion 评审中 |
| G3 | ansible-core 门槛 | ≥ 2.19 | ≥ 2.16 / 2.17 | 声明更高 | ❌ 有意取舍，不追 |
| G4 | 维护资源 | 个人维护 | 厂商 + Red Hat/社区团队 | 结构性差距 | 📋 缓解型动作 |

> 口径修正（2026-09-02 晚）：集成测试原按 yml 数对比（62 vs 690，得 ~11x），
> 但各家 target 内 yml 组织密度不同（amazon 690 yml 属 160 个 target；本库 62 yml
> 属 21 个 target，其中 1 个是 coverage.yml），按 target 数对比更公平：
> 21 vs 160 vs 115 ≈ 落后 ~8x（对 google 为 ~5.5x）。google 集成测试实为
> 115 targets / 468 yml（此前误记 504，那是全仓库含单测的 yml 数）。

## G1 集成测试深度 — 🔄 在途（P0-01/02 骨架落地 · P0-04 扩至 30+）

**现状**（2026-09-09 随 P0-03/04 刷新，此前口径沿革见 09-02 注）：26 targets / 77 yml
（`tests/integration/targets/` 76 yml + 1 coverage.yml）。与 amazon 160 / google 115 的差距按
target 数约 6x / 4.4x。**旗舰覆盖**：13 个旗舰 write 模块中 cvm_instance / vpc / subnet /
cdb_instance / tke_cluster 已有专属集成 target（provision → assert → cleanup，落地 `6d83295`）；
eip / clb_load_balancer 由 network / clb_http 场景 target 覆盖。**剩余盲区**：redis_instance /
cos_object / scf_function / ckafka_instance / cbs_disk / nat_gateway 六个旗舰仍无任何集成覆盖，
已按 product-depth 排入 P0-04 路线图（`docs/integration-env.md` §7 R1-R6）。

> ⚠️ 逻辑修正（2026-09-02）：roadmap #57 是**单元测试覆盖驱动**（针对 write 模块
> 语句覆盖率，已由 G1b 承接），**不是**集成测试驱动，不能记在 G1 名下。G1 需要
> 单独的集成计划。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G1-a | 为旗舰 write 模块建集成 target 骨架（复用 amazon `tests/integration/targets/` 布局；执行环境策略定为真实腾讯云账号 + 计费护栏） | 无 | 2026-09-16 | ✅ P0-01/02（`6d83295`，2026-09-09：cvm_instance / vpc / subnet / cdb_instance / tke_cluster） |
| G1-b | 定义集成测试的可信执行环境（真实腾讯云账号 + 凭据注入 + 资源清理防线 + 失败告警） | G1-a | 随首批 | ✅ P0-03（`docs/integration-env.md` 落盘 + workflow 凭据接线/告警步，2026-09-09） |
| G1-c | 目标：集成 target 26 → 30+（13 旗舰已覆盖 7 个：5 专属 + 2 场景；余 6 个按 product-depth 优先补） | G1-a/b | 2026-10 | 🔄 P0-04（R1-R9，2026-09 里程碑 28 dirs，见 `docs/integration-env.md` §7） |

**验收**：cvm_instance / vpc / subnet / cdb_instance / tke_cluster 已进入集成套件 ✅（2026-09-09）；
redis_instance 等其余旗舰随 P0-04 R1-R6 排入；2026-10 底前集成 target ≥ 30 且全部绿
（R1-R9 里程碑与验收口径见 `docs/integration-env.md` §7）。

## G1b 单元测试广度（write 面）— ✅ 80% 里程碑达成（收口持续）

**现状**：整体语句覆盖率 81.44%（2026-09-08 实测，9,985 tests / 30 skipped），
coverage gate 随实测抬至 80。80% 冲刺以主路径 `run_module` 单测批量新增
73 个模块测试文件（1,102 tests，6 组并行），write 面无专属单测模块从
222（/313，2026-08-31 基线）收口到 **111（/440，25%，2026-09-08）**。
历史基线（2026-08-31）：语句覆盖率 ~60.9%（gate 55）；
批次 1-11 已把单模块耗时从 1-2h 压到 20-40min。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G1b-a | 先实现 `--module-test` 骨架生成器（coverage-batching.md lever 1） | 无 | 下一批前 | 🔄 在途（P0-08，2026-09-08 启动） |
| G1b-b | 继续按 per-file miss 报告从高到低逐模块写测试（主路径单测 + 分支补漏） | G1b-a 可并行，不阻塞 | 持续 | 🔄 在途（P0-07，按 miss 榜批量） |
| G1b-c | 每批 commit + CI 全绿（sanity 矩阵 + coverage gate 不破，现 80） | G1b-b | 随批 | 🔄 |

**验收**：整体实测覆盖率 ≥ 80% 且 gate 抬至 80（✅ 2026-09-08 达成 81.44%）；
write 面无专属单测模块持续收口。

## G2 生态信任 — ⏸ 半被动（inclusion #89 评审中）

**现状**：inclusion 申请已提交（discussion #89，2026-09-02），自查评论已贴（discussioncomment-18250641），仓库已发布 v1.0.0 / v1.1.0（09-04）。评审者尚未回复（截至 09-08）。

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

## G5 引用解析与生命周期语义 — ✅ 已闭合（panorama P0-01 / P0-02）

> 依据：`docs/panorama.html`（2026-09-07 基线 `3c868f8`）。八项决定性差距里，
> panorama 自己点明"可以一次性补齐的是框架和约束"，其中两条为 P0：
> P0-01 统一资源引用 resolver、P0-02 统一生命周期与错误语义。

**为什么是 P0**：腾讯云 list 过滤是**子串匹配**（`vpc-name=prod` 会同时命中
`prod-old` / `prod-eu`），而 103 个 `find_*` 里绝大多数直接取 `XxxSet[0]`。
一条 `name: prod` 的 task 实际管到的是 API 恰好先返回的那一个，改名或删错资源
既可能发生也看不见。生命周期语义同理：not-found / 不可变漂移 / 异步等待 /
软删除 / check-diff 每个模块各写一份，靠复制保持一致，已经出现分歧。

**已交付**：

| 交付 | 内容 | 状态 |
|---|---|---|
| `module_utils/resolver.py` | 统一引用解析：ID 优先、精确名优于模糊名、唯一模糊候选接受、≥2 候选失败（C(ambiguous=true) + 候选清单）、无选择器返回 None（绝不静默通配）、支持 tag 与 register 变量 dict | ✅ |
| `module_utils/lifecycle.py` | 统一生命周期：C(error_envelope)/C(fail_from_sdk_error)（含脱敏与 C(error_kind)）、C(missing_as_none)、C(delete_resource)、C(soft_delete)（隔离→清除两阶段）、C(plan_changes)、C(require_state) | ✅ |
| 首批消费模块 | `vpc`、`subnet`、`security_group`、`route_table`、`eip`、`nat_gateway`、`cvm_instance` | ✅ |
| VPC 资源族 | `vpn_gateway`、`vpn_connection`、`peering_connection`、`network_interface`、`network_acl`、`vpc_flow_log`、`nat_gateway_rule`、`customer_gateway`、`dc_direct_connect`、`dc_direct_connect_tunnel` | ✅ |
| 资源族回归测试 | `tests/unit/plugins/modules/test_resource_family_resolution.py` 对全部查找入口断言同一契约（精确名优先 / 唯一模糊候选接受 / ≥2 候选 C(ambiguous) / ID 忽略噪声行） | ✅ |
| TKE 资源族 | `tke_cluster`、`tke_node_pool`、`tke_cluster_upgrade` | ✅ |
| 负载均衡资源族 | `clb_load_balancer`、`clb_target_group`、`clb_listener`、`clb_rule` | ✅ |
| 数据库资源族 | `cdb_instance`、`redis_instance`、`mongodb_instance`、`elasticsearch_instance`、`sqlserver_instance`、`mariadb_instance`、`dcdb_instance`、`postgresql_instance`、`cynosdb_cluster`、`tdcpg_cluster`、`tdmysql_db_instance` | ✅ |
| 数据库资源族读面 | `elasticsearch_instance_info`、`tdcpg_cluster_info` 生成补齐；`postgresql_instance` 映射至既有 `postgres_instance_info`（read 覆盖 153→155 / mapped 6→7 / gap 281→278） | ✅ |

**剩余**：resolver/lifecycle 已覆盖 VPC / TKE / 负载均衡 / 数据库四个旗舰资源族。
其余 ~20 个 `find_*` 仍是 first-match（TSF、TSE、DLC、TIONE、WAF、Oceanus、
TEO、CFW、CFS、Lighthouse 等），继续按 panorama 推荐顺序逐族推进，
每完成一个资源族同步升级对应角色与 info 面。

## 执行清单（2026-09-09 刷新）

> 全景图 30 件事（`docs/panorama.html`）已获批准执行 **P0×12 + P1×10**（本清单
> G1/G1b 相关项已并入对应 P0 编号；G2/G3/G4 映射的 P2 项仍在待批状态）。
> 状态图例：✅ 已完成 · 🔄 在途 · ⏸ 排队/等待外部 · 📋 待启动/待批准。

1. G1-a 集成 target 骨架 → **P0-01/02** ✅（cvm_instance/vpc/subnet/cdb_instance/tke_cluster 落地
   `6d83295`，2026-09-09；执行环境策略：真实腾讯云账号 + 计费护栏 + 三道清理防线）
2. G1-b/c 可信执行环境 + 30+ 路线图 → **P0-03/04** 🔄（`docs/integration-env.md` 已落盘 + workflow
   凭据接线/失败告警；R1-R9 至 2026-10 底，2026-09 里程碑 28 dirs）
3. G1b-a 单测骨架生成器 → **P0-08** 🔄（纯本地，1 commit，已启动）
4. G1b-b 继续 batch 12 → **P0-07** 🔄（每周节奏，111 → <60，不需特批）
5. G2-a 评审 1 个他人 collection → **P2-01** 📋（2026-09-09 前，需你指定目标或我从官方清单挑）
6. G3-b + G4-c capability-map.html 差距卡措辞修正 → ✅（已随 09-08 数据同步合入）
7. G4-a CONTRIBUTING.md 补 co-maintainer 路径 → **P2-03** 📋（2026-09-30 前，低优先级）

---

_本计划由 docs/capability-map.html / docs/panorama.html INDUSTRY BENCHMARK 区块派生 · 2026-09-02 初版 · 2026-09-08 随 P0-12 刷新至 781 模块 / 204 产品 / gate 80 口径 · 数据均为源码实测 + Galaxy 产物实拉_
