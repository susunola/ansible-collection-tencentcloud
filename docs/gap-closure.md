# Gap closure plan — 与行业顶尖 Collection 的差距追差

> 当前整合树快照（2026-09-23）：1025 模块（456 write + 569 _info）；下文行业基准及带日期数字仍为历史快照。

> 依据：`docs/capability-map.html` / `docs/panorama.html` 的 INDUSTRY BENCHMARK 区块
> （本库源码 main HEAD 实测 + 对比方 Galaxy 产物实拉；2026-09-02 初版，2026-09-08 随 P0-12 同步刷新，
> 2026-09-09 随 P0-03/04 同步 G1 集成口径至 26 targets / 77 yml，
> 2026-09-14 随 v1.4.0 发布全量重测：1005 模块 / 456 write + 549 _info、34 targets / 104 yml、
> 覆盖率 92.65%、write 无专属单测 111 → 0、读面缺口 356 → 112，其中真 backlog 28 → **0**
> （2026-09-15 由 G1-l 收干，见文末执行清单第 16 项）。
> 对比对象：amazon.aws 11.4.0 / azure.azcollection 4.0.0 / google.cloud 1.14.0（版本未变，沿用 09-02 核验）。
> 状态图例：✅ 已闭合 · 🔄 在途 · ⏸ 排队/等待外部 · 📋 待启动 · ❌ 明确不追（有意取舍）。

## 差距总览

| ID | 差距维度 | 本库实测 | 行业最优实测 | 判定 | 状态 |
|---|---|---|---|---|---|
| G1 | 集成测试深度 | 34 targets / 104 yml（2026-09-14） | amazon 160 targets / 690 yml（google 115 targets / 468 yml） | 落后 ~4.7x（按 target；google ~3.4x） | 🔄 在途（7 / 13 旗舰已覆盖，余 6 个排入 P0-04） |
| G1b | 单测广度（write 面） | 无专属单测 write 模块 222 → 111 → **0**（456 中 0%，2026-09-14） | 覆盖率 92.65%（gate 80） | 广度缺口已闭合 | ✅ 里程碑达成（info 侧 36 → 0 亦已收口，2026-09-14） |
| G2 | 生态信任与下载 | 553 累计（2026-09-14 实拉） | amazon 91.3M | 差距巨大 | ⏸ #89 inclusion 评审中 |
| G3 | ansible-core 门槛 | ≥ 2.19 | ≥ 2.16 / 2.17 | 声明更高 | ❌ 有意取舍，不追 |
| G4 | 维护资源 | 个人维护 | 厂商 + Red Hat/社区团队 | 结构性差距 | 📋 缓解型动作 |

> 口径修正（2026-09-02 晚）：集成测试原按 yml 数对比（62 vs 690，得 ~11x），
> 但各家 target 内 yml 组织密度不同（amazon 690 yml 属 160 个 target；本库 62 yml
> 属 21 个 target，其中 1 个是 coverage.yml），按 target 数对比更公平：
> 21 vs 160 vs 115 ≈ 落后 ~8x（对 google 为 ~5.5x）。google 集成测试实为
> 115 targets / 468 yml（此前误记 504，那是全仓库含单测的 yml 数）。

## G1 集成测试深度 — 🔄 在途（P0-01/02 骨架落地 · P0-04 扩至 30+）

**现状**（2026-09-14 全量重测，此前口径沿革见 09-02 / 09-09 注）：**34 个 target 目录 / 104 个 yml**
（`tests/integration/targets/` 102 yml + coverage.yml + smoke_readonly.yml）。按 target 数与
amazon 160 / google 115 的差距约 4.7x / 3.4x。**目录 ≠ 已跑**：34 个目录里 33 个进
`coverage.yml` registry、21 个在 workflow 默认清单；`cvm_image` / `lighthouse` 曾两侧都不在
（孤儿 target），09-14 已补进 registry（G1-d 关闭），唯一未登记的目录是 `cleanup` 清扫器
（由 workflow 直接调用，非 target）。**旗舰覆盖**：13 个旗舰 write 模块中 7 个已覆盖
（cvm_instance / vpc / subnet / cdb_instance / tke_cluster 有专属 target，落地 `6d83295`；
eip / clb_load_balancer 由 network / clb_http 场景 target 覆盖）。**剩余盲区**：redis_instance /
cos_object / scf_function / ckafka_instance / cbs_disk / nat_gateway 六个旗舰仍无任何集成覆盖，
已按 product-depth 排入 P0-04 路线图（`docs/integration-env.md` §7 R1-R6）。

> ✅ **G1-d 已关闭（2026-09-14）**：`cvm_image` 与 `lighthouse` 两个 target 有完整
> meta/tasks/vars，但既不进 `coverage.yml` registry 也不进 workflow 默认清单 —— 它们永远
> 不会被跑，且没有任何检查会发现（`validate_registry` 只走 registry → 目录，反方向没人管）。
> 两处都已修：两个 target 以 `cost: high` 补进 registry（仍在默认清单外，两者都建计费资源），
> 并给 `scripts/integration_impact.py` 加了 `validate_target_dirs()` —— 反向校验
> 「目录 vs registry」，未登记的 target 目录直接让 `--check` 失败（`cleanup` 清扫器是唯一
> 豁免：它由 workflow 直接调用，不走 target 选择）。回归测试见
> `tests/unit/scripts/test_integration_impact.py`。

> ⚠️ 逻辑修正（2026-09-02）：roadmap #57 是**单元测试覆盖驱动**（针对 write 模块
> 语句覆盖率，已由 G1b 承接），**不是**集成测试驱动，不能记在 G1 名下。G1 需要
> 单独的集成计划。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G1-a | 为旗舰 write 模块建集成 target 骨架（复用 amazon `tests/integration/targets/` 布局；执行环境策略定为真实腾讯云账号 + 计费护栏） | 无 | 2026-09-16 | ✅ P0-01/02（`6d83295`，2026-09-09：cvm_instance / vpc / subnet / cdb_instance / tke_cluster） |
| G1-b | 定义集成测试的可信执行环境（真实腾讯云账号 + 凭据注入 + 资源清理防线 + 失败告警） | G1-a | 随首批 | ✅ P0-03（`docs/integration-env.md` 落盘 + workflow 凭据接线/告警步，2026-09-09） |
| G1-c | 目标：集成 target 26 → 30+（13 旗舰已覆盖 7 个：5 专属 + 2 场景；余 6 个按 product-depth 优先补） | G1-a/b | 2026-10 | 🔄 P0-04（R1-R9；数量里程碑已过：09-14 实测 **34 dirs / 33 进 registry**（G1-d 补入 cvm_image / lighthouse 后），但默认清单仍 21 个，billed target 需人工 dispatch） |

**验收**：cvm_instance / vpc / subnet / cdb_instance / tke_cluster 已进入集成套件 ✅（2026-09-09）；
redis_instance 等其余旗舰随 P0-04 R1-R6 排入；2026-10 底前集成 target ≥ 30 且全部绿
（R1-R9 里程碑与验收口径见 `docs/integration-env.md` §7）。

## G1b 单元测试广度（write 面）— ✅ 80% 里程碑达成（收口持续）

**现状**（2026-09-15 全量重测）：整体语句覆盖率 **92.65%**（CI 口径
`tests/contract` + `tests/unit/plugins/module_utils` + `tests/unit/plugins/modules`
共 13,654 条：13,601 passed / 31 skipped / 22 xfailed，`--cov-fail-under=80` 通过）。
模块级单测 1,068 个文件 / 10,674 个测试函数。
**write 面无专属单测模块已归零**：456 / 456 全部有专属单测文件
（`test_<module>_main.py` 约定），从 222（/313，2026-08-31 基线）→ 111（/440，2026-09-08）
→ **0（/456，2026-09-14）**。
历史基线（2026-08-31）：语句覆盖率 ~60.9%（gate 55）；09-08 80% 冲刺达 81.44%，
09-09 随 P0-05/06 续升至 82%，09-14 重测为 92.65%。
**广度缺口已完全闭合**：435 个 `_info` 曾有 36 个（8%）没有专属单测文件，2026-09-14 由生成器扩展补齐；现 **write 456 / 456 与 info 549 / 549 全部有专属单测文件**。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G1b-a | 先实现 `--module-test` 骨架生成器（coverage-batching.md lever 1） | 无 | 下一批前 | ✅ 已落地 `scripts/generate_module_test_skeleton.py` |
| G1b-b | 继续按 per-file miss 报告从高到低逐模块写测试（主路径单测 + 分支补漏） | G1b-a 可并行，不阻塞 | 持续 | ✅ write 面已归零（456/456）；info 侧 36 个缺口已同步归零（535/535） |
| G1b-c | 每批 commit + CI 全绿（sanity 矩阵 + coverage gate 不破，现 80） | G1b-b | 随批 | 🔄（实测 92.65%，余 12.65 点） |

**验收**：整体实测覆盖率 ≥ 80% 且 gate 抬至 80（✅ 2026-09-08 达成 81.44%，09-09 随 P0-05 续升至 81.64%、随 P0-06 升至 82%，
09-14 重测 92.65%）；write 面与 info 面无专属单测模块均已收口到 0。

## G2 生态信任 — ⏸ 半被动（inclusion #89 评审中）

**现状**：inclusion 申请已提交（discussion #89，2026-09-02），自查评论已贴（discussioncomment-18250641），仓库已发布至 **v1.4.0（2026-09-14）**，release 全链路（tag → build → GitHub release → Galaxy publish）已自动化。Galaxy 累计下载 553（09-14 实拉）。**评审者已于 2026-09-15 首次回复**
（steering committee 的 Andersson007：已收到申请，待委员会有人接手）——这是
「有人理了」的信号，但还不是正式 review，G2-b 的 24h 响应窗口由此开启。
**已于当日 11:40 UTC 响应**（[discussioncomment-18448852](https://github.com/ansible-collections/ansible-inclusion/discussions/89#discussioncomment-18448852)，
5 小时内）：自查评论写于 1.0.0 时期，其中「3000+ 单测」已滞后近 4 倍，而那正是
未来评审者会先读到的一条——响应顺手把它订正为实测值，并说明 release 全链路已
自动化（checklist 从此每次 release 重验，而非提交时验一次）。

**G2-a 已交付（09-15）：评审 #87 openvswitch.openvswitch**

选它的理由不是随机：队列里 #88（cisco.catalystcenter）与 #87 都在 "First review in progress"，
但 **#87 自 Andersson007 2026-08-19 贴出 checklist 后 4 周无 maintainer 回应** —— 一个评审挂 4 周
没人接，正是本库 roadmap 把「没人理」当结构性风险的同一件事，而且它 6 条 MUST FIX 全部可机械核验。

做法不是复述 checklist，而是把每条拿去对 `main` @ `3b979e2`（2026-09-10，tag 2.2.2）**重测**：

| MUST FIX（2026-08-19 checklist） | 09-15 实测 |
|---|---|
| 加 `attributes:` | 4/4 模块都没有 |
| 选项级 `version_added`（原只点名 `database_socket`、`set`） | **38/38 全缺**，checklist 只点了 2 个 |
| `openvswitch_bond` 的 `version_added` 写错 | 仍写 1.0.0；changelog 1.1.0（PR #58）才是真正的加入版本 |
| 用语义标记 | `O(`/`V(`/`C(`/`M(` 计数为 **0**；`I(` 出现 8 次且基本都该是 `O(`/`V(` |
| 不得用 `state: read` 查信息 | 仍在 choices + 3 个示例 + 2 段 RETURN + `main()` 分支 |
| `datbase` 拼写 | 4 个模块各 1 处 |
| 描述句末句号 | 另有 **28 处**缺（bond 10 / bridge 7 / db 4 / port 7） |

另附一条**评审之后才出现**的新证据：`2.2.1` 在 **patch 版本**里带 `breaking_changes`（"Minimum
required ansible-core version is now 2.16"），且 `release_date` 为空 —— 正是 checklist 标
「MUST FIX in future」的 semver 问题在继续发生。2 个在途 PR（#149 / #150）均未触及上述任何一项。

结尾主动提出：机械四项（选项 `version_added` / bond 版本 / 拼写 / 句号）我可直接提 PR，让
maintainer 只花时间在需要设计判断的两项（`attributes:` 取值与 `openvswitch_db_info` 拆分）上。
**是否提 PR 取决于对方回应** —— 已按外部动作规则先问后动，未擅自改他人代码。

**建议动作**：
| 步骤 | 动作 | 依赖 | 截止 | 状态 |
|---|---|---|---|---|
| G2-a | 按官方流程评审 1 个排队中的他人 collection（README step 1：先评审别人可提升自身优先级） | 官方 README 排队清单 | 2026-09-09 → **逾期 6 天，09-15 已交付** | ✅ 目标 #87 openvswitch.openvswitch（[discussioncomment-18449321](https://github.com/ansible-collections/ansible-inclusion/discussions/87#discussioncomment-18449321)），7 项实测结论见下 |
| G2-b | 每周五检查 #89 是否有评审反馈并回复 | 无 | 每周 | ✅ 本周（09-15 收到首条回复，5h 内已响应；下周五复检） |
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

## 执行清单（2026-09-14 刷新）

> 全景图 30 件事（`docs/panorama.html`）已获批准执行 **P0×12 + P1×10**（本清单
> G1/G1b 相关项已并入对应 P0 编号；G2/G3/G4 映射的 P2 项仍在待批状态）。
> 状态图例：✅ 已完成 · 🔄 在途 · ⏸ 排队/等待外部 · 📋 待启动/待批准。

1. G1-a 集成 target 骨架 → **P0-01/02** ✅（cvm_instance/vpc/subnet/cdb_instance/tke_cluster 落地
   `6d83295`，2026-09-09；执行环境策略：真实腾讯云账号 + 计费护栏 + 三道清理防线）
2. G1-b/c 可信执行环境 + 30+ 路线图 → **P0-03/04** 🔄（`docs/integration-env.md` 已落盘 + workflow
   凭据接线/失败告警；**数量里程碑已过**（09-14：34 dirs / 33 进 registry），但默认清单仍 21 个；
   下一次带凭据的定时跑 2026-09-19 是「可信执行环境」的真正验收点）
3. G1b-a 单测骨架生成器 → **P0-08** ✅（`scripts/generate_module_test_skeleton.py` 已落地）
4. G1b-b 继续 batch 12 → **P0-07** ✅（write 面 111 → **0**；info 面 36 → **0**）
5. G2-a 评审 1 个他人 collection → **P2-01** ✅（09-15 交付：#87 openvswitch.openvswitch，
   7 项实测 + 1 项评审后才出现的新证据；选它的理由见下）
6. G3-b + G4-c capability-map.html 差距卡措辞修正 → ✅（已随 09-08 数据同步合入，09-14 再同步数量）
7. G4-a CONTRIBUTING.md 补 co-maintainer 路径 → **P2-03** 📋（2026-09-30 前，低优先级）
8. **G1-d（09-14 新增）** 孤儿 target 收口 → ✅（两个 target 以 `cost: high` 补进 `coverage.yml`
    registry；`scripts/integration_impact.py` 新增 `validate_target_dirs()` 反向校验并已进 CI 的
    「Integration coverage registry is valid」步骤；9 条回归测试全绿）
 9. **G1-e（09-14 新增）** info 侧单测广度收口 → ✅（`scripts/generate_info_modules.py` 新增
    `none` 与 `token` 两套测试模板，`SPECS` 之外的 7 个模块由骨架生成器补齐；**549 / 549 个
    `_info` 全部有专属单测文件**，模块与测试共用 `_token_termination()` 终结表达式以免漂移；
    4 条生成器回归测试锁定该契约。CI 口径 12,828 → 12,961，覆盖 92.58% → 92.65%）
 10. **G1-f（09-14 新增）** `meta/extensions.yml` 有了反向校验 → ✅（该文件 09-09 落地并随
    v1.4.0 发布，但 panorama 一直写「仍缺」—— 手工元数据无人校验，声明与产物可以长期不一致，
    与 G1-d 的孤儿 target 同一类缺陷。新增 `scripts/check_extensions_metadata.py --check`
    并已进 CI：声明 → 磁盘（目录存在、集合内相对路径、有 .py）与磁盘 → 声明（非 core 插件
    类型、非 module_utils / plugin_utils 的目录必须声明）双向校验；24 条单测，3 次变异均被
    捕获后按 sha256 逐字节还原）
 11. **G1-g（09-14 新增）** event_source 的示例与文档不再无人校验 → ✅（ansible-core 不加载
    `plugins/event_source`，`ansible-doc` 与任何 sanity test 都看不到它，所以 4 个插件的示例可以
    长期与代码不一致且无人发现 —— 实际已经发生了两处：cls 示例写 `event.level` 而源码把整条日志
    嵌在 `cls` 键下，cmq 示例写 `event.cmq.MsgBody` 而源码发的是 `msg_body`，两条规则在真实
    rulebook 里永远匹配不到。已给 4 个插件补齐 EXAMPLES 块与载荷字段文档（DOCUMENTATION 用
    `I(event.<key>.<field>)` 声明可匹配字段），并新增
    `tests/unit/plugins/event_source/test_examples.py`（11 例）双向校验：示例/模块 docstring 用到
    的字段 ⊆ 文档承诺的字段 ⊆ 源码与其单测里实测出现的字段。6 次变异全部被捕获后按 sha256
    逐字节还原；含防空断言（找不到插件、找不到 payload key、文档未声明任何字段都会失败）——
    第一版就因为 `parents[3]` 算错层级而整体空转，三个「变异」全过）
 12. **G1-h（09-14 新增）** panorama 的头版数字改为实测 → ✅（benchmark 页上的
    模块 / 产品 / role / 单测文件 / 集成 target / sanity ignore / 插件类型计数全是手抄的，
    已经错两处：单测文件写 1,014（新增两个 guard 后实为 1,016/1,017），plugin_utils 写 6
     （按 module_utils 16 的同款口径 —— 不计 `__init__.py` —— 实为 5）。新增
     `scripts/check_doc_figures.py --check` 并已进 CI：24 个数字全部从磁盘重算，再要求在
     `docs/panorama.html` 里存在「数字 + 定位关键词同行」的一行，数字被改掉或整段删掉都会失败；
     18 条单测，含真实仓库锚点（`validate(measure(ROOT), panorama) == []`）与自反性校验
     （新增任一单测文件会让该数字变化 —— 已按 1,018 改正）。数字按**整体数值**比对而非子串：
     `55` 会出现在 `1557` 与 `553` 里，子串匹配曾让「读面缺口波及 55 产品」在页面根本没写
     这个数时依然通过 —— 该 vacuity 由 `test_validate_matches_whole_numbers_only` 守住
  13. **G1-i（09-14 新增）** 读面 backlog 的统计口径 → ✅（`scripts/gap_backlog.py`
     用「双引号正则」去抓 `KNOWN_GAPS`，而该 set 是单引号写的 —— 于是 128 条 curated
     backlog 全被报成 UNTRACKED（0 in KNOWN_GAPS）；且它只按「有没有同名 `_info`」计数，
     把「已经映射到别的 _info」「根本没有列表 API」「真待补」三种情况混为一谈，对外报 226/59。
     现在改为**直接 import** `audit_info_coverage` 复用它的判定，产品分组也换成本库自己的
     inventory（旧口径把 `api_gateway_*` 与 `apigateway_*` 拆成两个产品）。实测拆分：
     456 write = 330 有同名 _info + 43 已映射 + 55 无列表 API + **28 真 backlog（18 产品）**。
     `check_doc_figures.py` 新增 4 条 claim 钉住这四个数。连带修正：panorama / capability-map /
     roadmap 里「tse 27 / cos 14 是大户」是错的 —— 两者 backlog 实为 **0**，真正的大户是
     apigateway 8 / ckafka 6 / trabbit 6 / cfw 5 / dts 5。10 条单测，6 个变异全被捕获）

---

_本计划由 docs/capability-map.html / docs/panorama.html INDUSTRY BENCHMARK 区块派生 · 2026-09-02 初版 · 2026-09-08 随 P0-12 刷新至 781 模块 / 204 产品 / gate 80 口径 · 2026-09-09 随 P0-05 刷新覆盖率至 81.64%、随 P0-06 至 82% · **2026-09-14 随 v1.4.0 全量重测至 891 模块（456 write + 435 _info）/ 204 产品 / gate 80 实测 92.65% / 34 targets（104 yml）/ write 与 info 无专属单测均 0 / 读面缺口 226（55 产品，其中 backlog 128 / 45 产品）** · 数据均为源码实测 + Galaxy 产物实拉_
  14. **G1-j（09-14 新增）** panorama 30 件事的「已达成」徽章不再无人校验 → ✅
     （`docs/panorama.html` 的优先级表每行挂一个手写的 `chip done`，没有任何东西校验它 ——
     于是它**双向**腐烂：既可能挂着 done 而验收从没满足，也可能工作早就落地却一直没标。
     09-14 实测后一种更严重：**10 项（P0-03 / P0-09 / P0-10 / P0-11 / P0-12 / P1-07 /
     P1-09 / P1-10 / P2-03 / P2-08 的稿件部分）按它们自己写下的验收口径全部通过，表格却
     仍列为未完成**，文档因此持续对外宣称一批并不存在的缺口。
     新增 `scripts/check_roadmap_status.py`：12 项可机械度量的验收逐个从磁盘实测
     （module 测试文件 <80 行归零 = 0 / 68 role × 6 断言族 / 456 write 契约覆盖
     442 实跑 + 14 书面豁免 / 1005 FQCN 索引零缺失 / 16 个 module_utils helper 全部入档 /
     三份伴生文档都写出当前模块数 / triage 工作流存在且 SLA 成文 / demo 页存在且被 README 链接 /
     14 个发布版本全部进 porting 版本映射表），再与徽章做**双向**比对 —— 标 done 但验收不过、
     或验收过了却没标，两边都失败。P0-05/06（读面收口）与 P2-01/02/08（外部动作）不伪造成
     可度量，而是明确列为 not mechanically measurable —— **即便 P2-01 已于 09-15 交付，
     它仍不在 CRITERIA 里**：评审是否「实质」无法从磁盘测出，硬造一个可过的判据只会让徽章
     为错误的原因变绿。
     顺带把 3 个**真**缺口补上：`.github/workflows/triage.yml`（open/reopen 打 `triage`，
     首个真人评论或 review 自动摘除，机器人不算，每日 07:23 UTC 跑 SLA 扫描 —— 从不 checkout
     PR 代码）、`docs/porting.md` §10 版本映射（14 个发布版本逐个入表 + 3 个需要动手的版本的
     升级说明）、`docs/demo.html`（把 06_full_chain.yml 拆成 4 步的可执行演示，已链入 README）。
     `docs/triage.md` 里「None of this is automated yet」这句旧断言已同步改写。
     24 条单测，含真实仓库锚点与 6 个合成失败路径（浅测试 / 陈旧数字 / 缺告警章节 /
     版本未映射 / demo 页缺失或未链接），**8 个变异全部被捕获**）
  15. **G1-k（09-14 新增）** 策展读面目标表不再无人校验 → ✅（P0-05 / P0-06 的收口靠
     `scripts/info_specs_targets.py` —— 一张手写的「write 模块 → SDK 读接口」表，100 条。
     `discover_info_specs.py` 对每个 SDK 产品只保留评分最高的一个 action，多资源产品因此
     被系统性欠覆盖：apigateway / ckafka / trabbit 各自拥有多个列表接口，此前三家加起来
     只落了一个 `_info` 模块。这张表补上了缺口，但它**本身就是典型的会静默腐烂的手写索引**：
     一条 entry 可能指向已改名的 write 模块、已被 SDK 下线的 action，或被生成器拒收的
     spec —— 三种情况的后果完全一样：目标从缺口报表里悄悄消失，没有任何东西失败。
     新增 `scripts/check_info_targets.py` 做**双向**校验：声明侧 → 磁盘（write 模块存在、
     `<name>_info` 已生成、单测已生成、target 不得以 `_info` 结尾、mapping 必须有非空
     action）；spec 侧 → 声明（`info_specs_auto.py` 里带 `TARGET_VERSION_ADDED` 标记的
     spec 集合必须**恰好等于** target 集合，于是「action 解析不出来」会在这里炸掉，而不是
     让读面悄悄缩水）。14 条单测，含空表反空转、真实仓库锚点与 target 数 ≥ 50 的反空转，
     **10 个变异全部被捕获**。
     结果：backlog **128 → 28**、backlog 产品 **45 → 18**、读面缺口 **226 → 126**、
     `_info` 模块 **435 → 535**、模块总数 **891 → 991**；apigateway / ckafka / trabbit
     三个大户全部归零。生成器顺带修掉三处真实缺陷：`_join_args` / `_join_kwargs` 折行
     （100 个新模块/测试原本有 20 处超过 160 列）、`offset`/`limit` 与请求自带 Offset/Limit
     撞名导致的 `Duplicate parameter`（`tke_cls_log_config_info`）、以及
     `pagination_type == "list"` 且带 ids 时漏传 ids 参数（`goosefs_fileset_info`）。
     100 个新模块与 100 个新测试零改动任何既有文件；`scripts/check_info_targets.py`
     已挂进 CI 的 ruff 之前）
     100 个模块首次进 sanity 时又暴露出**三条生成器规则缺失**（原始统计：60 处 pep8 E128、
     34 处 `parameter-list-no-elements`、7 处 `no-log-needed`）：
     ① 生成的续行用固定 8 空格缩进，ruff 只查 E501 放过了，但 `ansible-test sanity` 跑
     完整 pep8，E128 要求续行对齐**视觉缩进**（开括号后那一列）—— 改成按
     `len(<call head>)` 计算衬垫；
     ② `type: list` 的 `extra_params` 没带 `elements`（新增 `_EXTRA_ELEMENTS`）；
     ③ `no_log` 判定过于粗糙：`next_token` / `page_token` 是模块自己走的分页游标，不该
     暴露成选项（并入 `_RESERVED`）；而 `keyword` / `search_key` / `client_token` 只是
     *名字像*凭据，必须显式写 `no_log: False`，反之 `password` / `secret` / `credential` /
     `private_key` 是真的凭据，必须写 `no_log: True`（ES `DescribeIndexList` 的 Password
     就是活例子）。注意 **`no_log` 不是合法的 DOCUMENTATION key**，只属于 argument_spec——
     写进文档会被 validate-modules 判 `extra keys not allowed`。
     这三条规则此前**没有任何测试**，只有在有人重新生成模块时才会炸，因此新增
     `tests/unit/scripts/test_discover_info_specs.py`（23 条，含真实 spec 反空转与
     「生成文档不得出现 no_log」），**6 个变异全部被捕获**。
     另外修掉一个潜伏的 CI 自伤：`ruff check .` 会在工作副本里留下 `.ruff_cache/`，而紧随
     其后的 `ansible-test sanity` 会扫描**全部文件**，把缓存二进制判成 CRLF 和非 UTF-8
     （实测 13 处 line-endings + 577 处 no-smart-quotes）。CI 改为 `ruff check . --no-cache`，
     `.ruff_cache/` 同时加入 `.gitignore`。）
  16. **G1-l（09-15 新增）** 读面 backlog 收干到 0，且空表不再等于「没人检查」 → ✅
     （G1-k 把 backlog 从 128 压到 **28**，剩下的 28 个跨 18 个产品，逐个查过 SDK 后
     分三类处置：**13 个**确实有可用列表接口 —— 补进 `scripts/info_specs_targets.py`
     策展表后由生成器直接产出 `_info`（`cdwch_backup_config` / `cdwch_parameter` /
     `cdwpg_parameter` / `cfw_internet_acl_rule` / `cfw_nat_acl_rule` /
     `cfw_vpc_acl_rule` / `cmq_subscription` / `dcdb_security_config` /
     `elasticsearch_snapshot` / `emr_cluster` / `tem_application_deployment` /
     `tione_model_service_state` / `tione_model_service_traffic`）；**14 个**本来就
     能被某个既有 `_info` 读到，只是没人登记 —— 逐个比对该 `_info` 的响应模型后写进
     `KNOWN_COVERAGE`（例：`tke_cluster_deletion_protection` 读的是
     `tke.Cluster.DeletionProtection`、`clb_snat_ip` 读的是 `clb.LoadBalancer.SnatIps`、
     `gwlb_target_group_association` 读的是 `gwlb.GatewayLoadBalancer.TargetGroupId`）；
     **1 个**（`gaap_layer4_listener`）无法用生成器表达 —— GAAP 把四层监听的列表接口
     拆成 `DescribeTCPListeners` / `DescribeUDPListeners` 两个 sibling action，请求与
     响应形状完全相同，而生成器是「一个 write 模块对一个 action」，因此手写
     `gaap_layer4_listener_info` 依次查两个协议并给每条记录打上 `protocol` 标记
     （API 不返回协议字段）。映射一律先读 SDK 响应模型再落笔：`KNOWN_COVERAGE` 的
     docstring 里那句「a wrong mapping is worse than an honest gap」是硬约束，
     宁可留着缺口也不造不存在的读面。
     结果：backlog **28 → 0**、backlog 产品 **18 → 0**、读面缺口 **126 → 112**
     （57 已映射 + 55 无列表 API）、`_info` **535 → 549**、模块总数 **991 → 1005**
     —— P0-05 的验收口径是 backlog 128 → ~60、P0-06 是 backlog 产品 45 → <25，两项
     均已完成而非接近。
     但 **backlog 归零恰恰是最危险的状态**：空桶和「永远填不进去的桶」长得一模一样，
     原来那条反空转断言 `assert data["counts"]["backlog"] > 0` 会当场失守。
     因此 `tests/unit/scripts/test_gap_backlog.py` 把反空转**从真实仓库搬到合成用例**：
     `test_a_module_with_no_excuse_still_lands_in_backlog` 摘掉一个「无列表 API」豁免、
     把它改判为 gap，要求工具必须把它报进 backlog；真实仓库只负责保证另外两个桶
     非空。`KNOWN_GAPS` 现为空集，并在源码里写明它不是停车场——新 write 模块必须
     落地即被 `KNOWN_COVERAGE` 覆盖，否则
     `scripts/audit_info_coverage.py --check` 立刻失败。**4 个变异全部被捕获**
     （改 `backlog:` 前缀 / 删掉 `KNOWN_GAPS` 分支 / 把 `KNOWN_NO_LIST_API` 的判定
     换成 `KNOWN_GAPS` / 往 `KNOWN_GAPS` 塞回一个陈旧条目）。
     顺带修掉两处长期失校：① 上述两张表的说明文字是隐式字符串拼接，约 40 处丢空格
     （`whichis` / `thewritemodule` / `bucket,whichis`）与 130+ 处拼接点缺空格，
     已按「只插入空格、不改任何字符」逐条修好并用去空白比对证明零语义变化；
     ② `tests/unit/scripts/test_check_doc_figures.py` 里硬编码的 `1,121 个` 锚点
     每次新增测试文件都会失效，且失效方式是**静默通过**（replace 没匹配上，于是断言的
     「应当报出 1 个问题」变成 0 个问题也算过）—— 改为从实测数字推导锚点，
     并在锚点消失时直接报错而不是静默放行；
     ③ 测试函数个数是同一类失校——`docs/panorama.html` 与
     `docs/capability-map.html` 都声称引用该数字，却一处写 10,826、一处写
     10,869，且两者在页面自己声明的口径（模块级 `test_*.py` 里行首
     `def test_`）下都复现不出来（实测 **10,674**）。根因与 ① ② 相同：**只要
     数字是手写的，就一定会被下一次提交甩在后面**。因此把该数字收进
     `scripts/check_doc_figures.py`（第 25 项），由脚本按页面自述口径实测；
     CI 条数同理按 `.github/workflows/ci.yml` 的 coverage 口径
     （`tests/contract` + `tests/unit/plugins/module_utils` +
     `tests/unit/plugins/modules`）重测为 **13,654 条（13,601 过 / 31 跳 /
     22 xfail）**，并把复测命令写进页面，替换掉原先 12,961 / 14,290 两个
     互相打架的历史值。）
  17. **G1-m（09-15 新增）** 每周真实账号跑的默认清单不再无人校验 → ✅
     （P0-04 剩下的一半。`docs/integration-env.md` 里**写着**规则——free/low
     进默认清单、medium/high 保持 opt-in——但「写下规则」不等于执行：清单实
     测 **21 个**，里面混着 **2 个 `cost: medium`**（`cfs_file_system` /
     `clb_http`），与文档自述的规则直接冲突。更根本的问题是这份清单在
     `.github/workflows/integration.yml` 里被**手打了两遍**（`workflow_dispatch`
     的 `default:` 与 `inputs.targets || '...'` 的兜底），改其中一遍是一次
     完整、静默、成功的编辑——而这是本仓库唯一会碰真实云账号的东西。
     新增 `scripts/check_integration_defaults.py --check`，把规则变成代码，
     并接进 `ci.yml`（在 ruff 之前）：两遍清单必须一致；不得重复；每个目标
     必须在 `coverage.yml` 里登记（否则周跑是「未知目标报错」而不是跳过）；
     `high` 永不进清单；`medium` 只有在 `VETTED_MEDIUM` 里写明理由才允许
     ——理由会打在 `--check` 的输出里，评审者看到的是依据而不是名字；反向
     同样校验：`free`/`low` 漏出清单即失败，因为**没人跑的目标正是 registry
     声称有、实际没有的覆盖**。两个 medium 目标的理由都是「provision 一个
     资源加其 VPC/子网，并在 `always:` 块里三者一起拆掉，不留长期计费资源」。
     `tests/unit/scripts/test_check_integration_defaults.py` 共 **22 个用例**，
     含反空转（默认清单 >10 个、opt-in 集合非空、每个 cost 档都有样本）与
     双向驱动（不该跑的被抓 / 该跑却没跑的也被抓），外加合成失败路径
     ——high 混入、未登记目标、重复、两遍不一致、工作流改结构导致正则失效、
     清单被清空、`VETTED_MEDIUM` 自身腐烂（指到不存在的目标 / 目标 cost 已
     经不是 medium / 已不再被 dispatch）、以及 empty 分支失效。
     变异测试 **10/10 被杀死**（逐条关掉 9 条判定规则 + 把正则改回 `+`），
     **9/9 个工作流变异都以正确的规则名报错**（而不是被「两遍不一致」这条
     兜底捕获——第一版变异只改了一遍，8 个里有 5 个是被兜底捞住的，那不是
     证据）。过程中修掉脚本自身一个死角：正则原为 `+`，清单被清空时匹配
     不上，于是报「找不到两遍清单」——把人引向改正则而不是恢复目标；改为
     `*` 后空的归空的、解析不了的归解析不了的。
     顺带收掉两处残留失校：`docs/integration-env.md` 三处规则表述改为指向
     新脚本（§3 计费护栏、§6 runbook、新增目标清单），不再由文档复述规则；
     `docs/panorama.html` P2-04 那句「下一节奏点是 changelog fragment 的积累
     （当前目录为空）」已与仓库不符（fragment 已随 PR 逐条积累），改为陈述
     机制而非计数——`fragment` 一词在页面别处与 `doc_fragments` 的实测数字同行，
     硬塞一个新数字进 `check_doc_figures.py` 会与既有断言打架。）
 18. **G1-n（09-15 新增）** event_source 的 docsite 页不再是 0，且整条可达链
     都有人校验 → ✅（G1-g 给 4 个 event_source 插件补齐了 EXAMPLES 与载荷字段
     文档，但它们的 docsite 页始终是 **0 页** —— `plugins/event_source` 是
     ansible-core 与 antsibull-docs 都不加载的扩展类型，`ansible-doc` 看不到、
     sanity 测不到、antsibull-docs 也不会为它生成页面。于是 panorama P1-08 长期
     写着「docsite 入口待评估（需手写或生成 RST）」，而手写 RST 恰恰是本仓库反复
     出事的那类东西：它可能被下一次构建悄悄删掉，也可能永远不进任何 toctree，两种
     情况都不会有任何东西失败。
     因此做成**生成器 + 双向接线校验**而不是一份手写文档：
     `scripts/generate_event_source_docs.py` 从 4 个插件的 DOCUMENTATION /
     EXAMPLES 渲染 `docs/docsite/extra_rst/event_source_plugins.rst`（4 插件 /
     39 选项 / 12 个可匹配字段），`--check` 同时校验 ① 页面与 `render()` 逐字节
     一致 ② 插件 ↔ 章节双向（有插件没章节、有章节没插件都失败）③ 每个插件都声明
     了 `I(event.*)` 载荷字段与 EXAMPLES ④ **接线**：`build.sh` 必须把
     `extra_rst/` 拷进 `rst/`，且 `rst/index.rst` 的 toctree 里必须有
     `event_source_plugins`。页面放在 `extra_rst/` 而非 `rst/`，是因为
     `--cleanup similar-files-and-dirs` 会删掉 antsibull-docs 没写过的文件与目录；
     拷贝发生在 antsibull-docs 之后，任何 cleanup 模式都动不了它。
     33 条单测（真实仓库锚点：4 个插件逐个点名、每插件 ≥8 选项、载荷字段逐个匹配
     `event.<key>.<field>`、真实页面可复现），**12/12 变异全部被捕获**（逐个关掉
     9 条判定 + 改锚点正则 + 删拷页步骤 + 删 toctree 条目），脚本按 sha256 逐字节
     还原；已进 `ci.yml`（ruff 之前，「Event source docsite page」步骤）。
     顺带收掉四处残留失校，全是「没有守卫盯着的手写数字/断言」：
     ① `docs/docsite/README.md` 的 875 模块 / ~900 页 / 八分钟 —— 实测
     **1005 模块 / 1032 页 / 冷构建 77s（antsibull）+ 221s（Sphinx）**；
     ② 同一份 README 的「Everything else under rst/ and build/ is generated and
     ignored」与「build/ is git-ignored」**都是假的** —— `build/html` 有 1101 个
     入库文件，只有 `/build/doctrees`、`/rst/collections` 与顶层 `/rst/*.rst`
     被忽略（后者本次补进 `.gitignore`：`/rst/*.rst` + `!/rst/index.rst`）；
     smart quotes 那节还把已被 `conf.py` 的 `smartquotes = False` 修掉的问题写成
     仍在进行时（实测生成 HTML 里弯引号 **0** 个）；
     ③ `docs/roadmap.md` P1-04 同款的 875 / ~900 页；`docs/panorama.html` 与
     `docs/demo.html` 的 991 模块（实测 1005，且 1005 个模块确实全部声明
     `supports_check_mode=True`）；
     ④ panorama P1-04「随每次 release 重建」—— **没有任何工作流碰 docsite**，
     已改为「随插件变更手工重建（无自动重建工作流）」并写明 09-15 起的守卫。
     `check_doc_figures.py --check` 当场抓到一处新漂移：新增的测试文件让「单测文件」
     从 1,135 变 **1,137**，panorama 已同步 —— 这正是 G1-h 该有的样子。）
