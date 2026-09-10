# 维护一个 875 模块的腾讯云 Ansible 集合：一个月里可复用的经验

> 结论先行：集合大到跑不了、又不能被 CI 跑的时候，能救命的不是更多测试，而是一层"不执行也能查"的静态门禁。本文把这套做法和踩过的坑写成可复用经验，给后续接手或做同类集合的人。

## 背景

`susunola.tencentcloud` 是一个面向腾讯云的 Ansible 集合：875 个插件（440 个写模块 + 435 个 `_info` 只读模块）、68 个 role、从官方 SDK 自动生成。问题不在"写不出模块"，而在"模块一多，引用关系就管不住"——文档、示例 playbook、移植指南里写死的模块名、选项名、role 变量，任何一次重命名都会让它们静默失效，而 CI 全绿。

一个月里我们没有去堆更多模块，而是把"引用一致性"和"文档可校验"做成了基础设施。下面是用真金白银换来的几条经验。

## 1. 不能跑 ≠ 不能查：用静态门禁代替执行

CI 不能跑示例 playbook——跑了就创建计费资源。但"不能执行"不该等于"不能验证"。两类检查在 sub-second 内给出结论：

- `ansible-playbook --syntax-check`：证明 Ansible 认得这份 playbook（变量嵌套、block 结构合法）。它**不**证明模块名存在。
- 自写的引用检查器：解析 YAML/Markdown，断言"出现的每一个名字都真实存在"——模块解析到 `plugins/modules/<name>.py`，role 存在且 `defaults/main.yml` 声明了它读的每个变量，选项落在模块的 `argument_spec` 或 doc_fragment 里。

两种检查互补：语法检查证明结构对，引用检查证明名字没过期。第一次跑 `scripts/check_examples.py` 就抓到三处腐烂：`three_tier_web.yml` 传了未声明的 `web_instance_password`；两个示例在末尾打印 role 从没 set 过的 fact（直接 `VARIABLE IS NOT DEFINED!`）；五个 role 读了自己没声明的 region 变量，靠 `default(omit)` 侥幸过关，变量因此从 role 的公开接口里消失。全修。

**可复用点**：任何"跑不了但要保真"的产物（示例、教程、配置模板），都配一个静态引用检查器，CI 里 `--check` 失败即红。

## 2. 文档里的名字也要进 CI：映射表自检

`docs/porting.md` 是一张"Terraform 资源 → 模块 FQCN"的对照表，共 30 个模块名。表是手写的，重命名一个模块就让它过期——而且过期时**没有任何测试会报错**。

做法：`scripts/check_porting_map.py` 把 Markdown 表格当数据读出来，断言第二列的每一个模块都解析到真实文件。判别规则要够紧：只认"首列是真实 `tencentcloud_<词>` 资源、次列是单个反引号包住的模块名"的行，避免把正文里的 `loop`/`region`/`TENCENTCLOUD_SHARED_CREDENTIALS_DIR` 误判成模块。校验过 30 个名字、0 误报；往表里塞一个故意拼错的 `clb_loadbalancer` 会立即 FAIL。

**可复用点**：文档里出现代码实体名时，别把它当散文。写个解析器把"名字"抽出来对仓库做存在性断言，门禁挂上。

## 3. 写文档前，先把事实从仓库里读出来

`porting.md` 上线前我逐条核对了仓库真相，结果推翻了已有文档里的两处错：

- 原 `scenarios.md` 写"region 默认 `ap-guangzhou`"——错。本集合**没有默认 region**，不传 `region`/`TENCENTCLOUD_REGION`/profile 的 `region` 就直接失败。这是移植者第一次运行最常见的失败，文档却和现实相反。
- "资源族 37 个"——实际 `lookup/resource_id.py` 的 `resource_type` 选项是 **41** 个。

还澄清了几处和 Terraform 的命名/凭证差异：`token` 变量是 `TENCENTCLOUD_TOKEN`（Terraform 用 `TENCENTCLOUD_SECURITY_TOKEN`）；profile 文件是 `~/.tencentcloud/default.configure`（Terraform 用 `~/.tccli/default.credential`）；Terraform 的 `count`/`for_each` 对应 `exact_count`，`plan` 对应 `--check`，`provisioner` 等待对应 `tc_wait` action 插件。

**可复用点**：跨工具/跨语言的对照文档，每个事实都要能指回源码或 `--help` 的具体行，不要凭记忆写。

## 4. CI 分层，快门禁挡在慢门禁前面

全量门禁（`ansible-test sanity` × 三 Python 版本、`ansible-test units`、`coverage --cov-fail-under=80`、collection build）一次要十几分钟。把能在 1 秒内的静态检查单列成"快门禁"，先跑：

- SDK 漂移哨兵（生成代码与 SDK 版本不一致直接红）
- `sync_doc_fragments` / `sync_registry` / `audit_info_coverage` / `generate_cam_actions` / `generate_product_capabilities` / `check_module_tiers` / `check_sanity_ignore` / `check_examples` / `check_porting_map` ——全部 `--check` 退出 0

快门禁挡在前面，大部分引用类回归在 10 秒内就能红，不用等十几分钟全量跑完才发现模块名拼错。

**可复用点**：静态一致性检查便宜且快，应该独立成门前关卡，而不是埋在全量测试里最后才暴露。

## 5. 沙箱与工具链的三个坑

- **pytest 的 `tmp_path` 跨 uid 冲突**：sandbox 里默认 base `/tmp/pytest-of-unknown` 可能已被别的 uid 建过，新建同名目录报 `PermissionError: EEXIST`。解：跑测试加 `--basetemp=/tmp/ptm_<时间戳>`，别动测试本身。
- **zsh 不拆未加引号的参数展开**：`$PY "script.py --check"` 整串被当成文件名 → `can't open file`。用 `eval "$PY $s"` 或 `${=s}`。
- **`ansible-test sanity` 的 pyflakes/pep8 比 ruff 更严**：一个没用到的 `import pytest` 在本地 ruff 全绿，却让 CI sanity 整条红（F401）。凡贡献测试文件，本地也跑一次 `ansible-test sanity`，别只信 ruff。

## 一个月的量化结果

- 新增并跑通两套静态门禁：`check_examples.py`、`check_porting_map.py`（各带单元回归）。
- 出版 `docs/porting.md` 移植对照手册 + `docs/scenarios.md` 区域默认修正 + `docs/examples/README.md` 全链路说明，三处互相交叉引用。
- 文档类缺陷（静默腐烂、事实错误）在合入前清零，而不是等用户踩。

## 下一步

- P2-08 之后看 #89 的 `ansible-inclusion` 社区评审进展，决定集合是否进入官方收录流程。
- 把"静态引用检查"模式沉淀成一个 skill，下次起同类集合时第一步就生成检查器，而不是事后补。

---

*本文所有模块名、选项名、仓库路径均来自 `susunola.tencentcloud` 集合本体（commit `2f383da`），可对照 `docs/porting.md`、`scripts/check_examples.py`、`scripts/check_porting_map.py` 复现。*
