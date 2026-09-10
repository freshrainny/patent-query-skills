# patent-query-skills

两个 AI Agent Skill，把「专利法律状态查询」和「专利质押登记查询」的网页操作流程固化下来，让支持 **Computer Use（电脑操作浏览器）** 的 AI Agent 自动、稳定地批量完成查询。

- **patent-status-query**：在国家知识产权局专利审查信息查询系统按申请号/发明名称批量查询案件状态（法律状态）。
- **patent-pledge-query**：在信用中国·知识产权质押信息平台按专利号批量查询质押登记记录（出质人、质权人、质押登记号、当前是否有效）。

## 适用场景

尽职调查、专利尽调中，委托方往往只提供一份专利名称清单，缺少申请号、法律状态和质押信息。传统做法是律师在两个官方网站逐条手工查询，耗时且容易出错。这两个 Skill 把操作流程标准化，AI 加载后即可自动批量查询并整理成表。

## 环境要求

- 支持 Computer Use 的 AI Agent（可自动操作浏览器）。
- **推荐使用国内 AI 平台**，例如豆包 Work、Workbuddy 等。查询目标为国内政务网站（国家知识产权局、信用中国），海外 AI 访问可能存在网络可达性与合规问题。
- Python 3 + `openpyxl`（仅 `patent-status-query/scripts/update_excel_status.py` 更新表格时需要）。

## 安装方法

1. 克隆或下载本仓库：

   ```bash
   git clone https://github.com/freshrainny/patent-query-skills.git
   ```

   或直接在 GitHub 页面点 **Code → Download ZIP** 后解压。

2. 把两个 Skill 目录复制到你的 AI Agent 的**用户技能目录**（`.user_skills`）：

   ```bash
   cp -r patent-query-skills/patent-status-query  <.user_skills 目录>/
   cp -r patent-query-skills/patent-pledge-query  <.user_skills 目录>/
   ```

   常见位置（按你的实际环境选择）：

   - 豆包桌面端 Agent 环境：`~/Library/Application Support/Doubao/.../workspace/.user_skills/`
   - 其他 Agent 环境：其配置中的用户技能目录

3. 重启或刷新 AI 对话后，Skill 即被识别。

## 使用方法

直接用自然语言向 AI 下达任务即可，例如：

- "根据表格里的专利清单，帮我批量查询每件专利的法律状态（案件状态），并更新到表格里。"
- "查一下这批专利在信用中国质押平台有没有质押登记，有质押的列出来质权人和登记号。"

首次使用时，国家知识产权局查询系统会跳转统一身份认证页面，需要**本人完成一次登录**（扫码/验证码），之后 AI 即可继续自动操作。

## 目录结构

```
patent-query-skills/
├── patent-status-query/
│   ├── SKILL.md                       # 法律状态查询工作流
│   ├── references/query-scripts.md    # 可复制的浏览器查询代码片段
│   └── scripts/update_excel_status.py # 查询结果回写 Excel（自动备份+校验）
└── patent-pledge-query/
    ├── SKILL.md                       # 质押登记查询工作流
    └── references/pledge-query-scripts.md
```

## 数据来源与注意事项

- 法律状态数据来源：国家知识产权局专利审查信息查询系统（cpquery.cponline.cnipa.gov.cn）。
- 质押数据来源：信用中国·知识产权质押信息平台（zscq.creditchina.gov.cn，数据源自国家知识产权局质押登记公示）。
- 查询结果以官方网站实时公示为准，提交正式报告前建议复核或重新查询。
- AI 批量结果建议人工抽查，尤其是提示存在质押、案件状态异常（驳回、失效等）的专利。
- 涉及国知局统一身份认证的步骤必须由本人完成，AI 不代填账号密码。

## 许可

仅作内部工作流参考使用；网站界面与接口以官方实际页面为准。
