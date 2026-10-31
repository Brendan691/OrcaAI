# 更新日志 / Changelog

本文件记录小鲸 OrcaAI 的所有重要变更。

---

## [0.5.0] - 2026-10-31

正式发布。本版把"线上检索"与"论文实验"收敛到同一套编码、意图与候选策略实现上,
并补齐了依赖可观测性与测试隔离。

### 🔬 编码与重排同构

- 新增 `backend/src/services/bge_encoder.py` 作为 BGE-M3 的**唯一实现**
  (CLS pooling + L2 归一化 + `max_length=1024` + CPU 4 线程 + 导出 `fingerprint`),
  线上服务与离线实验必须共同 import 本模块,禁止各自复制加载逻辑,保证"评测口径 = 系统口径"。
- 新增 `EMBEDDING_BACKEND=local` 分支:通过本地编码 sidecar 调用同一实现。
  **该分支不静默降级**——sidecar 连不上直接抛错,避免把失败伪装成成功。
- 新增 `DASHSCOPE_RERANK_ENDPOINT_REMOTE`:`DASHSCOPE_RERANK_ENDPOINT` 可指向本地
  DashScope 兼容重排 shim,远程公共端点单独保留。

### 🧠 检索逻辑

- **CARE 校准门控**:新增 `CARE_GATE_*`(截距、基线间隔、GTE 间隔、top1 一致性)
  与 `CARE_MARGIN_*` / `CARE_AGREEMENT_*` 标准化参数;重排候选数默认 10 → **20**。
- **查询意图** `query_intent.py`(`maritime-query-intent-20261021-v1`):
  确定性的中文海事查询分析(时效线索、同义词组、年份等),供 RAG 与联网搜索共用。
- **候选策略** `candidate_policy.py`(`candidate-policy-20261021-v1`):
  本地/联网各 10 个候选、最终证据 5 条、单文档最多 3 块,并统一字符预算。
- **冲突先验** `conflict_prior.py`(`conflict-prior-20261021-v1`):
  针对时效性冲突问题的权威性/新鲜度先验,含官方域名白名单。
- **查询变体**:新增 `query_variants` 与 `SearchVariantTrace`,
  逐个变体记录 provider、结果数与降级码,便于解释联网结果为何退化。

### 📄 文档处理

- 分块重写:`CHUNK_SIZE` 1024 → **600**、`CHUNK_OVERLAP` 128 → **100**,
  且重叠部分必须是完整句子。
- Markdown 表格**整表独立成块**;超过 `CHUNK_MAX_TABLE`(1000)的表格,
  其后续块会带表头提示(`prefix_hint`),但不改变字符偏移。
- 新增 `CHUNK_MIN_LENGTH`(500)、尾块合并与切片 `flags` 标记;新增年份过滤。

### 🩺 可观测性

- 新增 `dependency_health.py`:启动时打印依赖摘要;`GET /health` 现在返回
  `status`(`healthy` / `degraded`)、`ready` 与逐项 `dependencies`。
- 编码 sidecar 为**必需**(不可用则 `ready=false`);重排 sidecar 为**可选**
  (不可用时 CARE 回退 AEF,不影响 `ready`)。远程托管端点不在启动时探测。

### ⚙️ 配置

- 新增 `EMBEDDING_BACKEND`、`EMBEDDING_ENDPOINT`、`DASHSCOPE_RERANK_ENDPOINT_REMOTE`、
  `CARE_GATE_*`、`CARE_MARGIN_*`、`CHUNK_MIN_LENGTH`、`CHUNK_MAX_TABLE`。
- 新增可选的 `QWEN38_API_KEY` / `QWEN38_BASE_URL` / `QWEN38_MODEL`
  (Qwen3.8 专用网关;留空时回退到 `DASHSCOPE_*`)。

### ✅ 质量

- **测试隔离**:`conftest.py` 固定 `EMBEDDING_BACKEND=dashscope` 与
  `RERANK_ENABLED=false`,单元测试不再隐式依赖外部 sidecar
  (此前 `.env` 的 `EMBEDDING_BACKEND=local` 会让 mock 向量测试真实请求 8765)。
- 新增测试:`test_candidate_policy`、`test_conflict_prior`、`test_dependency_health`、
  `test_query_intent`、`test_year_filter`、`test_config_credentials`。
- `.gitignore` 增加 `._*`:exFAT 会生成 AppleDouble 文件,避免被误提交。

### ⚠️ 破坏性变更

- **分块参数默认值变更**(1024/128 → 600/100):已有 Chroma 索引需重建才能与新分块对齐。
- **重排候选数 10 → 20**:CARE 的调用量与延迟随之上升,接入前需按本机实测重新评估超时配置。
- **`EMBEDDING_BACKEND=local` 无降级**:sidecar 未启动时检索直接失败,不再回落到 mock 向量。

---

## [0.4.0] - 2026-09-19

正式发布。上一个版本为 `v0.3.0`,本版汇总 v0.3.0 之后的全部改动:托管联网搜索、统一引用回溯、自适应检索(AEF)与 CARE 交叉编码器重排,以及三批互不重叠语料的开发/确认实验体系。

### 🧠 算法创新

- 新增自适应证据融合(AEF):按查询的精确线索、时效需求、复杂度和标签动态分配向量/关键词/时间/标签权重。
- 新增信号可靠性门控:来源发布日期缺失时自动移除时间权重,无显式标签过滤时自动移除标签权重。
- 融合校准分数与加权 RRF,并使用 MMR 风格目标减少重复切片。
- 新增置信度感知的本地/Web证据校正:动态预算、跨源去重、同文档切片上限。
- 网页采集新增可信发布日期提取,不再用入库时间代替内容发布时间。
- 新增 CARE 置信度自适应 cross-encoder 重排:根据 AEF 与 GTE 的分数间隔逐查询计算融合权重,异常时自动回退 AEF。

### 🏗️ 架构与实验

- 搜索、RAG 和论文实验统一调用同一生产排序模块,消除三套公式漂移。
- 将纯检索类型从 ORM 模型中拆出,论文实验不再启动数据库。
- 新增 AEF 完整方法、三项消融、查询类型分组和受控机制压力实验。
- 冻结银标测试集 AEF NDCG@5=0.9509、MRR@10=0.9350;与离线网格调参上限持平,相对默认方法提升不显著(p=0.243)。
- 新增并核验 Adaptive-RAG、CRAG、RankRAG、HippoRAG、MMR、RAG-Fusion 等前沿相关工作。
- 新增三批互不重叠网页语料的开发/确认流程。最终 48 文档、94 查询确认集上 CARE NDCG@5=0.9317,相对冻结四信号基线提升 0.0586(95% CI [0.0222,0.0974],p=0.001)。相对 GTE-raw 数值提升 0.0025,但不显著(p=0.8806)。
- 通用 Qwen 列表重排和 QAMER 原型均在独立数据上被淘汰,未接入生产主路径。

### ✅ 验证

- 后端全量测试:`68 passed`。
- Next.js 生产构建通过(`next build`),6 个页面全部预渲染成功。
- AEF、双源校正、日期元数据、引用链路定向测试:`44 passed`。
- CARE、AEF、证据选择和 RAG 引用定向回归:`32 passed`。
- 受控机制检查:时间缺失门控、时效路由、证据多样性全部通过。
- Tavily 真实航运查询与联网报告浏览器验证通过:日期星期正确、角标可点击、无裸 HTML、无同号不同链接。

### 🌐 第一阶段:托管联网搜索与引用回溯(2026-07-31 ~ 08-03 完成)

#### ✨ 新增功能

##### 托管联网搜索
- 接入 Tavily 托管搜索 API,作为默认互联网检索 Provider。
- 增加 Bing HTML 降级适配器,Tavily 缺少 Key、超时或失败时可自动降级。
- 新增统一搜索结果、状态和警告模型,前端可以区分成功、降级与失败状态。
- 知识问答和 AI 报告均支持按需开启联网搜索。

##### 统一引用与来源回溯
- 本地知识库和互联网搜索结果统一为同一种引用模型,包含稳定 ID、来源类型、标题、摘要和 URL。
- 知识库引用新增字符范围、行号、切片编号和定位说明,为回到原文具体位置提供基础。
- 回答中的引用角标可点击并滚动到来源卡片;互联网引用可直接打开原网页。
- AI 报告支持 Markdown 上标引用和自动生成的去重来源列表。

##### 入库定位基础
- 文档清洗保留换行,结构化切片记录字符范围和起止行号。
- URL 收藏与文件上传统一向 Chroma 写入完整切片对象,避免定位元数据丢失。
- 上传文件保留可访问的原文件 URL,为后续 PDF 页码和多模态附件回溯预留接口。

#### 🔧 改进

- 重构 RAG 编排,统一管理本地检索、联网检索、上下文构建、引用和降级回答。
- AI 报告联网素材使用全局来源编号,生成后按 URL 重新归一化角标。
- Next.js 前端增加可点击引用、来源卡片、联网状态提示和移动端响应式导航。
- 移除本地 SearXNG 配置及过时的 Streamlit、脚本入口,简化启动和维护成本。

#### 🐛 Bug 修复

- 修复报告引用被渲染为裸 `<sup>/<a>` HTML 文本的问题。
- 修复不同来源重复使用同一角标编号的问题;同一 URL 现在稳定复用同一编号。
- 修复模型自行推断星期导致日期正确、星期错误的问题;发布日期改由程序计算并强制覆盖。
- 修复文档清洗压缩全部换行、导致引用无法精确定位到原文行号的问题。

#### 📖 文档

- 新增对照 OmniBox 的架构评审报告:`docs/architecture-review-2026-07-31.html`。
- 新增引用与定位器领域术语,更新 README、答辩演示脚本和 Next.js 架构决策记录。
- 更新 `.env.example`,补充 Tavily 和联网搜索降级配置说明,不包含真实密钥。

#### ✅ 验证

- 后端测试:`55 passed`。
- Next.js 生产构建通过。
- Tavily 真实航运查询验证成功。
- 真实联网报告浏览器验证通过:日期星期正确、角标可点击、无裸 HTML、无同号不同链接。

### ⚠️ 破坏性变更

- 移除 Streamlit 管理后台与本地 SearXNG,启动入口统一为 `run.sh`。
- `.env` 新增 Tavily 与联网降级配置项;旧配置可直接沿用,未配置时自动降级。
- Chrome 扩展 `manifest.json` 的版本号必须为纯数字,因此前后端用 `0.4.0`,扩展也是 `0.4.0`,三者一致。

---

## [0.3.0] - 2026-07-29 ~ 2026-07-30

### 🎯 重大重构:通用内核 + 领域包架构

从"航运知识管理工具"升级为"为航运知识管理优化的**通用**知识管理引擎"。内核完全领域无关,航运成为一个可替换的「领域包」。

### ✨ 新增功能

#### 前端:Next.js 专业界面(2026-07-30,反转 ADR-0005)
- **全新 Next.js 16 前端** (`web/`,见 ADR-0008):
  - Next.js 16 + React 19 + Tailwind v4 + shadcn/ui
  - 6 个页面:系统概览/文档管理/知识搜索/知识问答/AI 报告/设置
  - 侧边栏导航 + 后端状态实时指示灯(10s 轮询 `/health`)
  - TypeScript 类型安全,API 客户端完整封装
- **视觉体验大幅提升**:
  - 卡片阴影、圆角、hover 动效,极简现代风格
  - 响应式布局,移动端友好
  - Toast 通知(sonner),加载骨架屏(skeleton)
- **功能增强**:
  - 文档内容预览:点击展开,通过搜索 API 自动拉取切片内容
  - 删除二次确认:Dialog 弹窗,防止误删
  - 四维检索得分可视化:搜索结果显示综合/向量/关键词/时间/标签五项得分
  - RAG 来源追溯:问答回答下方列出参考文档及相关度
  - 实时聊天界面:消息流式展示,自动滚动
- **移除 Streamlit 后台**(2026-07-30):
  - 删除 `admin/` 目录及 Streamlit 依赖
  - `run.sh` 现在启动后端 + Next.js(原 `start-all.sh` 功能已合并)
  - 简化技术栈:只维护一套前端,降低维护成本

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
