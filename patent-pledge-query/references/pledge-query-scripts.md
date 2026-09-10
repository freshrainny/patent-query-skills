# 质押查询脚本片段（在 mac_computer_use_tool + plane="bu" 的 cell 中运行）

以下代码在 `seed_browser_use` 环境（`import seed_browser_use as bu`）中运行。每个 `mac_computer_use_tool` cell 是独立进程，**跨 cell 后 bu 附加的 tab 会重置**，涉及 fetch 的 cell 必须先切到 zscq tab。

## 1. 打开平台并展开"专利质押"入口

```python
import seed_browser_use as bu
bu.navigate("https://zscq.creditchina.gov.cn/")
bu.wait_for_load(timeout=30)
bu.js("(() => { const l = Array.from(document.querySelectorAll('a')).find(a => a.textContent.trim() === '专利质押'); if (!l) return 'NOT_FOUND'; l.click(); return 'clicked'; })()")
```

## 2. 同一 cell 内：切 tab + 批量查询 API（含 HTML 容错）

```python
import seed_browser_use as bu
import json, time

tabs = bu.list_tabs()
target = next(t for t in tabs if "zscq.creditchina.gov.cn" in t["url"])
bu.switch_tab(target)
time.sleep(1)

def query_pledge(bu, num, retry=3):
    """查询单个专利号的质押记录；返回 dict 或 {'error':...}"""
    for i in range(retry):
        r = bu.js("(async (n) => { try { const resp = await fetch('/zscq/ip/searchIntellectual?zlh=' + encodeURIComponent(n) + '&_=' + Date.now()); const t = await resp.text(); try { return JSON.parse(t); } catch (e) { return {html: t.slice(0, 80), status: resp.status}; } } catch (e) { return {err: e.message}; } })('" + str(num) + "')")
        if isinstance(r, dict) and r.get("status") == 1 and not r.get("html"):
            return r
        time.sleep(2)  # 防护触发时退避重试
    return r

# patents: {名称: [申请号, 授权公告号]}
patents = {
    "涡轴发动机用减速器": ["2025117123789", "CN121841045B"],
    # ... 其余专利
}
results = {}
for name, (app_no, grant_no) in patents.items():
    results[name] = {
        "申请号": query_pledge(bu, app_no),
        "授权号": query_pledge(bu, grant_no),
    }
    time.sleep(0.3)
    print(name, "=>", json.dumps(results[name], ensure_ascii=False)[:300])
```

## 3. 结果解读：转换为中文可读信息

```python
def interpret_pledge(api_resp):
    """API 返回 -> 质押记录列表（中文），空列表 = 无质押"""
    if not isinstance(api_resp, dict) or api_resp.get("status") != 1:
        return None  # 查询异常
    data = api_resp.get("data", {})
    records = data.get("data")
    if not records:
        return []  # result=0 且无 data = 无质押记录
    out = []
    for rec in records:
        typ = "质押设立" if rec.get("type") == "3" else ("质押注销" if rec.get("type") == "5" else rec.get("type"))
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
def has_active_pledge(records):
    """有设立记录且其登记号无后续注销记录 => 当前有效质押"""
    setups = [r for r in records if r["类型"] == "质押设立"]
    cancels = [r for r in records if r["类型"] == "质押注销"]
    cancel_ids = {c["质押登记号"] for c in cancels}
    return [s for s in setups if s["质押登记号"] not in cancel_ids]
```

## 5. 补充：国知局按名称获取申请号（衔接 patent-status-query）

若输入只有专利名称，先按 `patent-status-query` Skill 的流程在国知局（cpquery.cponline.cnipa.gov.cn）查询每个名称的申请号/授权号；注意同批外观设计申请号连号（可交叉核对），短名称偶发 0 条需重试，型号片段可兜底（如搜 `FWH-3000` 找到"无人直升机（大型复合材料FWH-3000）"）。
