# v0.3.0 发布说明 / Release Notes

## 🎯 重大重构:通用内核 + 领域包架构

从"航运知识管理工具"升级为"为航运知识管理优化的**通用**知识管理引擎"。

### 核心亮点

- **领域包系统**:内核完全领域无关,航运成为一个可替换的「领域包」,已验证 maritime ↔ example 自由切换
- **采集器接口**:支持多平台内容采集扩展,已实现网页通用采集器 + 公众号文章专用采集器
- **离线降级**:零 API Key 也能跑,mock 向量 + 规则标签,测试不依赖外部服务
- **中文检索增强**:改用字符 bigram 分词,关键词得分从恒为 0 提升到 0.4+
- **本地零依赖**:SQLite 替代 Postgres,venv 从 5GB 降至 794MB,`bash run.sh` 一键启动

### 新增功能

#### 架构
- 领域包系统(`domains/maritime/` + `domains/example/`)
- 采集器接口(`collectors/`,见 ADR-0004)
- 离线降级机制(embedding/标签/问答三层降级,见 ADR-0007)

#### 文档体系
- 7 份架构决策记录(ADR)
- CONTEXT.md(领域词汇表)
- README/ROADMAP 完全重写
- 5 分钟答辩演示脚本

#### 测试
- 42 项测试(+6),全部通过,< 2 秒
- 中文检索、采集器选择、离线降级全覆盖

### 主要改进

- 数据库:SQLite 作本地默认,生产可切 Postgres
- 依赖精简:删除 10+ 零引用依赖,venv 减小 86%
- 前端决策:删除 `web/` 空壳,Streamlit 作主界面
- 中文关键词检索修复(bigram 分词)
- 工具链:`run.sh` 重写,一键启动/停止/状态

### Bug 修复

- 修复 config.TAGS_CONFIG_PATH 不存在导致崩溃
- 修复 SQLite 引擎参数错误
- 修复中文关键词检索恒为 0

### ⚠️ 破坏性变更

- `.env` 结构调整,默认 SQLite + local 存储
- 标签/提示词/报告改从领域包加载,硬编码已移除
- 生产依赖需单独安装 `requirements-prod.txt`

---

## 📦 安装与快速开始

```bash
git clone https://github.com/你的用户名/小鲸OrcaAI.git
cd 小鲸OrcaAI
bash run.sh
# 浏览器打开 http://localhost:8501
```

详见 [README.md](https://github.com/你的用户名/小鲸OrcaAI/blob/main/README.md)

## 📖 完整更新日志

见 [CHANGELOG.md](https://github.com/你的用户名/小鲸OrcaAI/blob/main/CHANGELOG.md)

## 🙏 致谢

本版本重构由 Claude (Kiro) 协助完成。
