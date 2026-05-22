# Care Plan Generation System — Design Doc

> **状态**: Draft v0.1 (Day 1)
> **作者**: [你的名字]
> **最后更新**: Day 1
> **说明**: 这是项目启动阶段的设计文档,会随着开发推进持续迭代。

---

## 1. 背景与问题 (Background & Problem)

一家专科药房 (specialty pharmacy) 的药剂师目前需要**手动**为每位患者编写 care plan,每位患者耗时 **20-40 分钟**。这项工作是合规要求(Medicare 和 pharma 报销所需),不可省略。药房目前严重缺人,该任务大量积压。

**我们要解决的问题**: 把 care plan 的编写过程自动化,把药剂师从重复性文书工作中解放出来。

---

## 2. 目标与非目标 (Goals & Non-Goals)

### 2.1 目标

- 让医疗工作者通过 Web 表单录入患者信息,系统自动生成 care plan。
- 系统能检测重复的患者、重复的订单、重复的 provider。
- 所有输入都经过验证,保证进入系统的数据是干净的。
- 错误处理安全、清晰、可控,不泄露患者隐私 (PHI)。
- 项目可被 clone 下来开箱即跑通 (end-to-end)。

### 2.2 非目标 (Out of Scope — 防止 scope creep)

- 不做患者端界面(患者不直接使用本系统)。
- 不做 care plan 的医学正确性校验(医学内容由 LLM 生成,由药剂师人工把关)。
- Phase 1 不做多数据源接入(其他医疗机构通过 API/XML 接入,属于后期迭代)。
- Phase 1 不做生产级监控告警(后期迭代)。

---

## 3. 目标用户与核心场景 (Users & Core Scenario)

### 3.1 用户

本系统的用户是 **CVS 的医疗工作者**。患者不接触本系统。医疗工作者在为患者开药时需要一份 care plan,生成后会**打印出来交给患者**。

### 3.2 核心用户场景

> 一个医疗工作者坐在电脑前 → 把患者信息填进表单 → 提交 → 拿到一份 care plan → 打印交给患者。

本质上是一条 **输入 → 输出** 的链路。所有功能都围绕这条核心链路展开。

---

## 4. 需求规格 (Requirements)

### 4.1 输入字段 (来自需求文档 1.1)

| 字段 | 类型 | 格式约束 (需求文档明确给出的) |
| --- | --- | --- |
| Patient First Name | string | — |
| Patient Last Name | string | — |
| Referring Provider | string | — |
| Referring Provider NPI | number | **10 位数字** |
| Patient MRN | number | **唯一,6 位数字** |
| Patient Primary Diagnosis | ICD-10 code | ICD-10 格式 |
| Medication Name | string | — |
| Additional Diagnosis | list of ICD-10 codes | ICD-10 格式 |
| Medication History | list of strings | — |
| Patient Records | string 或 PDF | — |

> **说明**: 需求文档 1.1 只给出了字段类型和上述格式约束,**未说明哪些字段必填、哪些可选**。本文档不擅自假设,该问题列入 §9 待澄清问题。

### 4.2 Care Plan 规则 (来自需求文档 1.4)

- **一个 care plan 对应一个订单(一种药物)。**
- Care plan 输出**必须包含**以下四个板块:
  - Problem list (Drug therapy problems)
  - Goals (SMART)
  - Pharmacist interventions / plan
  - Monitoring plan & lab schedule

### 4.3 重复检测规则 (来自需求文档 1.4)

| 场景 | 处理方式 | 原因 |
| --- | --- | --- |
| 同一患者 + 同一药物 + **同一天** | **ERROR** — 必须阻止 | 肯定是重复提交 |
| 同一患者 + 同一药物 + **不同天** | **WARNING** — 可确认后继续 | 可能是续方 |
| MRN 相同,但名字或 DOB 不同 | **WARNING** — 可确认后继续 | 可能是录入错误 |
| 名字 + DOB 相同,但 MRN 不同 | **WARNING** — 可确认后继续 | 可能是同一人 |
| NPI 相同,但 Provider 名字不同 | **ERROR** — 必须修正 | NPI 是全国唯一标识 |

> **设计说明**: ERROR 会阻止提交,WARNING 允许用户确认后继续。这个区别会在 API 层用不同的方式表达(详见 §6)。

### 4.4 功能需求 (来自需求文档 1.4)

| 功能 | 优先级 | 说明 |
| --- | --- | --- |
| 患者 / 订单重复检测 | Must-have | 不能打乱现有工作流 |
| Care Plan 生成 | Must-have | 系统核心价值 |
| Provider 重复检测 | Must-have | 影响 pharma 报告 |
| 导出报告 (用于 pharma reporting) | Must-have | pharma 报告需要 |
| Care Plan 下载 (文本文件) | Must-have | 用户需上传到自己的系统 |

### 4.5 Production-Ready 要求 (来自需求文档 1.1)

- 每个输入都被验证。
- 完整性规则始终强制执行一致性。
- 错误安全、清晰、可控。
- 代码模块化、易导航。
- 关键逻辑有自动化测试覆盖。
- 项目开箱即跑通 (end-to-end)。

---

## 5. 技术栈 (Tech Stack)

| 类别 | 选型 | 说明 |
| --- | --- | --- |
| 后端 | Python / Django / Django REST Framework | Web 框架与 API 开发 |
| 前端 | React | 用户界面 |
| 数据库 | PostgreSQL | 数据存储 |
| 异步任务(本地) | Celery + Redis | 本地后台任务 |
| 异步任务(云端) | AWS SQS + Lambda | 生产环境后台任务 |
| AI / LLM | Claude API 或 OpenAI API | Care plan 生成 |
| 容器化 | Docker / Docker Compose | 本地开发与部署 |
| 云部署 | AWS (Lambda, RDS, SQS, API Gateway) | 生产环境 |
| 基础设施 | Terraform | Infrastructure as Code |
| 监控 | Prometheus + Grafana / CloudWatch | 指标收集与可视化 |
| 测试 | pytest | 单元测试与集成测试 |

---

## 6. 系统设计 (System Design)

### 6.1 核心 API 设计

围绕核心场景"提交信息 → 拿结果",设计两个核心 API:

| API | 方法 | 作用 |
| --- | --- | --- |
| `/api/orders/` | POST | 提交患者信息,请求生成 care plan |
| `/api/orders/{id}` | GET | 查询某个订单 / care plan 的状态和内容 |

- **POST** 发送的内容: 患者信息、provider、诊断、药物、病历等(见 §4.1)。
- **GET** 返回的内容: 订单状态 (`pending` / `processing` / `completed` / `failed`),以及在 `completed` 时返回 care plan 内容。

### 6.2 Care Plan 状态机

```
pending → processing → completed
                     ↘ failed
```

只有 `completed` 状态时,前端才展示 care plan 内容。

### 6.3 数据存储(初步设想,Day 3 细化)

初步规划拆成四张表,通过外键关联(具体设计 Day 3 确定):

- **Patient** — 患者信息(姓名、MRN、DOB)
- **Provider** — 医生信息(姓名、NPI)
- **Order** — 订单(关联 Patient 和 Provider、药物、诊断、病历)
- **CarePlan** — care plan(关联 Order、内容、状态)

### 6.4 错误处理设计原则

系统区分三类"不正常"情况:

| 类型 | 例子 | 处理 |
| --- | --- | --- |
| 输入格式错误 | NPI 不是 10 位 | 拒绝,返回错误 |
| 业务规则阻止 (ERROR) | 同一 NPI 对应不同 provider 名字 | 阻止提交 |
| 业务警告 (WARNING) | 可能重复的患者 | 提示,允许用户确认后继续 |

> 错误信息不得包含 stack trace 或患者隐私 (PHI)。具体的统一错误处理方案在后续迭代细化。

---

## 7. 开发计划与范围划分 (Roadmap)

### Phase 1 — MVP (核心链路跑通)

- 前端表单 + 后端 API + LLM 调用,能完成"提交 → 生成 → 拿到 care plan"。
- 此阶段暂不做: 输入验证、重复检测、异步处理、自动化测试。

### Phase 2 — Production-Ready 加固

- 数据库设计、异步处理(消息队列 + Worker)、前端状态同步。
- 输入验证、重复检测、统一错误处理、自动化测试。
- 代码分层重构、多数据源适配。

### Phase 3 — 部署与运维

- Docker 容器化、AWS 部署、Terraform 管理基础设施、监控。

---

## 8. 风险与未知 (Risks & Unknowns)

| 风险 / 未知 | 说明 | 应对 |
| --- | --- | --- |
| LLM 不可靠 | LLM 可能调用失败,或生成不完整 / 错误的内容 (hallucination) | 需要 error handling + 重试机制;care plan 由药剂师人工把关 |
| 新技术学习成本 | Docker、Celery、AWS、Terraform 均为首次接触 | 学习时间已显式排进开发计划 |
| 需求模糊点 | 部分细节需与客户进一步澄清 | 见 §9 |
| 排期不确定性 | 新人估时偏乐观 | 估时基础上预留 20-30% buffer |

---

## 9. 待澄清问题 (Open Questions)

> 需求文档 1.4 已经统一了主要规则。以下是仍建议与客户确认的点:

- **输入字段中,哪些是必填、哪些可选?** 需求文档 1.1 未作说明(例如 Patient Records、Additional Diagnosis、Medication History 是否允许为空)。
- WARNING 之后,用户确认继续提交的具体交互流程是怎样的?
- "导出报告" 的具体格式要求是什么?需要包含哪些字段?
- Patient Records 以 PDF 上传时,系统是否需要解析 PDF 内容,还是仅作存档?
- care plan 生成后,是否需要药剂师在系统内审核 / 修改?

---

## 10. 附录: 示例数据

输入与输出的示例数据见需求文档 1.1 的"示例数据"一节(IVIG / myasthenia gravis 患者案例)。
