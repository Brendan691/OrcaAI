# 🐳 小鲸 OrcaAI

**为航运知识管理优化过的通用知识管理工具**

浏览网页时一键收藏文章/报告到知识库,AI 自动打标签分类,随时用自然语言向知识库提问。
内核与领域无关——航运只是当前加载的一个「领域包」,换个领域包就能服务其他行业。

> 📚 新手请先读 [`docs/guide/`](docs/guide/)(从 Python 语法讲起的完整学习指南)。
> 🧭 想了解"为什么这么设计"读 [`CONTEXT.md`](CONTEXT.md) 与 [`docs/adr/`](docs/adr/)。

---

## 这个项目解决什么

日常我们会看到很多专业文章、报告、新闻,通常的结局是:加书签 → 再也不看 → 要用时找不到。

小鲸 OrcaAI:
1. **一键收藏**:浏览网页时点一下,自动抓取正文存入知识库(公众号文章有专用采集器)。
2. **AI 自动打标签**:按领域标签体系自动分类,无需手动整理。
3. **智能问答**:用自然语言提问,AI 基于你收藏的内容回答(RAG,有出处、不瞎编)。
4. **混合检索**:向量语义 + 关键词 + 时间 + 标签四维加权,检索更准。

**适用场景:** 写论文找资料、行业调研、追踪动态、整理专业知识。

---

## 系统架构(通用内核 + 领域包)

```
  采集入口              通用内核(领域无关)                领域包(可替换)
 ───────────         ────────────────────────         ──────────────────
 Chrome 插件 ─┐
 文件上传    ─┼─▶ 采集器 Collector ─▶ 切片 ─▶ 向量化 ─▶ 知识库          ┌──────────────┐
 粘贴文本    ─┘   (网页/公众号/文件)              (Chroma+SQLite)      │ maritime     │
                                                       │              │ 航运领域包    │
 Streamlit ◀── RAG 问答 / 混合检索 ◀──────────────────┴──────────────│ ·四维标签     │
  管理后台        │                                                   │ ·分类提示词   │
                 └─▶ 报告生成(周报/风险预警/公约解读)◀───────────────│ ·报告模板     │
                                                                     └──────────────┘
                        LLM:通义千问(打标签 / 向量化 / 问答 / 生成)
```

- **通用内核**:采集、切片、向量化、知识库、混合检索、RAG —— 不含任何"航运"字样。
- **领域包** `backend/src/domains/maritime/`:标签体系、提示词、报告模板。换包即换行业(见 `domains/example/` 空模板)。

---

## 快速开始(本地零依赖,无需 Docker)

### 准备
| 需要 | 说明 |
|------|------|
| Python 3.10+ | 本机已用 3.13 验证 |
| 通义千问 API Key | [百炼控制台](https://help.aliyun.com/zh/model-studio/models) 申请,新用户有免费额度。**没有也能启动**(走离线降级) |
| Chrome | 装插件用 |

### 三步

```bash
# 1. 进入项目
cd 小鲸OrcaAI

# 2. 一键启动(自动建虚拟环境、装依赖、起服务)
bash run.sh

# 3. 浏览器打开管理后台
#    http://localhost:8501
```

首次运行会生成 `.env`。填入 `DASHSCOPE_API_KEY` 后重跑即可获得完整 AI 能力;
不填也能启动——此时走**离线降级**(mock 向量 + 规则标签 + 检索片段),用于演示流程与跑测试(见 [ADR-0007](docs/adr/0007-offline-mock-embedding.md))。

停止:`bash run.sh stop` · 状态:`bash run.sh status`

### 装 Chrome 插件
`chrome://extensions/` → 打开右上角「开发者模式」→「加载已解压的扩展程序」→ 选 `extension/` 文件夹。

---

## 五大功能

| # | 功能 | 说明 | 入口 |
|---|------|------|------|
| ① | 文档收藏 / 问答 / 搜索 / 标签 | 项目核心:收藏→打标签→入库→混合检索→RAG 问答 | 插件 / 后台 |
| ② | 文件上传 | PDF / Word / PPT / TXT / MD / CSV 解析入库 | 后台 |
| ③ | AI 报告生成 | 基于知识库生成航运周报 / 风险预警 / 公约解读 | `POST /api/generate/report` |
| ④ | 用户认证 | JWT 注册登录,文档归属用户 | `/api/auth/*` |
| ⑤ | 团队协作 | 团队创建、成员管理、角色权限 | `/api/teams/*` |

---

## 代码结构

```
小鲸OrcaAI/
├── backend/                    后端(FastAPI)
│   ├── src/
│   │   ├── main.py             程序入口,注册五大功能路由
│   │   ├── core/               配置、数据库(SQLite)、安全(JWT)
│   │   ├── api/                路由:routes/auth/files/teams/generate
│   │   ├── models/             数据模型(Document/User/Team)
│   │   ├── services/           核心逻辑:切片/向量化/混合检索/RAG/标签/报告
│   │   ├── collectors/         ★ 采集器接口 + 网页/公众号采集器(见 ADR-0004)
│   │   └── domains/            ★ 领域包:maritime(航运)/ example(空模板)
│   │       └── maritime/       tags.yaml + prompts + keywords + reports
│   ├── tests/                  测试(42 项,无需 API Key)
│   └── requirements.txt        本地依赖(生产额外依赖见 requirements-prod.txt)
├── admin/app.py                Streamlit 管理后台
├── extension/                  Chrome 插件(MV3)
├── docs/
│   ├── adr/                    架构决策记录(为什么这么设计)
│   └── guide/                  从零学起的技术指南
├── CONTEXT.md                  领域语言词汇表
├── ROADMAP.md                  路线图(多平台采集等)
├── docker-compose.yml          生产部署(Postgres/MinIO 等,见 ADR-0002)
└── run.sh                      一键启动脚本
```

---

## 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| 后端 | FastAPI | HTTP 服务 |
| 元数据库 | SQLite(异步 SQLAlchemy) | 用户/团队/文档记录。生产可切 Postgres |
| 向量库 | Chroma | 语义检索 |
| LLM | 通义千问(OpenAI 兼容) | 打标签 / 向量化 / 问答 / 生成 |
| 后台 | Streamlit | 纯 Python 管理界面 |
| 插件 | Chrome Extension MV3 | 一键收藏 |

---

## 运行测试

```bash
cd backend
../.venv/bin/python -m pytest tests/ -v
```

42 项测试,**不需要 API Key、不产生费用、不联网**(< 1 秒)。

---

## 生产部署(可选)

本地默认零依赖。若要部署到服务器并启用重型服务栈(Postgres / MinIO / Meilisearch / SearXNG):

```bash
pip install -r backend/requirements.txt -r backend/requirements-prod.txt
# 在 .env 中按注释切换 DATABASE_URL / STORAGE_BACKEND
docker-compose up -d
```

存储层做了可切换抽象,业务代码不变。详见 [ADR-0002](docs/adr/0002-local-first-storage.md)。

---

## 路线图

多平台采集(小红书 / 抖音 / 公众号内容识别入库)等规划见 [ROADMAP.md](ROADMAP.md)。
采集器接口已预留,新增平台 = 新增一个采集器文件,入库管线不变。

---

## 负责人

Brendan Liao · 大创项目

*有编程基础可直接看 `http://localhost:8000/docs` 的交互式 API 文档。*

