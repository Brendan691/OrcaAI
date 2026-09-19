# 🐳 小鲸 OrcaAI

**面向海事知识管理的可追溯 RAG 知识库**

浏览网页时一键收藏文章/报告,AI 自动打标签分类,随时用自然语言提问,并拿到**能点回原文的带定位引用**。
内核与领域无关 —— 航运只是当前加载的一个「领域包」,换包即可服务其他行业。

当前版本 **`v0.4.0-alpha`** · 变更见 [CHANGELOG.md](CHANGELOG.md) · 规划见 [ROADMAP.md](ROADMAP.md)

> 🧭 想了解"为什么这么设计",读 [CONTEXT.md](CONTEXT.md)(领域词汇表)与 [docs/adr/](docs/adr/)(0001–0010 架构决策记录)。

**目录**

- [这个项目解决什么](#这个项目解决什么)
- [系统架构](#系统架构通用内核--领域包)
- [检索链路](#检索链路从提问到带定位引用)
- [快速开始](#快速开始本地零依赖无需-docker)
- [功能一览](#功能一览)
- [API 速查](#api-速查)
- [配置项](#配置项)
- [代码结构](#代码结构)
- [技术栈](#技术栈)
- [测试](#测试)
- [生产部署](#生产部署可选)
- [已知限制](#已知限制)

---

## 这个项目解决什么

日常我们会看到很多专业文章、报告、新闻,通常的结局是:加书签 → 再也不看 → 要用时找不到。

小鲸 OrcaAI:

1. **一键收藏** —— 浏览器里点一下,自动抓取正文入库(公众号文章有专用采集器)。
2. **AI 自动打标签** —— 按领域标签体系四维分类(业务类型 / 地理区域 / 主题类别 / 事件性质),无需手动整理。
3. **自适应检索(AEF)** —— 按查询动态分配向量、关键词、时间、标签的权重;元数据缺失时自动门控该信号,再做加权 RRF 融合与去重。
4. **专用精排(CARE)** —— 对前 10 个候选调用 `gte-rerank-v2` 交叉编码器,按两路排序的置信度间隔逐查询计算融合权重;无 Key 或调用异常时自动回退 AEF。
5. **可追溯问答** —— 回答里的角标绑定到具体文档 / 切片 / 字符范围 / 行号,能跳回原文位置。
6. **AI 报告** —— 基于知识库生成周度市场简报、航线风险预警、公约更新解读。

**适用场景:** 写论文找资料、行业调研、追踪动态、整理专业知识。

---

## 系统架构(通用内核 + 领域包)

```
┌─ 采集入口 ─────────────────────────────────────────────────────────────┐
│ Chrome 插件 / 文件上传 / 粘贴文本 / 微信文章链接                           │
└─────────────────────────────┬──────────────────────────── ────────────┘
                              ▼
┌─ 入库流水线(通用内核,领域无关) ────────────────────────────────────────┐
│ 采集器 ─▶ 清洗切片 ─▶ 向量化 ─▶ Chroma 向量库 + SQLite 元数据           │
│ 网页·公众号   字符+行号   embedding    切片对象:字符偏移 / 标签 / 时间    │
└─────────────────────────────┬──────────────────────────────────────┘
                              ▼
┌─ 检索流水线(通用内核,领域无关) ────────────────────────────────────────┐
│ 入口:Next.js Web 前端 / Chrome 插件                                  │
│ 本地:AEF 混合检索(BM25 + 向量 + 标签,信号可靠性门控)                    │
│ 联网:Tavily 托管搜索(缺 Key / 超时 / 失败时降级 Bing)                  │
│       └─▶ 证据选择(跨源去重 + 多样性) ─▶ CARE 重排(gte-rerank-v2)      │
│              置信度自适应融合;无 Key / 异常时自动回退 AEF 排序           │
└─────────────────────────────┬──────────────────────────────────────┘
                              ▼
┌─ 生成与回溯(通用内核,领域无关) ────────────────────────────────────────┐
│ RAG 问答 / AI 报告(周报 · 风险预警 · 公约解读)                         │
│       └─▶ 带定位引用:文档 · 切片 · 字符范围 · 行号                      │
└────────────────────────────────────────────────────────────────────┘

        ┌─ 领域包(可替换) ─────────────────────────────┐
        │ maritime:标签体系 / 分类提示词 / 报告模板      │
        │ example :空模板,用于验证领域可切换             │
        └────────────────────────────────────────────┘
                 ▲ 内核按协议读取领域包,实现换包即换行业

模型:通义千问(打标签·问答·报告) · text-embedding-v3(向量) · gte-rerank-v2(重排) · Tavily(联网)
```

- **通用内核**:采集、切片、向量化、知识库、AEF 混合检索、联网搜索、证据选择、CARE 重排、RAG 问答与报告生成 —— 不含任何"航运"字样。
- **领域包** `backend/src/domains/maritime/`:标签体系、分类提示词、报告模板。换包即换行业(见 `domains/example/` 空模板)。
- **外部服务**:通义千问负责打标签、问答和报告;`text-embedding-v3` 负责向量化;`gte-rerank-v2` 负责 CARE 重排;Tavily 负责联网搜索。任一服务缺 Key 或异常时自动降级,零 Key 也能完整启动。

---

## 检索链路:从提问到带定位引用

```
提问
 └─▶ AEF 混合检索(hybrid_search)
       · 查询画像:精确线索 / 时效需求 / 复杂度 / 是否显式过滤标签
       · 信号可靠性门控:没有可信发布时间就把时间权重归零,没指定标签就把标签权重归零
       · 校准分数 + 加权 RRF 融合 + MMR 式去重
 └─▶ 联网(可选,search_service):Tavily 托管搜索;失败且开启降级时走 Bing HTML
 └─▶ 证据选择(evidence_selector):本地/网络预算分配 + 跨源去重 + 单文档切片上限
 └─▶ CARE 精排(care_reranker):对前 10 个候选调用 gte-rerank-v2
       · 比较 AEF 与交叉编码器的前二名间隔,逐查询算融合权重
       · 任何异常 → 直接返回 AEF 排序(响应里 care_rerank_used=false)
 └─▶ RAG 生成 / 报告生成:只允许引用给定角标
 └─▶ 引用回溯:角标绑定 文档 → 切片 → 字符范围 → 行号
```

`POST /api/search` 的每条结果除了综合分,还会返回各信号得分与诊断字段:
`vector_score` / `keyword_score` / `time_score` / `tag_score`、`retrieval_confidence`、
`adaptive_weights`(本次实际生效的权重)、`signal_reliability`(各信号可靠度)、
`care_rerank_used`、`care_weight`。答辩或调试时可据此解释"为什么这条排第一"。

---

## 快速开始(本地零依赖,无需 Docker)

### 准备

| 需要 | 说明 |
|------|------|
| Python 3.10+ | 本机已用 3.13 验证 |
| Node.js 18+ | 前端需要(本机已用 24.15 验证) |
| 通义千问 API Key | [百炼控制台](https://help.aliyun.com/zh/model-studio/models) 申请,新用户有免费额度。**没有也能启动**(走离线降级) |
| Tavily API Key | [tavily.com](https://tavily.com) 申请。只影响"联网搜索"开关,**没有也能用本地检索** |
| Chrome | 装插件用(可选) |

### 三步

```bash
# 1. 进入项目
cd 小鲸OrcaAI

# 2. 一键启动(后端 + Next.js 前端)
bash run.sh

# 3. 浏览器自动打开,或手动访问
#    http://localhost:3000
```

首次运行会自动生成 `.env`。填入 Key 后重跑即可获得完整能力:

```bash
# .env
DASHSCOPE_API_KEY=...    # 打标签 / 向量 / 问答 / 报告 / CARE 重排
TAVILY_API_KEY=...       # 联网搜索(可留空)
```

一个 Key 都不填也能启动 —— 此时走**离线降级**(确定性 mock 向量 + 规则标签 + 检索片段式回答),
用于演示流程和跑测试,见 [ADR-0007](docs/adr/0007-offline-mock-embedding.md)。

停止:`bash run.sh stop` · 状态:`bash run.sh status` · 接口文档:`http://localhost:8000/docs`

### 装 Chrome 插件

`chrome://extensions/` → 打开右上角「开发者模式」→「加载已解压的扩展程序」→ 选 `extension/` 文件夹。

---

## 功能一览

| # | 功能 | 说明 | 入口 |
|---|------|------|------|
| ① | 收藏 / 搜索 / 问答 / 标签 | 项目核心链路:收藏 → 打标签 → 入库 → 混合检索 → RAG 问答 | 插件 / Web 前端 |
| ② | 文件上传 | PDF / Word / PPT / TXT / MD / CSV 解析入库,保留原文件下载入口 | Web 前端 |
| ③ | AI 报告 | 周度航运市场简报 / 航线风险预警 / 公约更新解读 | `POST /api/generate/report` |
| ④ | 用户认证 | JWT 注册登录,文档归属用户 | `/api/auth/*` |
| ⑤ | 团队协作 | 团队创建、成员管理、角色权限 | `/api/teams/*` |
| ⑥ | 联网搜索 | Tavily 托管搜索,可与本地证据合并后统一引用 | 前端开关 / `GET /api/search/internet/` |
| ⑦ | 可追溯引用 | 角标可点击跳转,绑定到切片、字符范围与行号 | 问答与报告输出 |

---

## API 速查

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/documents/upload` | 收藏 URL 或粘贴文本入库 |
| GET | `/api/documents` | 文档列表 |
| DELETE | `/api/documents/{doc_id}` | 删除文档 |
| POST | `/api/search` | 库内混合检索(AEF + 证据选择 + CARE),返回各信号得分与诊断字段 |
| POST | `/api/chat` | 知识库问答(RAG),返回带定位引用的答案 |
| GET | `/api/search/internet/?q=&num=` | 联网搜索(Tavily,可降级) |
| GET | `/api/tags` | 当前领域包的标签维度 |
| GET | `/api/status` | 系统状态 |
| POST | `/api/files/upload` | 上传文件并解析入库 |
| GET | `/api/files/{object_name}/raw` | 下载原文件 |
| POST | `/api/generate/report` | 生成指定类型的报告 |
| GET | `/api/generate/report-types` | 当前领域包支持的报告类型 |
| POST | `/api/auth/register` `/login` `/refresh` | 注册 / 登录 / 刷新令牌 |
| GET | `/api/auth/me` | 当前用户信息 |
| POST GET DELETE | `/api/teams/*` | 团队创建、成员增删 |
| GET | `/health` | 健康检查 |

---

## 配置项

全部配置集中在根目录 `.env`(模板见 `.env.example`),代码里由 `backend/src/core/config.py` 统一读取。

| 变量 | 作用 | 缺省行为 |
|------|------|---------|
| `DASHSCOPE_API_KEY` | 通义千问:打标签 / 向量 / 问答 / 报告 / 重排 | 留空走离线降级 |
| `TAVILY_API_KEY` | 托管联网搜索 | 留空时联网不可用,本地检索不受影响 |
| `CHAT_MODEL` | 对话模型 | `qwen-plus` |
| `EMBEDDING_MODEL` | 向量模型 | `text-embedding-v3` |
| `RERANK_ENABLED` | 是否启用 CARE 精排 | `true` |
| `RERANK_MODEL` / `RERANK_CANDIDATES` | 精排模型与候选数 | `gte-rerank-v2` / `10` |
| `RERANK_TIMEOUT_SECONDS` | 精排超时,超时即回退 | `5` |
| `CARE_WEIGHT_LOW` / `CARE_WEIGHT_SPAN` | CARE 融合权重下界与跨度 | `0.4` / `0.8` |
| `WEB_SEARCH_FALLBACK` | Tavily 失败时是否降级 Bing | `true` |
| `ACTIVE_DOMAIN` | 加载哪个领域包 | `maritime` |
| `DATABASE_URL` / `STORAGE_BACKEND` | 元数据库与文件存储 | SQLite + 本地目录 |
| `JWT_SECRET` | JWT 签名密钥 | **对外部署前必须改成随机值** |

---

## 代码结构

```
小鲸OrcaAI/
├── backend/                    后端(FastAPI)
│   ├── src/
│   │   ├── main.py             程序入口,注册 6 组路由
│   │   ├── core/               配置、数据库(SQLite)、安全(JWT)
│   │   ├── api/                路由:routes / auth / files / teams / generate / search
│   │   ├── models/             数据模型(Document / User / Team / 纯检索类型)
│   │   ├── services/           切片 / 向量化 / AEF 混合检索 / 证据选择 / CARE 重排 / RAG / 标签 / 报告
│   │   ├── collectors/         采集器接口 + 网页 / 公众号采集器(见 ADR-0004)
│   │   └── domains/            领域包:maritime(航运)/ example(空模板)
│   │       └── maritime/       tags.yaml + prompts + keywords + reports
│   ├── tests/                  68 项测试,无需 API Key、不联网
│   └── requirements.txt        本地依赖(生产额外依赖见 requirements-prod.txt)
├── web/                        ★ Next.js 前端(主界面)
│   ├── src/app/                6 个页面:概览 / 文档 / 搜索 / 问答 / 报告 / 设置
│   ├── src/components/         sidebar / tag-list / markdown / shadcn-ui 组件
│   └── src/lib/                API 客户端 + Markdown 脚注处理
├── extension/                  Chrome 插件(MV3):一键收藏 + 网页抓取
├── docs/
│   ├── adr/                    架构决策记录 0001–0010
│   ├── demo-script.md          5 分钟答辩演示脚本
│   └── architecture-review-2026-07-31.html   对照 OmniBox 的架构评审报告
├── CONTEXT.md                  领域词汇表(RAG / 向量 / 领域包 / 采集器 / 引用定位)
├── ROADMAP.md                  路线图与 backlog
├── CHANGELOG.md                更新日志
└── run.sh                      一键启动 / 停止 / 状态
```

---

## 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| 后端 | FastAPI + Pydantic | HTTP 服务与数据校验 |
| 元数据库 | SQLite(异步 SQLAlchemy) | 用户 / 团队 / 文档记录,生产可切 Postgres |
| 向量库 | Chroma | 语义检索 |
| 稀疏检索 | BM25 + 字符 bigram | 中文关键词召回(见 ADR-0006) |
| 融合与精排 | AEF + `gte-rerank-v2`(CARE) | 自适应加权检索与交叉编码器重排 |
| 生成模型 | 通义千问(OpenAI 兼容接口) | 打标签 / 问答 / 报告 |
| 向量模型 | `text-embedding-v3` | 文档与查询向量化 |
| 联网搜索 | Tavily(降级 Bing HTML) | 时效性证据补充 |
| 前端 | Next.js 16 + React 19 + Tailwind v4 + shadcn/ui | 主界面 |
| 插件 | Chrome Extension MV3 | 一键收藏 |

---

## 测试

```bash
cd backend
../.venv/bin/python -m pytest -q
```

**68 项测试全部通过**,不需要 API Key、不联网、不产生费用(约 2–3 秒)。
覆盖切片与定位、中文检索、AEF、证据选择、CARE 重排、引用链路与报告日期。

前端构建验证:

```bash
cd web
npm run build
```

---

## 生产部署(可选,当前未验证)

本地 `bash run.sh` 是**唯一验证过**的启动方式。下面这条重型服务栈路径的适配代码已经写好
(`services/file_service.py` 的 MinIO 实现、`requirements-prod.txt`),但 Docker 配置还没修完,
`docker-compose up -d` **目前会失败**:

```bash
pip install -r backend/requirements.txt -r backend/requirements-prod.txt
# 在 .env 中按注释切换 DATABASE_URL / STORAGE_BACKEND
docker-compose up -d
```

存储层做了可切换抽象,业务代码不变,详见 [ADR-0002](docs/adr/0002-local-first-storage.md)。
具体的损坏点与修复清单见 [ROADMAP.md](ROADMAP.md) 第五节。

---

## 已知限制

- **多模态尚未入库**:当前只解析文本;图片、表格结构、音频转写与 PDF 页码级定位都还没做。
- **时间信号依赖真实发布时间**:抓不到可信发布日期时该维度会被门控掉,不会用入库时间冒充。
- **CARE 依赖外部服务**:没有 DashScope Key 时精排自动跳过,退回 AEF 排序,此时检索质量会下降。
- **评估集是银标**:CARE 的独立确认集查询由模型生成、每条只有一个相关文档,不是人工多级 qrels;论文中的提升结论据此限定。
- **单机规模**:SQLite + Chroma 面向个人与小团队,未做并发压测和分片。
- **前端无 E2E 测试**:目前只有后端单元/集成测试与生产构建验证。

---

## 负责人

Brendan Liao · 大学生创新创业训练计划项目

有编程基础的话,可直接打开 `http://localhost:8000/docs` 看交互式 API 文档。
