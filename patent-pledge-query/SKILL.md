---
name: patent-pledge-query
description: 查询中国专利的质押登记情况（知识产权质押信息公示），通过信用中国·知识产权质押信息平台（zscq.creditchina.gov.cn）按专利号检索专利质押登记记录并解读出质人/质权人/质押登记号/登记日与当前是否有效。适用于：用户要求查询一批专利的"质押情况/质押登记/质押状态/是否质押"、提供 zscq.creditchina.gov.cn 链接或"信用中国质押平台"等表述、表格中的专利需要标注质押信息时。常与 patent-status-query（按名称从国知局获取申请号）衔接使用。
---

# 专利质押记录查询

通过 CNGC Browser Use（`mac_computer_use_tool` + `plane="bu"` + `seed_browser_use`）在信用中国·知识产权质押信息平台检索专利质押登记记录。

## 前置：准备专利号

质押平台按**专利号/申请号**查询，不按名称。若输入只有专利名称（常见于用户表格），先用 `patent-status-query` Skill 在国知局查询系统（cpquery.cponline.cnipa.gov.cn）按名称获取每个专利的**申请号 + 授权公告号**，再执行本流程。

- 外观设计名称常带型号变体（括号、空格），如"无人直升机（大型复合材料 FWH-3000）"实际库中名称为"无人直升机（大型复合材料FWH-3000）"（无空格）；按型号片段（如 `FWH-3000`）搜索可兜底。
- 短名称（如"涡轴发动机"）单独搜索偶发返回 0 条，重试即可；或用"名称 + 申请人"组合条件，注意申请人条件有时不生效，可翻页核对。
- 同批外观设计申请号通常连续（如同一公司 2025-09-30 申请的 2025305886xxx 连号段），可据此交叉核对。

## 核心工作流

### 1. 打开平台并找到查询入口

```python
import seed_browser_use as bu
bu.navigate("https://zscq.creditchina.gov.cn/")
bu.wait_for_load(timeout=30)
```

首页"知识产权质押信息查询"→"专利质押"是**无 href 的 JS 折叠入口**（`bu.find` 找不到，用 JS 点击）：

```python
bu.js("(() => { const l = Array.from(document.querySelectorAll('a')).find(a => a.textContent.trim() === '专利质押'); if (!l) return 'NOT_FOUND'; l.click(); return 'clicked'; })()")
```

页面中存在多个隐藏搜索框（信用信息/专利质押/商标质押），专利质押输入框的 placeholder 为"请输入专利质押专利号"。**不要依赖 UI 逐条查询**，直接走 API（第 2 步）。

### 2. 批量调用查询 API（推荐，无需逐条 UI 操作）

核心接口（页面同域调用，返回 JSON）：

```
GET https://zscq.creditchina.gov.cn/zscq/ip/searchIntellectual?zlh=<专利号>&_=<时间戳>
```

- `data.result == 0` 且无 `data.data` → **该专利无质押登记记录**
- `data.data` 为数组 → 存在质押登记记录，逐条解析（字段见第 3 步）

**关键：必须在 zscq 域名页面上下文执行 fetch。** `bu` 跨 cell 后附加的 tab 会重置（新 cell 是独立进程），相对路径 fetch 可能被解析到国知局等其他 tab 导致返回国知局 HTML。**每个 cell 内先切 tab 再调用**：

```python
tabs = bu.list_tabs()
target = next(t for t in tabs if "zscq.creditchina.gov.cn" in t["url"])
bu.switch_tab(target)
import time; time.sleep(1)
# 然后 bu.js(fetch...) 调用 API
```

每个专利建议**申请号 + 授权公告号两种格式都查**（平台对两者都能匹配，双查更全面）。

### 3. 解析质押记录

每条记录字段（数据库列名，非中文）：

| 字段 | 含义 | 示例 |
|---|---|---|
| `zlh` | 专利号 | 2022106460997 |
| `czr` | 出质人 | 北京航景创新科技有限公司 |
| `zqr` | 质权人 | 北京中关村银行股份有限公司 |
| `zydjh` | 质押登记号（Y 开头） | Y2025980028553 |
| `type` | 记录类型：`3`=质押设立，`5`=质押注销 | 3 |
| `djr` | 设立登记日（YYYYMMDD） | 20250716 |
| `djjcr` | 注销登记日（仅注销记录） | 20250620 |
| `swggr` | 事务公告日 | 20250801 |
| `tname` | 表名：`zscq_zlzyclsj_sx`=设立，`zscq_zlzyclsj_zx`=注销 | zscq_zlzyclsj_sx |

**判断当前是否有效质押**：存在 `type=3`（设立）记录，且同一质押登记号无后续 `type=5`（注销）记录 → 当前有效；有对应注销记录 → 已解除。

### 4. 汇总与交付

- 输出按专利逐条列示：无记录填"无质押登记"；有记录列出质人、质权人、登记号、登记日、当前是否有效。
- 用户偏好直接回复结果；需要写表格时先备份、只更新质押列、回读验证（可复用 patent-status-query 的 `scripts/update_excel_status.py` 思路）。

## 关键陷阱清单

1. **跨 tab 上下文**（最高频错误）：`bu` 附加的 tab 跨 cell 重置；fetch 相对路径会落在错误域名。同一 cell 内先 `list_tabs → switch_tab(zscq)` 再调 API。
2. **连续快速调用触发防护**：返回 HTML（`<!DOCTYPE ...`）而非 JSON。解析时先 `resp.text()` 再 `JSON.parse` 容错；遇 HTML 稍等 1~3 秒重试，或单次查询后 sleep 0.3 秒。
3. **专利号必须准确**：号码来自国知局按名称查询结果；申请号与授权号都查一遍。
4. **勿用 UI 逐条查询**：平台结果页渲染不稳，API 调用更快更可靠；UI 仅用于首次确认入口与字段。
5. **result 字段含义**：`result=0` 是查询成功的"无数据"，不是错误；`result=1` 才会跳登录（本平台公众查询无需登录）。
6. **数据来源**：平台数据来源为国家知识产权局质押登记公示，字段为系统列名（czr/zqr 等），向用户交付时翻译成中文。
