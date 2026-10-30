---
name: patent-pledge-query
description: 查询中国专利的质押登记情况（知识产权质押信息公示），通过信用中国·知识产权质押信息平台（zscq.creditchina.gov.cn）按专利号检索专利质押登记记录并解读出质人/质权人/质押登记号/登记日与当前是否有效。适用于：用户要求查询一批专利的"质押情况/质押登记/质押状态/是否质押"、提供 zscq.creditchina.gov.cn 链接或"信用中国质押平台"等表述、表格中的专利需要标注质押信息时。动手前必须先统一专利号口径（申请号 vs 公开号）并去重。常与 patent-status-query 或 pss-patent-search（取申请号）衔接使用。
---

# 专利质押记录查询

通过 CNGC Browser Use（`mac_computer_use_tool` + `plane="bu"` + `seed_browser_use`）在信用中国·知识产权质押信息平台检索专利质押登记记录。

## 第 0 步：统一专利号口径并去重（动手前必做，最高优先级）

一次真实尽调中，因混淆两套编号导致约 69 件专利被重复查询，务必先做这一步。

### 两套编号不是一回事

| 编号 | 结构 | 示例 | 说明 |
|---|---|---|---|
| 申请号 | 13 位数字 + 1 位校验位；带前缀时为 `CN` + 数字 + 小数点 + 校验位 | `2022213054739` / `CN202221305473.9` | 专利的"身份证"，比对、去重只能用它 |
| 公开号 / 授权公告号 | `CN` + 7~8 位数字 + 类型字母 | `CN217624090U` | 每次公开/授权各有一个号，与申请号无数字对应关系 |

公开号末位类型字母：`A`=发明公布、`B`=发明授权、`U`=实用新型授权、`S`=外观设计授权。

### 判定与去重规则

1. **只能申请号对申请号**：把公开号和申请号直接比数字必然对不上，会误判"不重合"。同一专利的申请号**前 13 位一致即同一件**，末位是校验位。
2. **多来源清单先归一化再去重**：PSS 检索结果、公司台账、第三方平台导出的号码格式各异（`CN`/`ZL` 前缀、小数点、空格、类型后缀），统一归一化后用集合去重，得到唯一申请号清单。
3. **PSS 按申请人检索已包含共同申请**：以"申请人=某公司"在 PSS 检索，结果同时含该公司单独申请与共同申请，本就是公司台账的**子集**，不要把它当成独立的第二批重复查询。
4. 归一化函数（去 `CN`/`ZL` 前缀、去小数点与空格、去末尾类型字母，统一大写）：

```python
import re
def norm_app(n):
    s = re.sub(r'[^A-Za-z0-9]', '', str(n))   # 去点、空格
    s = re.sub(r'^(CN|ZL)', '', s, flags=re.I)
    s = re.sub(r'[ABUS]$', '', s.upper())       # 只删公开号类型字母 A/B/U/S；申请号校验位可能是 X，须保留
    return s
uniq = {norm_app(x): x for x in raw_list}      # dict 天然按归一化结果去重
```

## 前置：准备专利号（两条路径，取"申请号"字段）

质押平台按**专利号/申请号**查询，不按名称，也不按主体名称。若输入只有专利名称或公司名，先取号：

- **路径 A（推荐，适合按公司批量取全量）**：用 `pss-patent-search` Skill 在 PSS（pss-system.cponline.cnipa.gov.cn）按申请人检索，取记录里的 **`ap`（纯数字申请号）/ `apo`（带 CN 与点的申请号）字段**，不要只取 `pn`（公开号）。PSS 需用户先登录，token 约 20~40 分钟过期，取数要一次快速完成。
- **路径 B（适合少量按名称核实）**：用 `patent-status-query` Skill 在国知局查询系统（cpquery.cponline.cnipa.gov.cn）按名称获取申请号 + 授权公告号。
  - 外观名称常带型号变体（括号、空格），按型号片段（如 `FWH-3000`）可兜底；短名称偶发 0 条需重试；同批外观申请号通常连号，可交叉核对。

取号后回到第 0 步去重，再进入查询。

## 1. 打开平台并找到查询入口

```python
import seed_browser_use as bu
bu.navigate("https://zscq.creditchina.gov.cn/")
bu.wait_for_load(timeout=30)
```

首页"知识产权质押信息查询"→"专利质押"是**无 href 的 JS 折叠入口**（`bu.find` 找不到，用 JS 点击）：

```python
bu.js("(() => { const l = Array.from(document.querySelectorAll('a')).find(a => a.textContent.trim() === '专利质押'); if (!l) return 'NOT_FOUND'; l.click(); return 'clicked'; })()")
```

页面存在多个隐藏搜索框，专利质押输入框 placeholder 为"请输入专利质押专利号"。**不要依赖 UI 逐条查询，直接走 API（第 2 步）。**

## 2. 批量调用查询 API（用同步 XHR，不要用 async/Promise）

核心接口（页面同域，返回 JSON）：

```
GET https://zscq.creditchina.gov.cn/zscq/ip/searchIntellectual?zlh=<专利号>&_=<时间戳>
```

- `data.result == 0` 且无 `data.data` → **该专利无质押登记记录**（`result=0` 是查询成功的"无数据"，不是报错）。
- `data.data` 为数组 → 存在质押登记记录，逐条解析（字段见第 4 步）。

### 关键约束：`bu.js` 不支持 async/await 与 Promise

在该 Browser Use 环境，`bu.js` 里写 `async`/`await`/`fetch().then()` 不会按预期返回。**一律用同步 XHR（`xhr.open(..., false)`）**，完整可复制代码见 [references/pledge-query-scripts.md](references/pledge-query-scripts.md)。最小示例：

```python
def query_pledge(bu, num):
    js = ("(() => { const xhr = new XMLHttpRequest();"
          "xhr.open('GET', '/zscq/ip/searchIntellectual?zlh=' + encodeURIComponent('" + str(num) + "') + '&_=' + Date.now(), false);"
          "xhr.send(); const t = xhr.responseText;"
          "try { return JSON.parse(t); } catch (e) { return {html: t.slice(0, 80), status: xhr.status}; } })()")
    return bu.js(js)
```

### 跨 cell 必须先切 tab

`bu` 附加的 tab 跨 cell 后会重置（新 cell 是独立进程），相对路径可能被解析到其他 tab。**每个 cell 内先切 tab 再调用**：

```python
tabs = bu.list_tabs()
target = next(t for t in tabs if "zscq.creditchina.gov.cn" in t["url"])
bu.switch_tab(target)
import time; time.sleep(1)
```

每个专利建议**申请号 + 授权公告号两种格式都查**（平台对两者都能匹配，双查更全面）。

## 3. 频率控制与反爬防护（决定能否跑完全量）

平台有动态防护，连续快速调用会返回 HTML（反爬页）而非 JSON，频繁时浏览器会无响应/超时。实测稳定节奏：

1. **每批 3~5 个专利，每个间隔 1~2 秒**；150 件左右约需 20~30 批。环境顺畅时可短暂提到每批 10 个，一旦出现 HTML 立即降回 3 个。
2. 单个 `mac_computer_use_tool` cell 控制在能稳定完成的条数（建议 ≤15 个号），`timeout_ms` 设 150000~180000，避免整 cell 超时丢进度。
3. 解析先取 `responseText` 再 `JSON.parse` 容错；返回 HTML（含 `<!DOCTYPE`）时**等待约 10 秒退避后重试**，不要硬刷。
4. 浏览器被防护打到无响应时，先等待恢复、确认 `list_tabs` 正常，再从断点继续；进度实时落盘（每查完一个号就记录），便于断点续查。

## 4. 解析质押记录

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

## 5. 不支持按"主体名称/公司名"查询

- 页面上的"主体名称"输入框不能用于本 API：接口只认 `zlh=<专利号>`，传公司名会报"专利号不能为空"。
- "信用查询"区域按公司名也查不到专利质押登记。**没有按出质人一次性拉全量的捷径，必须逐个专利号查询。**

## 6. 汇总、交付与覆盖率纪律

- 逐条列示：无记录填"无质押登记"；有记录列出质人、质权人、登记号、登记日、当前是否有效，字段翻译成中文。
- **必须 100% 查完再下结论**：不能因已抽查的部分全部无记录就推断"大概率无质押"。交付时写明**专利总数、实际查询数、覆盖率、未查项及原因**；确实被防护阻断时如实标注，恢复后补查。
- 写表格时先备份、只更新质押列、回读验证（可复用 patent-status-query 的 `scripts/update_excel_status.py` 思路）。
- **甄别第三方平台标注**：天眼查/企查查写的"专利（申请）权的质押、保全及解除"不等于国知局质押登记，可能是**法院财产保全**（不在本平台范畴）或质押已注销解除。一切以信用中国平台实时公示为准，结论中区分这两类来源。

## 关键陷阱清单

1. **专利号口径混淆**（最高频、代价最大）：公开号当申请号比对 → 误判不重合、重复查询。先做第 0 步，只按申请号去重。
2. **`bu.js` 用 async/Promise 失败**：该环境不支持，必须同步 XHR。
3. **跨 tab 上下文丢失**：每个 cell 先 `list_tabs → switch_tab(zscq)` 再调 API。
4. **频率过快触发防护**：返回 HTML 而非 JSON；每批 3~5、间隔 1~2 秒，遇 HTML 退避 10 秒。
5. **误以为能按主体名称查**：API 只认专利号，无公司名批量入口。
6. **`result` 含义**：`result=0`=成功且无数据，不是错误；`result=1` 才会跳登录（本平台公众查询无需登录）。
7. **第三方"质押/保全"标注误导**：可能是财产保全或已注销，以本平台为准。
8. **PSS 取号只取了公开号**：务必取 `ap`/`apo` 申请号字段；PSS 登录态易过期，取数从速。
9. **数据来源**：平台数据源自国家知识产权局质押登记公示，向用户交付时把列名（czr/zqr 等）翻译成中文。
