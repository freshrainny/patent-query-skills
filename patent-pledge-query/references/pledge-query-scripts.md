# 质押查询脚本片段（在 mac_computer_use_tool + plane="bu" 的 cell 中运行）

以下代码在 `seed_browser_use` 环境（`import seed_browser_use as bu`）中运行。每个 `mac_computer_use_tool` cell 是独立进程：**变量不跨 cell 保留、bu 附加的 tab 跨 cell 重置**。因此函数定义、切 tab 都要放在同一个 cell 里。

> 环境约束：`bu.js` **不支持 async/await 与 Promise**，所有网络请求一律用**同步 XHR**（`xhr.open(..., false)`），不要用 `fetch`/`then`。

## 0. 专利号归一化与去重（查询前先做）

```python
import re
def norm_app(n):
    s = re.sub(r'[^A-Za-z0-9]', '', str(n))   # 去小数点、空格
    s = re.sub(r'^(CN|ZL)', '', s, flags=re.I) # 去 CN/ZL 前缀
    s = re.sub(r'[ABUS]$', '', s.upper())        # 只删公开号类型字母 A/B/U/S；申请号校验位可能是 X，须保留
    return s

# raw_list: 来自 PSS、公司台账、第三方的全部号码（含申请号与公开号，格式各异）
# 注意：去重应在"申请号"层面做；若清单里同一专利同时有申请号和公开号，先在取号阶段只保留申请号。
app_numbers = list({norm_app(x): x for x in raw_list}.values())
print("去重后专利数：", len(app_numbers))
```

判定同一件专利只能申请号对申请号，**前 13 位一致即同一专利**，末位校验位。PSS 按申请人检索已含共同申请，是公司台账子集，勿当独立批次重复查。

## 1. 打开平台并展开"专利质押"入口

```python
import seed_browser_use as bu
bu.navigate("https://zscq.creditchina.gov.cn/")
bu.wait_for_load(timeout=30)
bu.js("(() => { const l = Array.from(document.querySelectorAll('a')).find(a => a.textContent.trim() === '专利质押'); if (!l) return 'NOT_FOUND'; l.click(); return 'clicked'; })()")
```

## 2. 同一 cell 内：切 tab + 同步 XHR 批量查询（含 HTML 容错与退避）

```python
import seed_browser_use as bu
import json, time

# 每个 cell 先切到 zscq tab（跨 cell 会重置）
tabs = bu.list_tabs()
target = next(t for t in tabs if "zscq.creditchina.gov.cn" in t["url"])
bu.switch_tab(target)
time.sleep(1)

def query_pledge(bu, num, retry=3):
    """同步 XHR 查询单个专利号；返回 dict。触发防护(返回 HTML)时退避重试。"""
    r = None
    for i in range(retry):
        js = ("(() => { const xhr = new XMLHttpRequest();"
              "xhr.open('GET', '/zscq/ip/searchIntellectual?zlh=' + encodeURIComponent('" + str(num) + "') + '&_=' + Date.now(), false);"
              "xhr.send(); const t = xhr.responseText;"
              "try { return JSON.parse(t); } catch (e) { return {html: t.slice(0, 80), status: xhr.status}; } })()")
        r = bu.js(js)
        if isinstance(r, dict) and "html" not in r:   # 拿到 JSON，未触发防护
            return r
        time.sleep(10)                                  # 返回 HTML：退避 10 秒再试
    return r

# 单个 cell 建议 ≤15 个号，timeout_ms=150000~180000
# 每个专利申请号、授权公告号两种格式都查（这里 batch 为待查号子列表）
results = {}
for num in batch:
    results[num] = query_pledge(bu, num)
    print(num, "=>", json.dumps(results[num], ensure_ascii=False)[:200])
    time.sleep(1.5)                 # 每号间隔 1~2 秒，防限流
print("BATCH DONE")
```

大批量（约 150 件）按每批 3~5、间隔 1~2 秒推进，约 20~30 批；进度随时落盘，被防护打断后从断点续查。

## 3. 结果解读：转换为中文可读信息

```python
def interpret_pledge(api_resp):
    """API 返回 -> 质押记录列表（中文），空列表 = 无质押；返回 None = 查询异常需重查"""
    if not isinstance(api_resp, dict) or "html" in api_resp:
        return None
    data = api_resp.get("data", {})
    records = data.get("data")
    if not records:
        return []  # result=0 且无 data = 无质押登记
    out = []
    for rec in records:
        typ = "质押设立" if str(rec.get("type")) == "3" else ("质押注销" if str(rec.get("type")) == "5" else rec.get("type"))
        out.append({
            "类型": typ,
            "出质人": rec.get("czr"),
            "质权人": rec.get("zqr"),
            "质押登记号": rec.get("zydjh"),
            "登记日": rec.get("djr"),
            "注销日": rec.get("djjcr"),
            "公告日": rec.get("swggr"),
        })
    return out
```

## 4. 判断当前是否有效质押

```python
def active_setups(records):
    """有设立记录且其登记号无对应注销记录 => 当前有效质押"""
    setups = [r for r in records if r["类型"] == "质押设立"]
    cancel_ids = {r["质押登记号"] for r in records if r["类型"] == "质押注销"}
    return [s for s in setups if s["质押登记号"] not in cancel_ids]
```

## 5. 取号衔接（PSS / cpquery）

- **按公司取全量**：用 `pss-patent-search`，取 `ap`/`apo`（申请号）字段，不要只取 `pn`（公开号）；PSS 需先登录，token 20~40 分钟过期。
- **按名称少量核实**：用 `patent-status-query` 在 cpquery.cponline.cnipa.gov.cn 取申请号/授权号；型号片段（如 `FWH-3000`）可兜底，短名称 0 条需重试，同批外观申请号连号可交叉核对。
- 本平台**不支持按主体名称查询**：传公司名报"专利号不能为空"，只能逐个专利号。

## 6. 交付甄别

第三方（天眼查/企查查）标注的"专利（申请）权的质押、保全及解除"可能是**法院财产保全**或已注销，并非国知局质押登记；以本平台公示为准。全部专利 100% 查完再下结论，交付时写明总数、已查数、覆盖率与未查项。
