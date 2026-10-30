# 查询脚本片段（在 mac_computer_use_tool + plane="bu" 的 cell 中运行）

以下代码在 `seed_browser_use` 环境（`import seed_browser_use as bu`）中运行。每个 `mac_computer_use_tool` cell 是独立进程，cell 内的变量不跨 cell 保留，因此把需要的函数定义在同一个 cell 里。

## 1. 提取结果 JS（核心）

```python
EXTRACT_JS = """(() => {
  const info = document.querySelector('.table_info');
  const totalMatch = document.body.textContent.match(/共查询到\\s*(\\d+)\\s*条结果/);
  if (!info) return {found: false, total: totalMatch ? totalMatch[1] : null};
  const text = info.textContent;
  const statusMatch = text.match(/案件状态：([^\\n]+?)(?=授权公告日|$)/);
  const numMatch = text.match(/申请号\\/专利号：\\s*([A-Za-z0-9]+)/);
  const nameMatch = text.match(/发明名称：([^\\n]+?)(?=申请人：|$)/);
  const appMatch = text.match(/申请人：([^\\n]+?)(?=专利类型：|$)/);
  return {
    found: true, total: totalMatch ? totalMatch[1] : null,
    status: statusMatch ? statusMatch[1].trim() : null,
    num: numMatch ? numMatch[1] : null,
    name: nameMatch ? nameMatch[1].trim() : null,
    app: appMatch ? appMatch[1].trim() : null
  };
})()"""
```

## 2. 清空全部字段并设置指定字段

`idx=0` 是申请号/专利号，`idx=1` 是发明名称，`idx=2` 是申请人。**每次查询前必须清空全部字段**（残留字段会以 AND 逻辑过滤导致 0 结果）。

```python
def set_field(bu, idx, val):
    bu.js("((args) => { const inputs = document.querySelectorAll('input[id^=\"f_\"]'); " +
          "const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; " +
          "for (let i = 0; i < Math.min(inputs.length, 5); i++) { setter.call(inputs[i], ''); inputs[i].dispatchEvent(new Event('input', {bubbles: true})); } " +
          "const input = inputs[args.idx]; if (!input) return 'NO_INPUT'; " +
          "setter.call(input, args.val); input.dispatchEvent(new Event('input', {bubbles: true})); return 'ok'; })" +
          '("{"idx":' + str(idx) + ',"val":"' + str(val) + '"}")')
```

## 3. 点击查询按钮

```python
def click_query(bu):
    bu.js("(() => { const btn = Array.from(document.querySelectorAll('button'))" +
          ".find(b => b.textContent.includes('查询') && b.textContent.includes('search')); " +
          "if (!btn) return 'NO_BTN'; btn.click(); return 'clicked'; })()")
```

## 4. 申请号归一化（查询与比对共用）

```python
import re
def norm(n):
    s = str(n).strip()
    if re.match(r'^[A-Za-z]{2}', s):   # 去掉 ZL 等前两位字母前缀
        s = s[2:]
    s = re.sub(r'[^A-Za-z0-9]', '', s) # 去掉点、空格等
    return s.upper()
```

申请号（13 位数字 + 校验位）与公开号/授权公告号（`CN`+数字+末位类型字母 A/B/U/S）是两套编码，不能直接比数字；判定同一专利只按申请号、前 13 位一致即同一专利。多来源清单按归一化申请号去重，避免重复查询：

```python
uniq = list({norm(x): x for x in raw_numbers}.values())
```

## 5. 单条查询（含校验与重试）

```python
def query_one(bu, num, max_try=2):
    for _ in range(max_try):
        set_field(bu, 0, num)
        click_query(bu)
        time.sleep(3.5)
        r = bu.js(EXTRACT_JS)
        if r.get('found') and norm(r.get('num') or '') == norm(num):
            return r
        time.sleep(2.0)
    return {'error': 'NOTFOUND', 'total': r.get('total'), 'num': r.get('num'), 'status': r.get('status')}
```

## 6. 批量查询主循环

单 cell 处理 6~8 个，`timeout_ms` 设 150000~180000。

```python
import seed_browser_use as bu
import time, re

# 把上面 1-5 的函数定义放在这里（同一 cell 内）

numbers = ["2026104975588", "202610437475.X", "ZL2026104726903"]  # 原样抄表，含 ZL/点
results = {}
for n in numbers:
    results[n] = query_one(bu, n)
    print(n, "=>", results[n])
    time.sleep(1.0)
print("DONE")
```

## 7. 查无结果 → 发明名称搜索兜底

申请号查询 `total=0` 时，用表格中的发明名称搜索核实：

```python
set_field(bu, 0, "")            # 清空申请号
set_field(bu, 1, "桨叶静强度测试装置")  # 设置发明名称
click_query(bu)
time.sleep(4)
r = bu.js(EXTRACT_JS)
# 核对 r['name'] 与表格专利名称一致、r['app'] 与表格申请人一致，再采信 r['status']
```

## 8. 更新 Excel 法律状态列

浏览器侧收集完成后，用独立脚本更新表格（不在浏览器 cell 中做）：

```bash
python3 scripts/update_excel_status.py --file /path/表格.xlsx --mapping /path/status_map.json
```

`status_map.json` 为行号(字符串)到状态的映射：`{"2": "等待实审提案", "3": "进入审查", ...}`。脚本默认写第 6 列（F 列），可用 `--column` 改；默认自动备份原文件到同目录 `<原名>_备份_<日期>.xlsx`。
