# 🐳 小鲸 OrcaAI

**AI 驱动的一站式海事知识管理工具**

帮你在浏览网页时一键收藏航运新闻、行业报告到知识库，AI 自动打标签分类，随时向知识库提问。

---

## 📖 目录

- [这个项目是干什么的](#这个项目是干什么的)
- [系统架构（一张图看懂）](#系统架构一张图看懂)
- [三步跑起来](#三步跑起来)
- [详细使用指南](#详细使用指南)
  - [1. 启动后端](#1-启动后端)
  - [2. 打开管理后台](#2-打开管理后台)
  - [3. 安装 Chrome 插件](#3-安装-chrome-插件)
  - [4. 日常使用](#4-日常使用)
- [代码结构说明](#代码结构说明)
- [每个文件是干什么的](#每个文件是干什么的)
- [Docker 部署（可选）](#docker-部署可选)
- [运行测试](#运行测试)
- [常见问题](#常见问题)

---

## 这个项目是干什么的

日常工作中，我们会在网上看到很多海事航运相关的文章、新闻、报告。通常的做法是：加书签 → 再也不看 → 需要用的时候找不到。

小鲸 OrcaAI 解决的问题：
1. **一键收藏**：浏览网页时点一下按钮，自动保存到你的知识库
2. **AI 自动打标签**：根据内容自动匹配海事四维标签（业务类型/地理区域/主题类别/事件性质），无需手动分类
3. **智能问答**：向知识库用自然语言提问，AI 从你收藏的内容中找到答案

**适用场景：** 写论文找资料、做行业调研、追踪航运动态、整理专业知识。

---

## 系统架构

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────┐     ┌──────────────┐
│  你的浏览器    │────▶│  Chrome 插件      │────▶│  FastAPI     │────▶│  通义千问 LLM │
│  (网页文章)   │     │  (一键收藏)      │     │  后端服务    │     │  (打标签+问答) │
└──────────────┘     └──────────────────┘     └──────┬──────┘     └──────────────┘
                                                     │
                                          ┌──────────▼──────┐
                                          │  Chroma 向量库   │
                                          │  (存储知识)      │
                                          └──────────────────┘
```

- **Chrome 插件**：你和项目的交互入口，收藏网页 + 提问
- **FastAPI 后端**：整个系统的大脑，处理请求、调用 AI、管理数据
- **通义千问 LLM**：阿里云的大模型，负责理解文章内容、自动打标签、生成回答
- **Chroma 向量库**：把文章转成"数学向量"存储，让搜索不再是关键词匹配，而是"意思相近"的语义搜索

---

## 三步跑起来

### 准备工作

| 你需要有 | 怎么获取 |
|----------|----------|
| Python 3.10+ 或 Docker | [python.org](https://www.python.org/downloads/) 或 [Docker Desktop](https://www.docker.com/) |
| 通义千问 API Key | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com/) 免费注册，开通模型服务 |
| Chrome 浏览器 | 装插件用 |

### 第一步：打开终端

Mac 按 `Cmd+空格` 搜索"终端"，输入：

```bash
cd ~“文件位置”
```

### 第二步：启动（一条命令搞定一切）

```bash
bash run.sh
```

首次运行会引导你输入 API Key（从 https://dashscope.console.aliyun.com 获取），之后自动安装依赖、生成图标、启动全部服务。

### 第三步：打开管理后台

浏览器自动打开 http://localhost:8501，或者手动访问。

看到下面的输出就说明成功了：
```
🎉 小鲸 OrcaAI 已启动！

  📡 后端 API：  http://localhost:8000
  📊 管理后台：  http://localhost:8501
  📖 API 文档：  http://localhost:8000/docs

  停止服务：    bash run.sh stop
  查看状态：    bash run.sh status
```

---

## 详细使用指南

### 1. 启动后端

```bash
cd ~“文件位置”
bash run.sh
```

验证是否启动成功：浏览器打开 http://localhost:8000/health ，看到 `{"status":"healthy"}` 就 OK。

### 2. 打开管理后台

`bash run.sh` 已自动启动管理后台，浏览器打开 http://localhost:8501 即可。

管理后台可以：
- **系统概览**：查看知识库有多少文档、什么标签
- **文档管理**：查看、删除文档，手动添加文本
- **知识搜索**：搜索已收藏的内容
- **知识问答**：向知识库提问
- **设置**：修改后端地址，查看标签体系

### 3. 安装 Chrome 插件

1. 打开 Chrome 浏览器
2. 地址栏输入 `chrome://extensions/` 并回车
3. 打开右上角的 **"开发者模式"** 开关
4. 点击左上角 **"加载已解压的扩展程序"**
5. 选择 `小鲸OrcaAI/extension/` 文件夹
6. 完成！Chrome 工具栏右上角会出现小鲸的图标

> 💡 **找不到插件图标？** 点击工具栏右侧的拼图图标 🧩，找到"小鲸OrcaAI"，点一下图钉 📌 就能固定在工具栏上了。

### 4. 日常使用

**收藏网页：**
1. 浏览到一篇航运相关的文章
2. 点击工具栏的小鲸图标
3. 确认页面标题正确
4. 点击"收藏到知识库"
5. 等待 3-5 秒，AI 自动打好标签，保存完成

**向知识库提问：**
1. 点击工具栏的小鲸图标
2. 下方问答区输入问题，例如"最近集装箱运价趋势如何"
3. 按回车或点发送
4. AI 从你收藏的文章中找到答案并回复

---

## 代码结构说明

```
小鲸OrcaAI/
│
├── backend/                         # 后端（整个系统的核心）
│   ├── src/
│   │   ├── main.py                  # ★ 程序入口，启动 FastAPI 服务
│   │   ├── api/
│   │   │   └── routes.py            # ★ 所有 API 路由（上传/搜索/问答等接口）
│   │   ├── core/
│   │   │   └── config.py            # 配置管理（读取 .env）
│   │   ├── models/
│   │   │   └── document.py          # 数据模型定义
│   │   └── services/                # 服务层（核心业务逻辑）
│   │       ├── rag_service.py       # ★ RAG 问答：检索+生成回答
│   │       ├── hybrid_search.py     # ★ 混合相似度检索（论文创新点）
│   │       ├── tag_classifier.py    # ★ 海事四维标签自动分类
│   │       ├── document_processor.py # 网页抓取+文本切片
│   │       ├── embedding_service.py # 文本向量化
│   │       └── chroma_store.py      # Chroma 向量数据库操作
│   ├── config/
│   │   └── tags.yaml                # ★ 海事四维标签体系定义
│   ├── tests/                       # 测试代码
│   ├── requirements.txt             # Python 依赖包列表
│   ├── .env                         # API Key 配置（需自己创建）
│   ├── .env.example                 # 配置模板
│   └── run.sh                       # 启动脚本
│
├── extension/                       # Chrome 浏览器插件
│   ├── manifest.json                # 插件配置
│   ├── popup.html                   # 弹出窗口的界面
│   ├── popup.js                     # ★ 弹出窗口的逻辑（收藏+问答）
│   ├── popup.css                    # 弹出窗口的样式
│   ├── content.js                   # 与页面的交互脚本
│   ├── background.js                # 后台服务
│   └── icons/                       # 插件图标
│
├── admin/
│   └── app.py                       # ★ Streamlit 管理后台
│
├── scripts/
│   └── setup.sh                     # ★ 项目初始化脚本
│
├── Dockerfile                       # Docker 镜像定义
├── docker-compose.yml               # Docker 一键部署
└── README.md                        # 本文档
```

---

## 每个文件是干什么的

### 核心服务文件（带 ★ 的最重要）

**`backend/src/main.py`** — 程序入口
- 启动 FastAPI Web 服务
- 配置 CORS（允许 Chrome 插件跨域访问）
- 注册所有 API 路由

**`backend/src/api/routes.py`** — API 接口定义
- `POST /api/documents/upload` — 上传文档（URL 或文本）
- `GET /api/documents` — 获取所有文档
- `DELETE /api/documents/{id}` — 删除文档
- `POST /api/chat` — 知识库问答
- `POST /api/search` — 混合搜索
- `GET /api/tags` — 获取标签体系
- `GET /api/status` — 系统状态

**`backend/src/services/rag_service.py`** — RAG 问答
- 工作流程：用户提问 → 向量化问题 → 从 Chroma 找相关内容 → 用 LLM 生成答案
- 叫 RAG（Retrieval-Augmented Generation，检索增强生成）是因为 AI 先"检索"知识库再"生成"回答，而不是凭记忆瞎编

**`backend/src/services/hybrid_search.py`** — 混合相似度检索（论文核心创新点）
- 不只用向量相似度，四个维度加权融合：
  - 60% 向量相似度（语义相似）
  - 20% 关键词匹配（精确匹配）
  - 10% 时间衰减（新文档优先）
  - 10% 标签匹配（分类匹配）
- 权重可通过网格搜索自动优化

**`backend/src/services/tag_classifier.py`** — 海事四维标签分类
- 优先用 LLM 分析内容打标签（准确率高）
- 如果 LLM 调用失败，自动回退到关键词规则引擎（不依赖网络）

**`backend/config/tags.yaml`** — 标签体系定义
- 四个维度共 70+ 个标签
- 业务类型：集装箱运输、散货运输、港口作业等
- 地理区域：远东、欧洲、中国沿海等
- 主题类别：运价波动、碳排放政策、智能航运等
- 事件性质：船舶碰撞、法规更新、行业报告等

**`admin/app.py`** — Web 管理后台
- 纯 Python 写的网页界面（Streamlit 框架）
- 不需要写 HTML/CSS/JS

**`extension/popup.js`** — Chrome 插件主逻辑
- 获取当前浏览页面的标题和 URL
- 发送到后端进行收藏
- 在插件窗口中直接向知识库提问

**`scripts/setup.sh`** — 初始化脚本
- 自动检查环境、安装依赖、生成图标、创建配置文件

---

## Docker 部署（可选）

如果你想把服务部署到服务器上（比如阿里云轻量应用服务器），用 Docker 最方便：

```bash
# 1. 安装 Docker（Mac 上下载 Docker Desktop）

# 2. 确保 .env 中填好 API Key

# 3. 一键启动所有服务
docker-compose up -d

# 4. 检查运行状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f backend

# 6. 停止
docker-compose down
```

部署后：
- 后端 API：http://你的服务器IP:8000
- 管理后台：http://你的服务器IP:8501
- Chrome 插件设置里把后端地址改成服务器 IP

---

## 运行测试

```bash
cd backend

# 安装测试依赖（如果还没装）
pip3 install pytest

# 运行所有测试
python3 -m pytest tests/ -v

# 只运行一个测试文件
python3 -m pytest tests/test_tag_classifier.py -v
```

测试不需要 API Key，不产生费用。

---

## 常见问题

### Q: `pip3: command not found`
A: 先安装 Python 3（https://www.python.org/downloads/），Mac 上也可以用 `brew install python3`。

### Q: 启动后端时报错 `ModuleNotFoundError`
A: 依赖没装全，运行 `pip3 install -r backend/requirements.txt`。

### Q: 收藏网页时报"网络错误"
A: 后端没启动或地址不对。检查：
1. `backend/run.sh` 是否正在运行
2. Chrome 插件设置里的后端地址是否为 `http://localhost:8000`
3. 地址栏输入 `http://localhost:8000/health` 看能否打开

### Q: AI 打标签不准确
A: 标签分类依赖大模型理解能力，航运文章通常准确率在 80%+。如果不满意：
1. 尝试收藏文章正文（而非只有标题的页面）
2. 编辑 `backend/config/tags.yaml` 补充同义词关键词

### Q: 通义千问 API 要钱吗？
A: 新用户注册有免费额度。日常使用（每天几十次）基本不花钱。具体价格看阿里云官网。

### Q: 数据存在哪？
A: `backend/chroma_db/` 目录下。这是 Chroma 向量数据库的持久化文件。删了这个目录 = 清空知识库。

### Q: 怎么备份知识库？
A: 直接复制 `backend/chroma_db/` 文件夹即可。

### Q: AI 会不会瞎编答案？
A: 不会。本项目使用 RAG 技术，AI 必须基于你收藏的内容来回答。如果知识库里没有相关内容，AI 会直接告诉你找不到。

### Q: Chrome 插件图标没有显示
A: 打开 `chrome://extensions/`，找到小鲸 OrcaAI，确认已启用。如果图标文件夹为空，运行 `python3 extension/icons/generate_icons.py`。

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端框架 | FastAPI | 处理 HTTP 请求 |
| 大模型 | 通义千问 (Qwen-max) | 打标签、生成回答 |
| 向量化 | text-embedding-v3 | 文本转数学向量 |
| 向量数据库 | Chroma | 语义搜索存储 |
| 前端插件 | Chrome Extension MV3 | 浏览器交互 |
| 管理后台 | Streamlit | Web 管理界面 |
| 部署 | Docker / docker-compose | 容器化部署 |

---

## 版本

v0.2.0 — 完整功能版

---

## 负责人

Brendan Liao

---

*如果你有编程基础，可以直接看 `http://localhost:8000/docs` 的 API 文档。*
