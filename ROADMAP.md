# 小鲸 OrcaAI 路线图

本文件记录**尚未实现、暂缓或已知损坏**的部分。已实现的能力见 [README.md](README.md),历史变更见 [CHANGELOG.md](CHANGELOG.md)。

当前版本:**`v0.4.0`**

---

## 一、下一步优先级

### P0 —— 决定"能不能写进论文和答辩"的三件事

1. **人工多级 qrels**。CARE 的独立确认集是模型生成的**单目标银标**(48 文档 / 94 查询),每条查询只标了一个相关文档。必须由独立标注者做多等级标注,否则"检索显著提升"只能限定在银标范围内,不能声称通用优越。
2. **多模态入库**。图片 OCR、PDF 页码级定位、表格结构解析、音频 ASR —— 这是立项承诺里还没兑现的部分,目前系统只处理文本。
3. **前端 E2E 与 CI**。把"后端 68 项测试 + 前端生产构建 + 论文数据审计"固化成 CI,替代现在的手工验证。

### P1 —— 工程健壮性

- **修复并验证 Docker 部署**(具体坏点见第五节)。
- **并发与性能压测**:SQLite + Chroma 在数百文档、多用户并发下的表现尚未测量。
- **成本与配额统计**:DashScope 与 Tavily 的调用量、失败率、费用目前没有面板。

### P2 —— 采集面扩展

见第二节"愿景"的分期计划。

---

## 二、愿景:全平台内容采集

> 在任何软件(小红书 / 抖音 / 公众号文章等)看到视频、图文或文章,都能一键识别,
> 转成结构化数据存入关联账户的知识库;用户能回看收藏,并通过结构化数据定位回原视频/文章网址。

这是项目的核心增长方向。它把「知识管理器」从"我主动收藏网页"扩展到"我在任何地方看到的内容都能沉淀"。

### 架构基础(已就绪)

多平台采集的地基已经打好 —— **采集器接口 `Collector`**(见 [ADR-0004](docs/adr/0004-collector-interface.md)):

```python
class Collector(Protocol):
    source_type: str
    def can_handle(self, source: str) -> bool: ...
    def collect(self, source: str) -> RawDocument: ...
```

入库管线(切片 → 向量化 → 打标签 → 存储)对所有采集器共用。
**新增一个平台 = 新增一个实现 `Collector` 的类 + 注册一行**,内核与管线完全不动。
现已实现:`WebCollector`(通用网页)、`WechatArticleCollector`(公众号文章专用提取)。

### 各平台难度与技术路线

| 平台 | 输入形态 | 主要难点 | 技术路线 | 优先级 |
|------|---------|---------|---------|--------|
| **公众号文章** | 公开网页链接 | 基本无(已做 demo) | HTML 解析 `#js_content` | ✅ 已有 demo |
| **小红书图文** | 分享链接 | 需登录态/反爬;正文在动态渲染里 | 分享链接解析 + 移动端 API 或无头浏览器 | P1 |
| **小红书视频 / 抖音** | 分享链接 | 内容在视频里,需语音转文字 | 抽取视频 → ASR(语音识别)转文字 → 入库 | P2 |
| **微博 / B站** | 链接 | 各家结构不同、部分需登录 | 每家一个专用 Collector | P3 |
| **PDF / 图片** | 本地文件或链接 | 扫描件需 OCR;要定位到页码 | OCR + 页码级定位元数据 | P1 |

### 关键设计:可定位回原文

每个 `RawDocument` 都带 `source_url`,入库后存入元数据。
无论内容被切片、向量化成什么样,都能通过结构化数据**定位回原视频/文章网址** —— 满足"回看收藏并跳转原文"的需求。
文本类文档已经做到切片级 + 字符范围 + 行号定位;多模态要补齐"页码 / 时间戳"这一层。

### 分期计划

- **Phase 1(采集能力)**:小红书图文采集器 + 移动端分享链接解析。用户账户已就绪(功能④),收藏自动归属账户。
- **Phase 2(多模态)**:视频/音频 → ASR 转文字入库;扫描件 PDF → OCR,并带上页码与字符框定位。
- **Phase 3(采集端)**:除 Chrome 插件外,做移动端"分享到小鲸"入口(iOS / Android 分享扩展)。

---

## 三、暂缓功能(代码已实现,默认未启用)

| 功能 | 代码位置 | 暂缓原因 | 启用条件 |
|------|---------|---------|---------|
| **微信公众号问答机器人** | `backend/src/api/wechat.py` | 需公网服务器 + 已认证公众号 + ICP 备案 | 部署到公网后注册路由 |

> 注意区分:公众号**文章采集**(把文章存进知识库)**已在默认链路里**;这里说的是公众号**机器人**(在公众号里直接对话)。

> 联网搜索已经不是暂缓项:它现在是**默认能力**,由 Tavily 托管 API 提供,失败时可降级 Bing,
> 路由已在 `main.py` 注册,前端有开关。实现见 `backend/src/services/search_service.py`,
> 调用链见 README 的"检索链路"一节。

---

## 四、工程 backlog

- **中文分词**:当前用字符 bigram(见 [ADR-0006](docs/adr/0006-hybrid-search.md)),够用但不如词典分词精准。数据量大时可评估引入 jieba。
- **数据库迁移**:Alembic 尚未启用。切 Postgres 之前必须补上,否则表结构变更只能手工处理。
- **生产服务栈**:Postgres / MinIO / Meilisearch 的适配代码已在 `services/file_service.py` 与 `requirements-prod.txt` 就位,但 `docker-compose.yml` 需要先修好才能用(见第五节)。
- **检索权重寻优**:`hybrid_search.optimize_weights` 的网格搜索保留作为离线诊断工具;线上路径已改用 AEF 自适应权重 + CARE 交叉编码器重排。
- **质量门禁**:pytest 覆盖率门槛、ruff / mypy 静态检查、提交前钩子都还没接入。
- **结构化日志**:目前是 SQLAlchemy 与标准日志混用,需要统一的请求 ID 与检索诊断日志格式。

---

## 五、已知坏点(需修复,尚未实测)

本机未安装 Docker,以下问题由代码阅读确认,**没有经过实际构建验证**:

1. `Dockerfile` 仍执行 `COPY admin/ admin/` 与 `COPY searxng/ searxng/`,而这两个目录已在 v0.4.0 删除 → 镜像构建必然失败。
2. `Dockerfile` 的 `CMD` 写的是 `uvicorn backend.src.main:app`,但 `backend/` 不是 Python 包(没有 `__init__.py`),实际入口是 `cd backend && uvicorn src.main:app`。
3. `docker-compose.yml` 仍保留 `admin`(Streamlit)与 `searxng` 两个服务,它们挂载的 `admin/app.py`、`searxng/settings.yml`、`searxng/limiter.toml` 都已不存在。
4. `web/Dockerfile` 不存在,compose 里的 `web` 服务无法构建。
5. compose 里后端传的是 `MINIO_ENDPOINT`,而配置读取的是 `S3_ENDPOINT`;Chroma 的挂载路径也与 `CHROMA_PERSIST_DIR` 不一致。

结论:**当前唯一验证过的启动方式是本地 `bash run.sh`**。Docker 路径在修好并实测之前,不要写进答辩材料。
