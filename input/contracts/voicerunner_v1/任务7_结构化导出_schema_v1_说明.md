# 任务 7 结构化导出 Schema v1 说明

## 1. 文档目的

本文说明 [任务7_结构化导出_schema_v1.json](任务7_结构化导出_schema_v1.json) 的数据结构、字段语义和校验边界。对应示例见 [任务7_结构化导出_Mock.json](任务7_结构化导出_Mock.json)。

Schema 使用 JSON Schema Draft 2020-12，描述 CANVoiceRunner V2 单个采集 Session 的正式结构化导出。它面向 Java、Python及其他语言的读取、模型生成、格式校验和后续 ASC 分析输入。

该 JSON 是现场采集事实的索引，不包含 Raw ASC、图片二进制或音频二进制，也不负责解析 CAN、切割 ASC、识别车辆状态或形成诊断结论。

## 2. 总体结构

| 顶层字段 | 类型 | 必填 | 作用 |
|---|---|---:|---|
| `schema_version` | integer | 是 | 固定为 `1` |
| `mock_data` | boolean | 否 | 标识测试数据；正式文件可省略或设为 `false` |
| `exported_clock` | string | 是 | JSON 文件实际导出 Clock |
| `app_version` | string | 是 | 生成文件的 App 版本 |
| `session` | object | 是 | 本次 Session 的时间原点和结束状态 |
| `events` | array | 是 | 脚本 Event 及其计划、触发和跳过信息 |
| `photos` | array | 是 | 成功生成照片记录的照片元数据 |
| `notes` | array | 是 | Event 与照片备注，包括逻辑删除记录 |
| `audio_recording` | object | 是 | 本次 Session 的录音文件索引和录音自身元数据 |

顶层对象设置 `additionalProperties: false`。字段拼写错误或未经 Schema 定义的新字段应被校验器拒绝，避免不同语言静默产生不一致数据。

`events`、`photos` 和 `notes` 即使没有数据也必须存在，并使用空数组 `[]`。`audio_recording` 必须存在；未启用录音时用 `enabled = false`、`status = DISABLED` 及其他字段 `null` 明确表达，不能通过缺少对象猜测原因。

## 3. 通用数据约定

### 3.1 Clock

所有 `*_clock` 使用带日期、三位毫秒和时区的 ISO 8601 字符串：

```text
2026-09-09T15:30:25.827+08:00
```

| 要求 | 说明 |
|---|---|
| 日期 | 必须存在，不能只写 `15:30:25` |
| 毫秒 | 必须正好三位 |
| 时区 | 必须使用 `Z` 或 `±HH:mm` |
| 记录精度 | 毫秒，不伪造现实 Clock 的微秒精度 |

Schema 同时使用 `format: date-time` 和正则表达式约束格式。实际校验器必须启用 `format` 检查，不能只解析 JSON 语法。

### 3.2 `script_time`

| 约定 | 说明 |
|---|---|
| 单位 | 整数微秒 `us` |
| 时间源 | `ELAPSED_REALTIME` |
| 零点 | Session 正式开始时为 `0` |
| 暂停 | 暂停播报不停止 `script_time` |
| 普通事件时间 | 必须大于或等于 `0` |
| 录音起点偏移 | 可以为负数，因为录音可在准备倒计时提前开始 |

整数微秒是存储分辨率，不代表所有设备事件都具有一微秒真实准确度。录音起点在 v1 中明确记录工程准确度 `start_accuracy_us = 20000`。

### 3.3 空值

字段已经进入固定合同但本次不适用或未发生时使用 JSON `null`，不得使用：

```text
""
"null"
"N/A"
-1
0（当 0 可能被误解为真实时间时）
```

例如没有跳过的 Event：

```json
"skip_script_time_us": null
```

### 3.4 状态与枚举

机器字段使用 Schema 中定义的英文枚举，不能输出中文展示文字。例如 UI 的“录音已保存”在 JSON 中写作 `SAVED`。

### 3.5 文件编码

正式 JSON 使用 UTF-8。脚本动作和备注允许中文，消费者不得使用系统默认编码猜测文件内容。

## 4. Session 对象

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `session_id` | string | 是 | `S` 加数字，如 `S01` |
| `source_script_name` | string | 是 | 原始采集脚本文件名，不使用安全清洗后的替代值 |
| `start_clock` | Clock | 是 | Session 正式开始 Clock |
| `start_clock_epoch_ms` | integer | 是 | `start_clock` 对应的 Unix Epoch 毫秒 |
| `end_clock` | Clock | 是 | Session 正常结束或 `abort` Clock |
| `end_clock_epoch_ms` | integer | 是 | `end_clock` 对应的 Unix Epoch 毫秒 |
| `end_script_time_us` | integer | 是 | Session 最终真实耗时，必须大于或等于 `0` |
| `status` | enum | 是 | `COMPLETED / ABORTED / FAILED` |
| `end_reason` | string | 是 | 具体结束原因 |
| `script_time_source` | const | 是 | 固定为 `ELAPSED_REALTIME` |
| `script_time_unit` | const | 是 | 固定为 `us` |
| `clock_precision` | const | 是 | 固定为 `ms` |

Session 状态：

| 状态 | 含义 |
|---|---|
| `COMPLETED` | Session 按正常路径结束 |
| `ABORTED` | 用户或程序明确强行终止 |
| `FAILED` | Session 因采集级错误失败 |

录音失败不会自动把 Session 改为 `FAILED`。任务 6 已确定录音是可选附属证据，录音失败不得阻断主 Session。

`end_reason` 当前保持非空字符串，而不是封闭枚举，便于记录更具体的结束原因。处理程序应以 `status` 做主判断，把 `end_reason` 作为补充上下文。

## 5. Event 对象

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `event_id` | string | 是 | `E` 加数字，如 `E05` |
| `event_sequence` | integer | 是 | Event 在脚本中的一基顺序，从 `1` 开始 |
| `action` | string | 是 | 脚本原始实验目标动作 |
| `action_detail` | string | 是 | 动作下方的脚本原始详细说明；没有时为空字符串 |
| `plan_time_s` | integer | 是 | 脚本原始计划秒数，不因提前、延后或暂停而修改 |
| `status` | enum | 是 | `pending / triggered / skipped` |
| `trigger_script_time_us` | integer/null | 是 | 实际触发播报的 `script_time` |
| `skip_script_time_us` | integer/null | 是 | 人工跳过确认的 `script_time` |

状态与时间组合：

| `status` | `trigger_script_time_us` | `skip_script_time_us` | 含义 |
|---|---|---|---|
| `pending` | `null` | `null` | 计划节点尚未触发，也未跳过 |
| `triggered` | integer | `null` | 已触发，默认按剧本采集 |
| `skipped` | integer | integer | Event 触发后确认未执行；原触发时间必须保留 |

“跳过”只允许作用于已经触发的当前 Event，不允许跳过尚未触发的下一个 Event。Schema 强制 `triggered` 必须有触发时间，`skipped` 必须同时具有触发时间和跳过时间。v1 Schema 尚未通过条件语句强制 `pending` 的两个时间一定为 `null`，处理程序仍应执行此项语义校验。

`action` 永远表示脚本实验语义；状态变化不得覆盖动作文本。

## 6. Photo 对象

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `photo_id` | string | 是 | 例如 `E05-P01` |
| `event_id` | string | 是 | 用户点击拍照时冻结的 Event |
| `photo_sequence` | integer | 是 | 该 Event 内成功照片的一基顺序 |
| `captured_clock` | Clock | 是 | 图像传感器拍摄时刻对应 Clock |
| `captured_script_time_us` | integer | 是 | 拍摄时刻相对 Session 零点的时间 |
| `file_name` | string | 是 | 人工可读照片文件名 |
| `content_uri` | string | 是 | Android `MediaStore` URI |
| `file_status` | enum | 是 | `AVAILABLE / UNAVAILABLE` |

只有照片成功保存后才产生 Photo 对象。拍摄失败不生成 `photo_id`，也不在数组中放置失败占位记录。

`UNAVAILABLE` 表示照片记录仍然存在，但文件已被外部删除或当前不可读取。消费者不得因文件不可用而丢弃照片的事件关系和时间信息。

`content_uri` 是目标 Android 设备上的内容 URI，不是跨设备通用文件路径。其他语言在电脑上处理 JSON 时，应使用 `file_name` 匹配随同传输的照片文件，不能假定可以直接打开手机 URI。

## 7. Note 对象

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `note_id` | string | 是 | `N` 加数字，如 `N0001` |
| `target_type` | enum | 是 | `EVENT / PHOTO` |
| `target_id` | string | 是 | 对应 `event_id` 或 `photo_id` |
| `text` | string | 是 | 非空纯文本备注 |
| `created_clock` | Clock | 是 | 新增入口触发 Clock |
| `created_script_time_us` | integer | 是 | 新增入口触发时间 |
| `updated_clock` | Clock/null | 是 | 最近一次修改 Clock |
| `updated_script_time_us` | integer/null | 是 | 最近一次修改时间 |
| `deleted` | boolean | 是 | 是否逻辑删除 |
| `deleted_clock` | Clock/null | 是 | 逻辑删除确认 Clock |
| `deleted_script_time_us` | integer/null | 是 | 逻辑删除确认时间 |

目标约束：

| `target_type` | `target_id` 格式 |
|---|---|
| `EVENT` | `E` 加数字 |
| `PHOTO` | `E` 加数字、`-P`、再加数字 |

修改字段必须成对出现：

| 情况 | `updated_clock` | `updated_script_time_us` |
|---|---|---|
| 从未修改 | `null` | `null` |
| 已修改 | Clock | integer |

删除字段也必须成对出现。`deleted = false` 时两个删除字段必须为 `null`；`deleted = true` 时两个字段必须有值。逻辑删除的备注仍然输出完整 `text`、创建和修改历史，供审计使用。

一张照片同时最多存在一条 `deleted = false` 的照片备注。Schema 可以校验单条 Note 的结构，但不能仅靠当前规则检查整个数组内是否出现两条指向同一照片的有效备注，此约束必须由导出端和读取端共同检查。

## 8. Audio Recording 对象

`audio_recording` 只保存录音文件索引和录音自身时间，不包含 `.m4a` 音频数据，也不保存它与 Event、Photo 或 Note 的关系。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `enabled` | boolean | 是 | 采集前是否打开录音选项 |
| `status` | enum | 是 | 录音状态 |
| `file_name` | string/null | 是 | 录音文件名 |
| `content_uri` | string/null | 是 | Android `MediaStore` URI |
| `request_clock` | Clock/null | 是 | 录音启动请求 Clock |
| `request_offset_us` | integer/null | 是 | 请求时刻相对 Session 零点的有符号偏移 |
| `start_clock` | Clock/null | 是 | 首个有效 PCM 音频帧对应 Clock |
| `start_offset_us` | integer/null | 是 | 首帧相对 Session 零点的有符号偏移 |
| `start_method` | enum/null | 是 | 起点测量方法 |
| `start_accuracy_us` | integer/null | 是 | 起点工程准确度 |
| `end_clock` | Clock/null | 是 | 录音结束 Clock |
| `end_script_time_us` | integer/null | 是 | 停止录音时的 `script_time` |
| `duration_us` | integer/null | 是 | 音频媒体时长 |
| `sample_rate_hz` | integer/null | 是 | 实际采样率 |
| `channel_count` | integer/null | 是 | 实际声道数 |
| `mime_type` | string/null | 是 | 例如 `audio/mp4` |
| `bit_rate` | integer/null | 是 | 实际编码码率 |
| `end_reason` | string/null | 是 | 正常结束、`abort` 或中断原因 |
| `failure_clock` | Clock/null | 是 | 录音失败 Clock |
| `failure_script_time_us` | integer/null | 是 | 录音失败时的 `script_time` |
| `failure_reason` | string/null | 是 | 失败原因，如 `PERMISSION_NOT_GRANTED` |

录音状态：

| 状态 | 含义 |
|---|---|
| `DISABLED` | 本次未选择录音 |
| `PREPARING` | 正在准备录音 |
| `RECORDING` | 正在录音 |
| `SAVED` | 录音成功停止并保存 |
| `FAILED` | 权限、初始化、启动或采集中断失败 |
| `SAVE_FAILED` | 已录制但最终编码或保存失败 |

正式结束后导出的文件通常应为 `DISABLED / SAVED / FAILED / SAVE_FAILED`。`PREPARING / RECORDING` 保留在 Schema 中，是为了允许任务 8 持久化或异常快照复用同一对象；正常最终导出不应停留在运行态。

主要条件约束：

| 条件 | Schema 要求 |
|---|---|
| `enabled = false` | `status` 必须为 `DISABLED` |
| `enabled = true` | `status` 不能为 `DISABLED` |
| `status = SAVED` | 文件名、URI、起止 Clock、时长和音频参数必须存在 |
| `start_method = AUDIO_TIMESTAMP_BOOTTIME` | `start_offset_us` 与 `start_accuracy_us` 必须为整数 |
| `start_method = TIMESTAMP_UNAVAILABLE` | 两个起点数值必须为 `null` |

准备倒计时可能使 `start_offset_us` 为负数。例如 `-2385000` 表示首个有效音频帧比 Session 零点早 2.385 秒；正数表示 Session 开头存在对应时长的漏录。

## 9. ID 与对象关系

| 来源对象 | 关系字段 | 目标 |
|---|---|---|
| Photo | `event_id` | Event |
| Event Note | `target_id` | Event |
| Photo Note | `target_id` | Photo |
| Audio Recording | 无 | 只属于当前 Session |

以下关系不是自动语义推断：

- 时间接近的录音内容与 Event 不自动关联；
- 时间接近的照片与备注不自动关联；
- Audio Recording 中不保存 `event_id`、`photo_id` 或 `note_id`。

## 10. JSON Schema 校验范围

Schema 能直接检查：

- 必填字段是否存在；
- JSON 类型是否正确；
- 未定义字段是否出现；
- ID 与 Clock 格式；
- 枚举是否合法；
- 数值是否非负或允许有符号；
- Event 状态与必要时间字段；
- Note 修改、删除字段是否成对；
- Recording 状态与必要文件、时间及格式字段。

Schema v1 不能独立完成以下跨对象语义检查：

| 语义检查 | 原因/处理方式 |
|---|---|
| 所有 ID 在数组内唯一 | 需要遍历集合建立索引 |
| Photo 的 `event_id` 确实存在 | 需要跨数组引用检查 |
| Note 的 `target_id` 确实存在 | 需要跨数组引用检查 |
| `photo_id` 前缀与 `event_id` 完全一致 | 需要比较同一对象内两个字段的内容 |
| Event `event_sequence` 唯一且连续 | 需要集合级检查 |
| 一张照片最多一条有效备注 | 需要按目标分组统计 |
| Epoch 与 ISO Clock 表示同一时刻 | 需要解析并换算时间 |
| 所有事件时间不超过 Session 结束时间 | 需要跨对象数值比较 |
| 修改时间不早于创建时间 | 需要字段间比较 |
| 音频时长与起止时间物理一致 | 需要容差和媒体文件核验 |
| 文件真实存在且可读 | 需要访问 Android URI 或导出文件包 |

因此，其他语言的处理程序应分两层验证：

```text
JSON Schema 结构验证
        ↓
跨对象与时间语义验证
        ↓
进入 ASC 时间窗口或其他分析
```

Schema 校验失败时不得继续把文件当作正式 Timeline。语义校验失败时应保留原文件并报告具体字段、对象 ID 和失败原因，不能静默修复现场事实。

## 11. 跨语言类型映射

| JSON Schema | Java 建议类型 | Python 建议类型 | JavaScript/TypeScript 建议类型 |
|---|---|---|---|
| `integer` 时间微秒 | `long` / `Long` | `int` | `number`；读取时检查安全整数 |
| `boolean` | `boolean` / `Boolean` | `bool` | `boolean` |
| Clock string | `OffsetDateTime` | 带时区 `datetime` | ISO 字符串或 `Temporal`/日期库对象 |
| `string/null` | `String` 可空 | `str | None` | `string | null` |
| `integer/null` | `Long` | `int | None` | `number | null` |
| enum | Java `enum` | `Enum` 或受限字符串 | 字符串联合类型 |
| array | `List<T>` | `list[T]` | `T[]` |

Java 不应使用 `int` 保存微秒或 Epoch 值。所有语言都应按整数读取微秒字段，不转为浮点秒后再保存，以免引入舍入误差。

## 12. 推荐读取顺序

| 步骤 | 操作 |
|---:|---|
| 1 | 以 UTF-8 读取 JSON |
| 2 | 检查 `schema_version` 是否为处理程序支持的版本 |
| 3 | 使用 Draft 2020-12 校验器验证 Schema |
| 4 | 建立 Event、Photo、Note ID 索引并检查唯一性 |
| 5 | 检查跨数组引用和照片单条有效备注约束 |
| 6 | 检查 Clock、Epoch 和 `script_time` 的时间一致性 |
| 7 | 按任务需要读取附件文件；不要直接假定 `content_uri` 在电脑上可访问 |
| 8 | 只有结构和语义校验通过后，才把 Timeline 交给后续 ASC 分析程序 |

## 13. 版本规则

`schema_version = 1` 对应本文和当前 Schema 文件。v1 一旦审核定稿，字段名、含义、类型、枚举和必填性不应静默改变。

| 变化 | 处理方式 |
|---|---|
| 修正文档文字但不改变合同 | 保持 v1 |
| 增加或删除字段 | 建立新 Schema 版本 |
| 修改字段类型或单位 | 建立新 Schema 版本 |
| 修改枚举或状态语义 | 建立新 Schema 版本 |
| 修改 ID 规则或时间原点 | 建立新 Schema 版本 |

处理程序遇到未知 `schema_version` 时应停止并报告不支持，不能按最接近版本猜测。

## 14. 当前验证状态

Schema 与 Mock 均已通过 JSON 语法检查。当前工作环境未预装独立 JSON Schema 校验器，因此 Draft 2020-12 Schema 对 Mock 的完整语义执行验证尚未完成；该验证必须在任务 7 测试阶段纳入自动化测试。
