# 版本更新记录

本文档记录 `skills_test` 工作区的重要版本更新。

初始基线提交：

- `a31d64b` `【add】初始化项目`

## v0.1.0 - 初始基线

日期：2026-04-01

- 初始化 `skills_test` 工作区。
- 在 `freecad_cli_tools/` 下加入 FreeCAD CLI 工具源码。
- 增加用于 YAML 驱动 FreeCAD 装配工作的启动脚本和数据目录。

## v0.2.0 - 启动方式与 Skill 工作流更新

日期：2026-04-02

- 在 [start_wsl_freecad_rpc.ps1](./scripts/start_wsl_freecad_rpc.ps1) 中加入 GUI / Headless 启动模式切换。
- 新增 WSLg GUI 启动脚本 [start_freecad_gui_wsl.sh](./scripts/start_freecad_gui_wsl.sh)。
- 更新 FreeCAD skill 的移动规则：
  - 先分析，再直接执行，不再额外等待用户确认
  - 默认更新当前 CAD / YAML，不再自动新建新的装配文件
- 将最新 FreeCAD skill 备份同步到 [freecad_skill](./skill_backups/freecad_skill)。
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
- 新增可复用基准脚本 [benchmark_yaml_safe_move.py](./scripts/benchmark_yaml_safe_move.py)。

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
