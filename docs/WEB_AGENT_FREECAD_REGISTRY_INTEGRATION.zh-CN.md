# Web / Agent / FreeCAD CLI Artifact Registry 接入说明

本文档整理 `open_codex_web` 与 `freecad_cli_tools` 之间关于 `session_id / thread_id / turn_id` 的透传约定，用于把 FreeCAD 产物登记到 artifact registry。

适用代码基线：

- Web 前端：`/data/lbk/codex_web/open_codex_web/frontend/src/App.tsx`
- Web 后端：`/data/lbk/codex_web/open_codex_web/backend/src/routes/task.ts`
- Session 存储：`/data/lbk/codex_web/open_codex_web/backend/sessions.json`
- FreeCAD CLI registry：`/data/lbk/freecad_skills/freecad-skill/freecad_cli_tools/src/freecad_cli_tools/artifact_registry.py`

## 1. 当前实现现状

当前链路的真实状态是：

1. 前端本地生成 `Session.id`
   代码位置：`frontend/src/App.tsx`
2. 前端只把 `prompt / threadId / enabledSkills` 发送到 `POST /api/run`
   代码位置：`frontend/src/hooks/useTaskStream.ts`
3. 后端用 `threadId` 调用 `resumeThread` 或 `startThread`
   代码位置：`backend/src/routes/task.ts`
4. Codex 线程在 SSE 事件里返回 `thread.started`，其中带有 `thread_id`
5. 前端收到 `thread.started` 后，才把 `threadId` 存回当前 session
6. 前端在 run 结束后，才生成 `Turn.id` 并把本轮 events 写回 `sessions`

这意味着：

- `session_id` 目前只存在于前端 session 模型和 `sessions.json`
- `thread_id` 对于已有 session 是已知的；对于新 session 的第一轮，在发请求时未知
- `turn_id` 当前是在 run 完成后才生成，无法用于本轮执行中的 CLI 透传

## 2. 目标

目标不是让 FreeCAD CLI 去主动读取 `sessions.json` 推断上下文，而是让 Web / Agent 显式传入：

- `session_id`
- `thread_id`
- `turn_id`
- 可选：`run_id`

FreeCAD CLI 只负责消费这些上下文并写入 artifact registry：

- registry 索引：`<FREECAD_ARTIFACT_REGISTRY_DIR>/index.json`
- 单次 manifest：`<FREECAD_ARTIFACT_REGISTRY_DIR>/runs/<run_id>.json`

## 3. 推荐字段约定

### 3.1 Web 层字段

前端和后端之间建议统一以下字段名：

```json
{
  "prompt": "读取 YAML 并生成 assembly",
  "threadId": "019db475-aef0-7591-be45-427603bcf231",
  "sessionId": "mo9u2ua5xvp6xs176c",
  "turnId": "mo9ub1ikxqp4il65bld",
  "enabledSkills": ["freecad"]
}
```

字段说明：

- `sessionId`
  前端 session 主键，对应 `sessions.json[*].id`
- `threadId`
  Codex SDK thread ID，对应 `sessions.json[*].threadId`
- `turnId`
  前端为本轮预生成的稳定 ID
- `enabledSkills`
  保持现有语义不变

### 3.2 Agent -> FreeCAD CLI 字段

建议统一使用环境变量透传，必要时可再追加同名 CLI 参数作为冗余：

```bash
FREECAD_SESSION_ID
FREECAD_THREAD_ID
FREECAD_TURN_ID
FREECAD_RUN_ID
FREECAD_CALLER
FREECAD_AGENT_NAME
```

建议固定值：

- `FREECAD_CALLER=open_codex_web`
- `FREECAD_AGENT_NAME=codex`

CLI 侧已支持：

- `--run-id`
- `--session-id`
- `--thread-id`
- `--turn-id`

以及同名环境变量。

## 4. 最重要的时序约束

### 4.1 `session_id`

`session_id` 必须在前端发起 `/api/run` 之前就存在。

当前前端已经满足这一点：

- 新 session 在 `handleSubmit()` 里先创建
- 然后再调用 `run()`

所以 `session_id` 是最容易透传的字段。

### 4.2 `turn_id`

`turn_id` 需要改成“发请求前预生成”，不能继续在 run 完成后才创建。

推荐做法：

1. 前端点击提交
2. 立即生成 `turnIdForRun = generateId()`
3. 把 `turnIdForRun` 一起发给 `/api/run`
4. run 完成后归档当前 turn 时，直接使用这个 `turnIdForRun`

不要再在归档时重新生成另一个 `Turn.id`，否则 registry 和 session turn 无法稳定关联。

### 4.3 `thread_id`

这是最容易误判的点。

对于“已有 session 的后续轮”：

- `threadId` 已存在
- 可以在 `/api/run` 请求发起时透传

对于“新 session 的第一轮”：

- 当前实现里，`thread_id` 是在 SSE 的 `thread.started` 事件里才拿到
- 也就是说，第一轮开始执行 FreeCAD CLI 时，`thread_id` 很可能还不可用

因此推荐约定：

- 第一轮允许 `thread_id = null`
- registry 必须允许 `thread_id` 缺失
- 从第二轮开始再保证 `thread_id` 一定存在

这是当前实现下最现实也最稳的约定。

## 5. 推荐调用时序

### 5.1 新 session 第一轮

```text
frontend:
  1. 生成 sessionId
  2. 生成 turnId
  3. POST /api/run { prompt, threadId: null, sessionId, turnId, enabledSkills }

backend:
  4. startThread(...)
  5. build prompt prefix / context
  6. 开始 SSE 推流

agent:
  7. 若调用 FreeCAD CLI，则传：
     FREECAD_SESSION_ID=sessionId
     FREECAD_TURN_ID=turnId
     FREECAD_THREAD_ID=
     FREECAD_CALLER=open_codex_web
     FREECAD_AGENT_NAME=codex

frontend:
  8. 收到 thread.started，提取 thread_id
  9. 写回当前 session.threadId
  10. turn 完成后，用预生成的 turnId 归档
```

### 5.2 既有 session 的后续轮

```text
frontend:
  1. 从当前 session 读出 sessionId / threadId
  2. 预生成 turnId
  3. POST /api/run { prompt, threadId, sessionId, turnId, enabledSkills }

backend:
  4. resumeThread(threadId, ...)

agent:
  5. 调用 FreeCAD CLI 时传：
     FREECAD_SESSION_ID=sessionId
     FREECAD_THREAD_ID=threadId
     FREECAD_TURN_ID=turnId
     FREECAD_CALLER=open_codex_web
     FREECAD_AGENT_NAME=codex
```

## 6. 后端 `/api/run` 推荐请求体

当前后端签名是：

```ts
{ prompt: string; threadId?: string | null; enabledSkills?: string[] }
```

建议扩展为：

```ts
{
  prompt: string
  threadId?: string | null
  sessionId?: string | null
  turnId?: string | null
  enabledSkills?: string[]
}
```

推荐校验规则：

- `prompt` 必填
- `sessionId` 推荐必填
- `turnId` 推荐必填
- `threadId` 可空

## 7. Agent 提示词约定

后端当前会把 `enabledSkills` 拼到 prompt 前缀中：

- 代码位置：`backend/src/routes/task.ts`
- 函数：`buildPrompt()`

建议在这里继续追加一段“执行上下文约定”，例如：

```text
Execution context:
- session_id: mo9u2ua5xvp6xs176c
- thread_id: 019db475-aef0-7591-be45-427603bcf231
- turn_id: mo9ub1ikxqp4il65bld

When invoking any freecad-* CLI command, pass these values through environment variables:
- FREECAD_SESSION_ID
- FREECAD_THREAD_ID
- FREECAD_TURN_ID
- FREECAD_CALLER=open_codex_web
- FREECAD_AGENT_NAME=codex
```

推荐用法示例：

```bash
env \
  FREECAD_SESSION_ID=mo9u2ua5xvp6xs176c \
  FREECAD_THREAD_ID=019db475-aef0-7591-be45-427603bcf231 \
  FREECAD_TURN_ID=mo9ub1ikxqp4il65bld \
  FREECAD_CALLER=open_codex_web \
  FREECAD_AGENT_NAME=codex \
  freecad-create-assembly \
    --input /data/lbk/codex_web/FreeCAD_data/sample.yaml \
    --doc-name SampleYamlAssembly
```

如果你希望 run manifest 文件名也能被外层稳定引用，可以再追加：

```bash
FREECAD_RUN_ID=fc_run_20260423_153012_ab12cd
```

否则 CLI 会自行生成 `run_id`。

## 8. Frontend 推荐改法

### 8.1 提交前预生成 turnId

当前代码在 run 结束后才构造：

```ts
const completedTurn: Turn = {
  id: generateId(),
  userPrompt: currentPromptRef.current,
  events: currentEventsRef.current,
}
```

建议改成：

1. `handleSubmit()` 开始时生成 `turnIdForRun`
2. 保存到 ref：`currentTurnIdRef.current = turnIdForRun`
3. 发给 `/api/run`
4. 归档 turn 时使用 `currentTurnIdRef.current`

### 8.2 `/api/run` 请求体增加 `sessionId / turnId`

当前：

```ts
body: JSON.stringify({ prompt, threadId, enabledSkills })
```

建议：

```ts
body: JSON.stringify({
  prompt,
  threadId,
  sessionId,
  turnId,
  enabledSkills,
})
```

## 9. Backend 推荐改法

### 9.1 扩展 `/api/run` body 类型

把：

```ts
{ prompt: string; threadId?: string | null; enabledSkills?: string[] }
```

扩展为：

```ts
{
  prompt: string
  threadId?: string | null
  sessionId?: string | null
  turnId?: string | null
  enabledSkills?: string[]
}
```

### 9.2 在 prompt 前缀中注入执行上下文

当前后端没有逐请求环境变量注入到 Codex 命令执行层的显式代码，因此最稳的第一步是先用 prompt 协议约束 agent。

也就是说：

- 先在 `buildPrompt()` 里把 `sessionId / threadId / turnId` 明确写给 agent
- 要求 agent 在调用 `freecad-*` CLI 时显式用 `env ... freecad-xxx`

这是当前实现下最容易落地的方案。

## 10. Failure Handling

### 10.1 缺少 `session_id`

建议：

- Web 层尽量保证不缺
- 如果真缺失，允许 CLI 继续运行
- registry 里记 `session_id: null`

### 10.2 新 session 第一轮缺少 `thread_id`

建议：

- 允许 `thread_id: null`
- 不阻断 FreeCAD CLI
- 第二轮开始再要求稳定透传

### 10.3 缺少 `turn_id`

建议：

- Web 层修成提交前预生成
- 如果后端收到空值，可继续运行，但 registry 关联会变差

### 10.4 registry 写失败

当前 CLI 已实现为非致命：

- CAD 主流程成功不应因为 registry 失败而变成业务失败
- 只在 stderr 打 warning

## 11. 一套可直接执行的最小接入方案

如果只做 MVP，推荐按下面顺序：

1. 前端提交前预生成 `turnId`
2. `/api/run` 增加 `sessionId / turnId`
3. 后端 `buildPrompt()` 注入：
   - `session_id`
   - `thread_id`
   - `turn_id`
   - “调用 freecad-* CLI 时必须用 env 透传”
4. 先只约束 `freecad-create-assembly / freecad-replace-component / freecad-yaml-safe-move`
5. UI 暂时不读 registry，只先让 registry 文件稳定落账

## 12. 一个完整示例

### 12.1 前端请求

```http
POST /api/run
Content-Type: application/json

{
  "prompt": "读取 /data/lbk/codex_web/FreeCAD_data/sample.yaml，生成 assembly",
  "threadId": "019db475-aef0-7591-be45-427603bcf231",
  "sessionId": "mo9u2ua5xvp6xs176c",
  "turnId": "mo9ub1ikxqp4il65bld",
  "enabledSkills": ["freecad"]
}
```

### 12.2 Agent 实际命令

```bash
env \
  FREECAD_SESSION_ID=mo9u2ua5xvp6xs176c \
  FREECAD_THREAD_ID=019db475-aef0-7591-be45-427603bcf231 \
  FREECAD_TURN_ID=mo9ub1ikxqp4il65bld \
  FREECAD_CALLER=open_codex_web \
  FREECAD_AGENT_NAME=codex \
  freecad-create-assembly \
    --input /data/lbk/codex_web/FreeCAD_data/sample.yaml \
    --doc-name SampleYamlAssembly
```

### 12.3 产物登记结果

CLI 会写出：

- `/data/lbk/codex_web/FreeCAD_data/registry/index.json`
- `/data/lbk/codex_web/FreeCAD_data/registry/runs/<run_id>.json`

其中 manifest 会包含：

- `session_id`
- `thread_id`
- `turn_id`
- `inputs.yaml_path`
- `outputs.step_path`
- `outputs.glb_path`

## 13. 推荐的下一步实现顺序

推荐实际改造顺序：

1. 改前端：`turnId` 预生成
2. 改前端：`/api/run` body 增加 `sessionId / turnId`
3. 改后端：扩展 `/api/run` body 类型
4. 改后端：`buildPrompt()` 注入上下文协议
5. 验证 agent 实际发出的 `freecad-*` 命令是否带 `env FREECAD_*`
6. 最后再决定要不要新增一个 `/api/freecad-artifacts` 查询接口，把 registry 读回 UI

---

一句话总结：

当前实现下最稳的透传方案是“前端显式生成 `sessionId + turnId`，`threadId` 对新 session 第一轮允许为空，后端通过 prompt 协议要求 agent 用 `env FREECAD_*` 调用 FreeCAD CLI”，而不是让 CLI 去反查 `sessions.json`。
