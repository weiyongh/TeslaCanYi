# `event_timeline.csv` v1 接口合同

## 1. 文档目的

本文定义 CANVoiceRunner Android 采集端与 Python/ASC 分析端之间的 Event 时间线接口合同。

`event_timeline.csv` 是 Android App 根据现场实际采集过程计算形成的 Event 时间结果，主要用于：

1. 把采集脚本中的实验动作映射为稳定的 `event_id`。
2. 提供 Event 滴声发生时相对 Session 零点的真实时间偏移。
3. 把相对时间重算为可与 ASC 对齐的绝对 Clock。
4. 明确区分已触发并默认执行、已触发但人为跳过，以及尚未触发的 Event。

该 CSV 是采集分析接口，不是 UI 展示文件，也不是完整 Session 元数据文件。照片、备注、录音和 Session 完整信息保存在同目录的 `session.json`。

## 2. 合同版本与识别

| 项目 | 固定值或规则 |
|---|---|
| 接口名称 | `event_timeline.csv` |
| 接口版本 | v1 |
| 字符编码 | UTF-8 |
| 表头 | 必须与本文第 4 节完全一致 |
| 数据行 | 一行对应一个采集脚本 Event |
| 行顺序 | 与采集脚本 Event 顺序一致 |
| 换行 | 当前生成器使用 LF；消费者应兼容常规 CSV 换行 |
| 时间数量 | 十进制整数，不使用浮点数 |
| 缺失值 | 空字段，不写 `null`、`None`、`NaN` 或 `0` |

CSV 本身不增加 `schema_version` 列。消费者应优先结合同目录 `session.json` 的 `schema_version = 1` 判断合同版本；仅取得 CSV 时，必须严格核对完整表头，不得根据相似字段猜测格式。

## 3. 文件与 Session 的关系

一个采集 Session 对应一个独立目录：

```text
Download/CANVoiceRunner/
└── <脚本名称>__<start_clock毫秒时间戳>__<S####>/
    ├── session.json
    ├── event_timeline.csv
    ├── photos/
    └── audio/
```

关系规则：

- `event_timeline.csv` 与同目录 `session.json` 必须属于同一个 Session。
- CSV 的 `event_id` 必须与 JSON `events[].event_id` 一一对应。
- CSV 的 `session_script_time_us` 与 JSON 的 `trigger_script_time_us` 表达同一个 Event 滴声时间。
- CSV 的 `skip_script_time_us` 与 JSON 同名字段表达同一个人为跳过时间。
- CSV 不重复保存 `session_id`、Session 起止 Clock、照片、备注或录音对象。
- 同一个采集脚本可以产生多个 Session；分析端不得仅凭脚本文件名合并 CSV。

## 4. 固定表头

v1 表头固定为：

```csv
event_id,action,plan_time_s,status,session_script_time_us,skip_script_time_us,clock_iso,clock_epoch_ms
```

不允许静默增加、删除、改名或调整字段顺序。未来如需改变合同，应建立新版本。

## 5. 字段定义

| 顺序 | 字段 | CSV 类型 | 单位 | 可为空 | 准确定义 |
|---:|---|---|---|---:|---|
| 1 | `event_id` | string | — | 否 | Event 稳定编号，例如 `E01`。编号按脚本顺序从 1 开始生成 |
| 2 | `action` | string | — | 否 | 采集脚本中的实验目标动作原文；UI 操作和状态变化不得覆盖其语义 |
| 3 | `plan_time_s` | integer | 秒 | 否 | 脚本原始计划时间；从脚本读取后永久保留，不因提前、延后、暂停或跳过而修改 |
| 4 | `status` | enum string | — | 否 | `pending / triggered / skipped` 之一 |
| 5 | `session_script_time_us` | integer | 微秒 | 条件允许 | Event 的 3—2—1 倒计时结束后，滴声发生时相对 Session `script_time = 0` 的真实偏移 |
| 6 | `skip_script_time_us` | integer | 微秒 | 条件允许 | Event 已触发后，用户确认动作未执行并点击“跳过”时相对 Session 零点的真实偏移 |
| 7 | `clock_iso` | ISO 8601 string | 毫秒 Clock | 条件允许 | 根据 Session Clock 锚点与 `session_script_time_us` 重算的 Event 绝对 Clock，包含日期、毫秒和时区 |
| 8 | `clock_epoch_ms` | integer | Unix Epoch 毫秒 | 条件允许 | 与 `clock_iso` 表达同一绝对时刻，供程序直接计算 |

### 5.1 `plan_time_s`

`plan_time_s` 是剧本时间，不是现场事实：

```text
plan_time_s = 42
```

只表示脚本计划在第 42 秒触发该 Event。暂停播报可以推迟实际触发，但不得把现场触发时间反写到 `plan_time_s`。

### 5.2 `session_script_time_us`

`session_script_time_us` 是现场 Event 滴声的实际相对时间：

```text
session_script_time_us = 42048642
```

其时间源为 Android 单调时间 `SystemClock.elapsedRealtimeNanos()`，从 Session 正式开始零点连续流淌。暂停播报、打开相机、输入备注、切换前后台或锁屏均不得使其停止、冻结、回拨或重新计时。

该字段记录的是 Event 滴声时间，不是人为点击“完成”的时间，也不是由 CAN Signal 变化反推的时间。

### 5.3 `skip_script_time_us`

跳过只允许作用于已经触发的当前 Event。因此：

- 不存在 `pending → skipped`。
- `skipped` 必须保留原 `session_script_time_us`。
- `skip_script_time_us` 必须大于或等于同一行的 `session_script_time_us`。
- `skipped` 表示滴声已经发生，但对应实验动作没有实际执行。

分析端不得把 `skip_script_time_us` 当作动作发生时间。

## 6. 状态与空值合同

| `status` | `session_script_time_us` | `skip_script_time_us` | `clock_iso` | `clock_epoch_ms` | 实验语义 |
|---|---:|---:|---|---:|---|
| `pending` | 空 | 空 | 空 | 空 | 采集结束前该计划节点没有触发 |
| `triggered` | 非负整数 | 空 | 非空 | 非负整数 | Event 已滴声触发，默认按剧本完成采集 |
| `skipped` | 非负整数 | 非负整数 | 非空 | 非负整数 | Event 已滴声触发，但用户明确标记动作未执行 |

禁止用 `0` 表示缺失时间。Event 可以合法地在零点附近触发，因此 `0` 是有效数值，不是空值替代品。

## 7. Clock 重算合同

### 7.1 计算公式

对具有 `session_script_time_us` 的 Event：

```text
clock_epoch_ms =
    session.start_clock_epoch_ms
    + round(session_script_time_us / 1000)
```

当前 Java 实现使用正数 `Math.round(double)`：微秒除以 1000 后四舍五入到最接近的毫秒。

随后使用与 Session `start_clock` 相同的时区偏移格式化：

```text
clock_iso = ISO8601(clock_epoch_ms, session.start_clock timezone)
```

示例：

```text
session.start_clock_epoch_ms = 1788994804125
session_script_time_us       = 42048642
round(42048642 / 1000)       = 42049
clock_epoch_ms               = 1788994846174
clock_iso                    = 2026-09-10T07:00:46.174+08:00
```

### 7.2 精度边界

- 相对 Event 时间继续保留整数微秒，不得仅从 `clock_iso` 反推 Event 间隔。
- 绝对 Clock 记录到毫秒，不宣称墙上时钟具有微秒级准确度。
- `clock_iso` 和 `clock_epoch_ms` 是由同一 Session 锚点计算的两个表达，必须相互一致。
- CSV 内部换算自洽不自动证明已经与 ASC 对齐。ASC 必须与 Android 共享时间原点，或存在另外确定、可审计的时间映射。

## 8. Event 语义合同

1. 采集脚本的每个计时节点均为普通 Event。
2. 脚本中的“开始采集”和“结束采集”也是普通 Event，不生成 `session_start` 或 `session_end` 特殊 CSV 行。
3. `action` 始终保存实验目标动作，不写成“完成”“跳过”“点击按钮”等 UI 操作。
4. App 不根据照片、备注、录音或 CAN Signal 自动改变 Event 状态。
5. Event 状态表示现场采集记录，不证明车辆物理响应已经发生。

## 9. CSV 转义规则

当前生成器遵循以下输出规则：

- `action` 和 `clock_iso` 总是使用双引号包围。
- 字段内容中的一个双引号写成两个双引号。
- `event_id`、整数和状态不额外加引号。
- 空值输出为两个分隔逗号之间没有字符。
- 动作中可以包含中文、空格和逗号，消费者必须使用标准 CSV 解析器，不得直接按逗号拆分字符串。

示例：

```csv
E01,"插入""充电枪""",30,triggered,34827000,,"2026-09-10T09:30:34.827+08:00",1789003834827
```

## 10. 完整示例

| event_id | action | plan_time_s | status | session_script_time_us | skip_script_time_us | clock_iso | clock_epoch_ms |
|---|---|---:|---|---:|---:|---|---:|
| E01 | 开始采集 | 0 | triggered | 125000 |  | 2026-09-10T09:30:00.125+08:00 | 1789003800125 |
| E02 | 手动下降，按住 | 20 | triggered | 21427836 |  | 2026-09-10T09:30:21.428+08:00 | 1789003821428 |
| E03 | 松开 | 22 | skipped | 23550642 | 24100821 | 2026-09-10T09:30:23.551+08:00 | 1789003823551 |
| E04 | 自动上升 | 37 | pending |  |  |  |  |

对应原始 CSV：

```csv
event_id,action,plan_time_s,status,session_script_time_us,skip_script_time_us,clock_iso,clock_epoch_ms
E01,"开始采集",0,triggered,125000,,"2026-09-10T09:30:00.125+08:00",1789003800125
E02,"手动下降，按住",20,triggered,21427836,,"2026-09-10T09:30:21.428+08:00",1789003821428
E03,"松开",22,skipped,23550642,24100821,"2026-09-10T09:30:23.551+08:00",1789003823551
E04,"自动上升",37,pending,,,"",
```

## 11. Python 消费规则

推荐使用 `csv.DictReader`，并显式转换整数和空值：

```python
import csv


def optional_int(value: str) -> int | None:
    return int(value) if value != "" else None


with open("event_timeline.csv", encoding="utf-8", newline="") as stream:
    rows = list(csv.DictReader(stream))

for row in rows:
    row["plan_time_s"] = int(row["plan_time_s"])
    row["session_script_time_us"] = optional_int(
        row["session_script_time_us"]
    )
    row["skip_script_time_us"] = optional_int(row["skip_script_time_us"])
    row["clock_epoch_ms"] = optional_int(row["clock_epoch_ms"])
```

按实验动作建立 ASC 分析窗口时：

- `triggered`：可以作为默认有效动作 Event 时间点，但仍需结合现场记录确认物理动作和证据质量。
- `skipped`：不得作为动作实际发生点，应从有效动作窗口中排除；可以保留作流程审计。
- `pending`：没有现场触发时间，不得参与实际时间窗口计算。

分析处分离“解析成功”和“实验有效”。CSV 行合法并不自动意味着该 Event 足以形成有效 CAN 分析窗口。

## 12. 与采集脚本及 ASC 的交接

建议分析端按以下顺序处理：

1. 确认 Session 目录及 `session.json`、`event_timeline.csv` 属于同一次采集。
2. 核对 CSV 表头是否为 v1 固定表头。
3. 按 `event_id` 对应 JSON Event 和当前采集脚本节点。
4. 核对 `action`、`plan_time_s` 是否保持脚本原值。
5. 执行状态与空值约束检查。
6. 使用 Session 起点重新计算每个已触发 Event 的 `clock_epoch_ms`。
7. 按确定的 Clock 映射把有效 Event 投射到 ASC 时间轴。
8. `skipped` 和 `pending` 不建立有效动作分析窗口。
9. 保留原始 CSV，不由分析程序就地改写。

App 不修改 Raw ASC，也不在 CSV 中保存 ASC 文件名或 CAN 分析结论。ASC 与 Session 的归属及时间映射必须由上层采集记录或分析流程明确建立。

## 13. 消费者强制校验清单

| 编号 | 校验项 | 失败处理 |
|---:|---|---|
| 1 | 文件为 UTF-8 且能由标准 CSV 解析器读取 | 停止处理并报告格式错误 |
| 2 | 表头与 v1 固定表头完全一致 | 停止处理，不猜测版本 |
| 3 | `event_id` 非空、唯一且顺序与脚本一致 | 停止该 Session 分析 |
| 4 | `action` 非空，`plan_time_s` 为非负整数 | 报告脚本接口错误 |
| 5 | `status` 属于三个允许值 | 停止处理该行 |
| 6 | 状态与三个时间字段的空值组合符合第 6 节 | 报告合同错误 |
| 7 | `skip_script_time_us >= session_script_time_us` | 报告时间顺序错误 |
| 8 | `clock_epoch_ms` 符合第 7 节重算公式 | 报告 Clock 映射错误 |
| 9 | `clock_iso` 与 `clock_epoch_ms` 表示同一毫秒时刻 | 报告格式化错误 |
| 10 | CSV Event 与 JSON Event 一一对应 | 停止该 Session 联合分析 |
| 11 | `plan_time_s` 与采集脚本原值一致 | 报告脚本被改写或文件错配 |
| 12 | ASC 时间映射来源明确且可审计 | 不进入正式 ASC 证据分析 |

## 14. 生产者保证与非保证范围

Android App 保证：

- 按脚本顺序生成全部 Event 行。
- 使用单调时间记录实际滴声和跳过时间。
- 保留脚本原始计划时间和动作语义。
- 根据同一 Session Clock 锚点生成两个绝对时间字段。
- 正常 Session 生命周期内持续写入，并在结束时形成最终文件。

Android App 不保证：

- `triggered` Event 对应的车辆动作或 CAN 响应一定真实发生。
- Android Clock 与 ASC 天然同源。
- `plan_time_s` 等于实际动作时间。
- `skipped` Event 可以作为动作窗口。
- 仅凭 CSV 即可完成实验有效性或 Signal 语义判断。

## 15. 当前验证状态

2026-09-10 真机生成的 S0001、S0002 CSV 已完成以下检查：

- JSON 与 CSV 均包含 12 个相同 `event_id`，顺序一致。
- 所有具有 `session_script_time_us` 的行，其 `clock_epoch_ms` 按本合同重算误差为 0 毫秒。
- `pending` 行的实际时间字段为空。
- `skipped` 行同时保留触发时间和跳过时间。
- `plan_time_s` 保持采集脚本原始值。

该结果验证了 Android 内部 `Session Clock ↔ script_time ↔ CSV Event Clock` 的换算自洽。CSV 与真实 ASC 的最终联合对齐仍属于任务 9。

