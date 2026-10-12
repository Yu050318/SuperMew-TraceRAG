# S3：Vue 来源详情与真实联调

## 实现

沿用 Chat 与 `cite-click`，不新增聊天页、Citation Store、下载/Excel 预览 API。

| 文件 | 修改 |
| --- | --- |
| `utils/ragSources.ts` | 统一来源校验、允许引用位置、叶子/父块/旧文档格式；null 与缺省兼容 |
| `References.vue` | 使用实际入选集合，区分回答已引用/入选未引用/旧检索记录；真实来源摘要与截断提示 |
| `KnowledgeContextPanel.vue` | 同一来源函数与入选集合，不用候选排名替代引用 |
| `MessageItem.vue` | 区分检索数与已引用数；给 MessageContent 传允许编号 |
| `MessageContent.vue`、`utils/markdown.ts` | 仅合法编号生成可点击引用；未知数字仍是文本，不制造跳转 |
| `ChatArea.vue` | 点击再次核验真实来源数量后定位已有 chunk DOM |
| `events/runEventReducer.ts` | 公开 Trace 校验后才推进 sequence，复用原错误处理 |
| `stores/chat.ts` | 历史消息同样校验来源 |

父块显示“不连续命中行集合”，不是整个父块覆盖区间。PDF 页码保留；无 provenance 的
旧 XLS/XLSX 只显示文件级来源；HTML/Word 保持原展示。空入选集合不得 fallback 候选。

## 真实联调证据

测试所有者 account_id=3 的密码重设已获授权；经正式登录 API 操作，凭据仅内存传输，
不改变其他用户/角色/所有权。Chrome headless 访问真实 FastAPI 托管的 Vue 生产 Build，
正式 Chat/SSE Run 查询开发题 `table_query_003`：`NX-003 的库存是多少？`。

实时回答为库存 **88 台**、上海测试仓、2026-10-01；显示 inventory.xlsx 的 `库存` Sheet
和命中物理行。点击 `[1]` 定位到实际已渲染证据。刷新、选择同一历史 Thread 后，引用
详情文本完全一致。`.artifacts/synthetic-enterprise/s3/live-ui.json` 记录 Run/Thread IDs、
去正文 Trace、事件 sequence 与检查结果；`live-citations.png`、`history-citations.png`
为真实截图（忽略目录，不提交）。正式 Event Journal 重放用于核验，实时 DOM 来自 SSE，
不是离线注入事件或 mock UI。

联调修复两个测试/兼容问题：Chrome 可能回收已完成 SSE body，改用正式持久 Event
Journal 核验而不再次调用 RAG；历史 response-model 的 null 来源曾被客户端当成不完整
字段，已改为“null=缺省”，新增回归，不放宽非空 malformed 来源校验。

另修复原 `scripts/check-bundle-size.mjs` 的 Windows URL.pathname 与分隔符问题，使用
Node `fileURLToPath`/原生 separator；门限未变，实测初始 JS gzip 73.64 KiB。

## 测试和边界

`References.spec.ts` 校验父块详情/真实点击；`ragSources.spec.ts` 校验非法位置、旧格式、
null；`runEventReducer.spec.ts` 校验同一来源实时与 journal replay 一致。完整前端
229 tests / 27 files 通过；typecheck、lint、build:check 通过。

本轮实时 UI 验证一条代表题，不声称 20 题都经浏览器执行；20 题由原生 Evaluation Worker
执行。详情是只读证据，不是原 Excel 光标定位。合法来源不等于该父块每行都支持答案。
