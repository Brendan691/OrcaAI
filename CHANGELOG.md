# 更新日志 / Changelog

本文件记录小鲸 OrcaAI 的所有重要变更。

---

## [0.3.0] - 2026-07-29

### 🎯 重大重构:通用内核 + 领域包架构

从"航运知识管理工具"升级为"为航运知识管理优化的**通用**知识管理引擎"。内核完全领域无关,航运成为一个可替换的「领域包」。

### ✨ 新增功能

#### 架构与设计
- **领域包系统** (`backend/src/domains/`):
  - `DomainPack` 协议定义标签体系、提示词、报告模板
  - `maritime/` 航运领域包:84 个标签(4 维)+ 3 种报告类型
  - `example/` 空模板:5 个标签,证明领域可切换
  - 已验证 maritime ↔ example 自由切换
- **采集器接口** (`backend/src/collectors/`,见 ADR-0004):
  - `Collector` 协议 + 注册表,支持多平台采集扩展
  - `WebCollector`:通用网页抓取
  - `WechatArticleCollector`:公众号文章专用提取(精准提取标题/正文/作者)
  - 路由自动选择合适的采集器(公众号链接走专用采集器)
- **离线降级机制**(见 ADR-0007):
  - `embedding_service`:无 API Key 时用确定性 mock 向量(词袋 hash)
  - `tag_classifier`:规则引擎兜底(基于领域包关键词)
  - `rag_service`:问答降级为检索片段 + 提示
  - 效果:零 Key 也能跑、测试不触外部 API

#### 功能增强
- **中文关键词检索修复**:改用字符 bigram 分词(之前整段中文成一个 token 导致关键词得分恒为 0)
- **存储层抽象**:LocalFileStorage / MinioFileStorage,业务代码统一接口

### 🔧 改进

#### 精简与优化
- **数据库**:SQLite 替代 Postgres 作本地默认,异步 SQLAlchemy,生产可切回(见 ADR-0002)
- **依赖精简**:删除 10+ 零引用依赖(asyncpg/minio/motor/httpx-sse 等),venv 从预估 5GB 降至 794MB
- **前端决策**:删除 `web/` 空壳(11 文件),Streamlit 作为主界面(见 ADR-0005)

#### 质量提升
- **测试覆盖**:42 项测试(+6),全部通过,< 2 秒
  - 新增 `tests/test_chinese_search.py`:锁定中文 bigram 行为
  - 新增 `tests/test_collectors.py`:采集器选择逻辑
- **工具链**:
  - `run.sh` 重写:一键启动/停止/状态,清华源加速
  - `.env.example` 更新:本地 SQLite 配置,生产配置已注释

### 📖 文档体系建立

- **CONTEXT.md**:领域语言词汇表
- **7 份架构决策记录**(docs/adr/0001-0007):
  - 0001:为什么要写 ADR
  - 0002:本地优先存储(SQLite)
  - 0003:可插拔领域包
  - 0004:采集器接口
  - 0005:Streamlit vs Next.js
  - 0006:混合检索算法(四维加权)
  - 0007:离线降级机制
- **README.md** 完全重写:新定位、架构图、快速开始、五大功能说明
- **ROADMAP.md**:多平台采集愿景、各平台技术难点、分期计划
- **docs/demo-script.md**:5 分钟答辩演示脚本
- **GUIDE-PROMPT.md**:技术指南生成提示词(面向编程初学者)

### 🐛 Bug 修复

- 修复 `config.TAGS_CONFIG_PATH` 不存在导致 import 崩溃(已移入领域包)
- 修复 SQLite 引擎参数错误(pool_size/max_overflow 对 aiosqlite 无效)
- 修复中文关键词检索恒为 0(改用 bigram)

### ⚠️ 破坏性变更

- **配置文件**:`.env` 结构调整,默认 SQLite + local 存储(旧配置需迁移)
- **依赖**:删除 asyncpg/minio/motor 等,需生产部署时单独装 `requirements-prod.txt`
- **代码结构**:
  - `backend/config/tags.yaml` → `backend/src/domains/maritime/tags.yaml`
  - 标签/提示词/报告全部改从领域包加载,硬编码的地方已重构

### 📊 数据指标

- 代码行数:约 3500 行 Python(不含测试)
- 测试覆盖:42 项,核心逻辑全覆盖
- 文档字数:README 2k + ROADMAP 2k + ADR 7k + 演示脚本 2k ≈ 13k 字
- venv 大小:794MB(本地模式)

---

## [0.2.0] - 2026-07 之前

初始版本,功能包括:
- 五大功能:①文档收藏/问答/搜索/标签 ②文件上传 ③AI报告生成 ④JWT认证 ⑤团队协作
- FastAPI 后端 + Postgres + Chroma + 通义千问
- Streamlit 管理后台 + Chrome 插件(MV3)
- 混合检索(向量 + 关键词 + 时间 + 标签)
- 硬编码航运标签体系

---

## 版本说明

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

- **主版本号(MAJOR)**:不兼容的 API 修改
- **次版本号(MINOR)**:向下兼容的功能性新增
- **修订号(PATCH)**:向下兼容的问题修正
