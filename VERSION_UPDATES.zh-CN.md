# 版本更新记录

本文档记录 `skills_test` 工作区的重要版本更新。

初始基线提交：

- `a31d64b` `【add】初始化项目`

## v0.9.1 - 外部安装面边界约束与文档同步

日期：2026-04-13

- 在 [geometry.py](./freecad_cli_tools/src/freecad_cli_tools/geometry.py) 中新增外部安装面的面内边界辅助逻辑，使 6-11 号外部安装面的移动即使跳过内部包络包含约束，也仍然会限制在目标墙面的二维轮廓内。
- 在 [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) 与几何分析上下文中补充 `envelope_face_id` 和 `wall_size`，让 `analyze_position()` 与 `find_best_safe_scale()` 能在外部安装面触碰边界时正确截断，并报告 `FACE_BOUNDARY`。
- 在 [test_yaml_component_safe_move.py](./freecad_cli_tools/tests/test_yaml_component_safe_move.py) 中增加回归测试，覆盖外部安装面的允许/拒绝位置、在墙面边缘处截断安全前缀，以及内部安装面继续返回 `ENVELOPE_BOUNDARY` 的行为。
- 清理了会阻塞 CI 的 Ruff / Black 问题，并同步更新工作区与包级 README，补充外部安装面移动的新约束说明。

## v0.1.0 - 初始基线

日期：2026-04-01

- 初始化 `skills_test` 工作区。
- 在 `freecad_cli_tools/` 下加入 FreeCAD CLI 工具源码。
- 增加用于 YAML 驱动 FreeCAD 装配工作的启动脚本和数据目录。

## v0.2.0 - 启动方式与 Skill 工作流更新

日期：2026-04-02

- 在现已退役的 WSL 启动链路中加入 GUI / Headless 启动模式切换。
- 在现已退役的启动链路中加入 WSLg GUI 启动路径。
- 更新 FreeCAD skill 的移动规则：
  - 先分析，再直接执行，不再额外等待用户确认
  - 默认更新当前 CAD / YAML，不再自动新建新的装配文件
- 将最新 FreeCAD skill 备份同步到 [`skill_backups/`](./skill_backups/) 下的跟踪备份目录。
- 调整 skill 备份策略，工作区只保留最新一份备份。

## v0.3.0 - 碰撞搜索与同步性能优化

日期：2026-04-03

- 将 [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) 从高密度路径采样改为基于 swept AABB 的区间分析。
- 将静态障碍物包围盒改为每次移动预计算一次，而不是在每个候选点重复计算。
- 将异常回退采样路径从类似 `2000 + 60` 的探测缩减为仅在边界场景使用的 `256 + 24`。
- 将主安全前缀搜索改为线性扫描障碍物，不再维护碎片化安全区间。
- 新增直接同步位姿的脚本 [sync_component_placement.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_scripts/sync_component_placement.py)。
- `--sync-cad` 不再要求 FreeCAD 重新读取 YAML，而是直接通过 RPC 传递最终位置和旋转。
- 在 [rpc_client.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_client.py) 与 [cli_support.py](./freecad_cli_tools/src/freecad_cli_tools/cli_support.py) 中去掉了 `execute_code` 之前多余的 `ping()` 往返，降低了每次调用延迟。

## 功能验证

日期：2026-04-03

### 装配创建

- 基于 [sample.yaml](./examples/sample.yaml) 在 `data/` 下生成运行期验证装配：
  - `OriginalSingleUnit_Verify.FCStd`
  - `CompareSingleUnit_Verify.FCStd`
- 两个文档都成功在 FreeCAD 中打开：
  - `OriginalSingleUnit_Verify`
  - `CompareSingleUnit_Verify`

### 移动流程

- 对 `CompareSingleUnit_Verify` 做了真实移动测试：
  - 组件：`P005`
  - 目标：`TOP` 面右前方
  - 输出 YAML：`data/compare_single_unit_verify.P005.top-right-front.yaml`
- 验证结果：
  - `OriginalSingleUnit_Verify` 中的 `P005` 保持原始位置 `[170.39544205001832, -32.163340202523656, -170.91101196102727]`
  - `CompareSingleUnit_Verify` 中的 `P005` 更新为 `[159.80590107668024, 53.18129340212163, 81.58361030306861]`
  - 对比文档中的旋转四元数也更新为预期值 `[0.0, -0.7071067811865475, 0.0, 0.7071067811865476]`

## 性能对比

基准场景：`P005 -> TOP 面右前方`，同一台机器、同一份 YAML、同一条 `--sync-cad` 文档更新路径（除特别说明外）。

| 场景 | 实测耗时 |
|---|---:|
| 当前算法，不同步 CAD | `0.42s` |
| 早期优化版搜索，尚未优化同步路径 | `~5.20s` |
| 直接传位姿但尚未去掉额外 RPC 往返 | `~4.80s` |
| RPC 优化后的当前版本 | `~2.76s` |
| 在 `CompareSingleUnit_Verify` 上的当前验证移动 | `~2.63s` |

总结：

- 碰撞搜索已经不再是主要瓶颈。
- 剩余主要成本集中在 FreeCAD 文档修改和 GUI 刷新。
- 相比早期约 `~5.20s` 的同步路径，当前约 `~2.76s` 的结果在该测试路径上约下降了 `47%`。

## v0.4.0 - 质量、CI 与仓库治理

日期：2026-04-03

- 为 YAML 安全移动核心新增单元测试 [test_yaml_component_safe_move.py](./freecad_cli_tools/tests/test_yaml_component_safe_move.py)。
- 在 [pyproject.toml](./freecad_cli_tools/pyproject.toml) 中补充测试路径配置。
- 新增 GitHub Actions CI [ci.yml](./.github/workflows/ci.yml)，运行 `ruff`、`black --check` 和 `pytest`。
- 在 [pyproject.toml](./freecad_cli_tools/pyproject.toml) 与 [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py) 中将版本从 `0.1.0` 升到 `0.4.0`。
- 将被跟踪的示例 YAML 从 `data/` 挪到 [examples/sample.yaml](./examples/sample.yaml)，使 `data/` 仅保留为运行期输出目录。
- 增加 Python 缓存忽略规则，并从版本控制中移除已跟踪的 `__pycache__` 产物。
- 在旧的工作区 `scripts/` 目录中新增过可复用基准脚本。

## v0.5.0 - 可复用同步模块与批量 CAD 更新

日期：2026-04-03

- 新增可复用位姿同步辅助模块 [freecad_sync.py](./freecad_cli_tools/src/freecad_cli_tools/freecad_sync.py)，让多个 CLI 命令共享统一的归一化与 RPC 脚本渲染逻辑。
- 新增批量位姿同步 CLI [sync_component_placements.py](./freecad_cli_tools/src/freecad_cli_tools/cli/sync_component_placements.py)。
- 新增 FreeCAD 端批量同步脚本 [sync_component_placements.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_scripts/sync_component_placements.py)，可在一次 RPC 调用中更新多个组件，并选择只做一次 recompute。
- 将 [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) 切换到共享批量同步路径，即使是单组件同步也复用同一套能力，减少重复实现。
- 修复 [cli_support.py](./freecad_cli_tools/src/freecad_cli_tools/cli_support.py) 中的 JSON 文件读取逻辑，使 PowerShell 生成的带 UTF-8 BOM 文件可以直接用于 `--updates-file`。
- 更新 [README.md](./freecad_cli_tools/README.md)、[pyproject.toml](./freecad_cli_tools/pyproject.toml) 和 [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py)，对外暴露并说明新的同步接口。

## v0.6.0 - 双语文档与图示补充

日期：2026-04-03

- 新增中文版更新记录 [VERSION_UPDATES.zh-CN.md](./VERSION_UPDATES.zh-CN.md)。
- 新增工作区级中英文入口文档 [README.md](./README.md) 与 [README.zh-CN.md](./README.zh-CN.md)。
- 新增系统架构与流程图文档 [ARCHITECTURE.md](./docs/ARCHITECTURE.md)。
- 明确了工作区文档、包级文档、示例数据、运行时输出和启动脚本之间的关系。

## v0.7.0 - 原地更新移动流程与 skill 备份刷新

日期：2026-04-03

- 在 [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) 中新增 `--spin`，支持在同一面上做 90 度整数倍旋转。
- 在 [test_yaml_component_safe_move.py](./freecad_cli_tools/tests/test_yaml_component_safe_move.py) 中补充同面旋转和非法旋转角度的单元测试。
- 更新 [freecad_cli_tools/README.md](./freecad_cli_tools/README.md) 和 [freecad_cli_tools/README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md)，补充原地更新 YAML 的示例和同面旋转说明。
- 更新 [README.md](./README.md)、[README.zh-CN.md](./README.zh-CN.md) 和 [ARCHITECTURE.md](./docs/ARCHITECTURE.md)，将默认移动/旋转流程明确为“覆盖源 YAML，并原地保存当前 `FCStd` 文档”。
- 刷新已跟踪的 FreeCAD skill 备份到 [skill_backups/freecad](./skill_backups/freecad)，并移除旧的 `skill_backups/freecad_skill` 路径。
- 在 [pyproject.toml](./freecad_cli_tools/pyproject.toml) 和 [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py) 中将包版本由 `0.5.0` 升到 `0.7.0`。

## v0.9.0 - 外部安装面支持

日期：2026-04-09

### 新增

- 将 `mount_face` 范围扩展至 0–11，更新 [geometry.py](./freecad_cli_tools/src/freecad_cli_tools/geometry.py)、[yaml_schema.py](./freecad_cli_tools/src/freecad_cli_tools/yaml_schema.py) 和 [rpc_script_fragments.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_script_fragments.py)。面 6–11（`ext-x`、`ext+x`、`ext-y`、`ext+y`、`ext-z`、`ext+z`）将组件安装在包络体*外部*，以 `envelope.outer_size` 为墙面参考；面 0–5 仍为内部安装面。
- 在 `geometry.py` 中新增 `is_external_face()` 和 `component_contact_face()` 辅助函数。`component_mount_face()` 现在无论 YAML 中存储的是内部还是外部安装面，始终返回物理接触面（0–5）。
- `build_analysis_context()` 增加 `check_envelope` 参数；`analyze_bounds()` 和 `find_best_safe_scale()` 在外部面移动时跳过包络边界约束，改用仅基于障碍物的碰撞检测。
- `freecad-yaml-safe-move --install-face` 现在接受 0–11。外部面从 YAML 中读取 `outer_size` 作为墙面参考，禁用内部包络约束，并将组件朝向调整为向外（接触面指向包络中心）。
- 在 [examples/sample.yaml](./examples/sample.yaml) 中新增两个外部面组件：`P021`（`mount_face: 9`，外部 +Y 面）和 `P022`（`mount_face: 9`，外部 +Y 面，与 P021 并排）。

### 更新

- 在 [pyproject.toml](./freecad_cli_tools/pyproject.toml) 和 [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py) 中将包版本由 `0.8.0` 升至 `0.9.0`。
- 刷新 FreeCAD skill 备份至 [skill_backups/freecad](./skill_backups/freecad)。
- 更新 FreeCAD skill 文档（`SKILL.md`、`guides/safe-move-workflow.md`），将 `--install-face` 范围文档更新为 `<0..11>`。
- 更新 [freecad_cli_tools/README.md](./freecad_cli_tools/README.md) 和 [freecad_cli_tools/CHANGELOG.md](./freecad_cli_tools/CHANGELOG.md)，补充外部面功能说明。

## v0.8.0 - 几何模块提取与 YAML 格式校验

日期：2026-04-08

### 重构

- 从 [yaml_component_safe_move.py](./freecad_cli_tools/src/freecad_cli_tools/cli/yaml_component_safe_move.py) 中提取全部 44 个纯几何函数和 8 个常量到新模块 [geometry.py](./freecad_cli_tools/src/freecad_cli_tools/geometry.py)。CLI 文件从 1081 行缩减到约 280 行，只保留 CLI 解析、YAML I/O、CAD 同步和主流程编排。
- 在 [rpc_script_fragments.py](./freecad_cli_tools/src/freecad_cli_tools/rpc_script_fragments.py) 中添加交叉引用注释，将每个 FreeCAD 端字符串片段函数映射到对应的 `geometry.py` 实现，并配有同步测试防止两边逻辑悄悄分歧。
- 旧的导入路径 `freecad_cli_tools.cli.yaml_component_safe_move` 通过向后兼容的 re-export 仍然可用；新代码应直接从 `freecad_cli_tools.geometry` 导入。

### 新增

- YAML 装配格式校验模块 [yaml_schema.py](./freecad_cli_tools/src/freecad_cli_tools/yaml_schema.py)，提供 `validate_assembly()` 和 `AssemblyValidationError`。在 `freecad-yaml-safe-move` 加载 YAML 后自动调用，缺少字段时给出包含组件 ID 的清晰错误信息，而非隐晦的 `KeyError`。
- 新测试 [test_yaml_schema.py](./freecad_cli_tools/tests/test_yaml_schema.py)，包含 15 个格式校验测试，覆盖盒体、圆柱、缺失字段、错误类型和边界情况。
- 新测试 [test_fragment_sync.py](./freecad_cli_tools/tests/test_fragment_sync.py)，交叉验证 `rpc_script_fragments.py` 字符串片段与 `geometry.py` 函数在常量、旋转运算、圆柱辅助函数和位置平移方面的一致性。
- 新测试 [test_rpc_script_templates.py](./freecad_cli_tools/tests/test_rpc_script_templates.py)，用虚拟占位符渲染全部 6 个 RPC 脚本模板，通过 `compile()` 验证语法正确性。
- 在包目录下新增 [CHANGELOG.md](./freecad_cli_tools/CHANGELOG.md)。

### 修复

- 将 [test_yaml_component_safe_move.py](./freecad_cli_tools/tests/test_yaml_component_safe_move.py) 中手写的 `try/except/else` 替换为 `pytest.raises`；同时修正原代码中 `AssertionError` 拼写错误。

### 更新

- 在 [pyproject.toml](./freecad_cli_tools/pyproject.toml) 和 [__init__.py](./freecad_cli_tools/src/freecad_cli_tools/__init__.py) 中将包版本由 `0.7.0` 升到 `0.8.0`。
- 更新 [README.md](./freecad_cli_tools/README.md) 和 [README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md) 的开发布局章节，补充 `geometry.py`、`yaml_schema.py` 和 `tests/` 说明。
