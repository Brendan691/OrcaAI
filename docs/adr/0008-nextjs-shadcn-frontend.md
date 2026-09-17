# ADR-0008: 采用 Next.js + shadcn/ui 作为主前端(反转 ADR-0005)

**日期**: 2026-07-30  
**状态**: 已接受 (反转 ADR-0005)  
**决策者**: 项目作者

---

## 背景

ADR-0005 选择 Streamlit 作为前端方案,理由是:
1. 纯 Python,学习成本低
2. 快速搭建 MVP
3. 避免前后端两套技术栈

但用户在使用过程中发现:
1. **视觉体验不足**:Streamlit 界面"像毛坯",缺少现代感,难以达到答辩演示的专业水准
2. **交互限制**:每次交互全页重跑(rerun),无法实现丝滑的局部动效和复杂交互
3. **用户明确表示**:"前端交给 AI 就行,我们用行业标准"——学习成本的顾虑不再成立

此时项目有两个关键优势:
- 后端是干净的 REST API,前后端完全解耦,换前端不影响后端
- 前端脚手架与组件库成熟,可按需引入,不阻塞后端迭代

---

## 决策

**采用 Next.js 16 + React 19 + Tailwind v4 + shadcn/ui 作为主前端**,替代 Streamlit。

技术栈:
- **框架**: Next.js 16(App Router)+ React 19
- **样式**: Tailwind CSS v4
- **组件库**: shadcn/ui(现代、极简、可定制,答辩演示效果好)
- **语言**: TypeScript
- **图标**: lucide-react

---

## 方案对比

| 方案 | 视觉专业度 | 交互体验 | 学习成本 | 行业认可度 | 答辩演示效果 |
|------|-----------|---------|---------|-----------|-------------|
| **Streamlit(ADR-0005)** | 🟡 整洁但普通 | 🔴 全页 rerun | 🟢 纯 Python | 🟡 数据科学界 | 🟡 功能可演示但不出彩 |
| **Next.js + shadcn/ui** | 🟢 专业现代 | 🟢 丝滑局部更新 | 🟢 组件化开发 | 🟢 工业标准 | 🟢 视觉突出、可写进简历 |

---

## 实施细节

### 目录结构
```
web/
├── src/
│   ├── app/                    # 页面(App Router)
│   │   ├── page.tsx           # 系统概览
│   │   ├── documents/page.tsx # 文档管理
│   │   ├── search/page.tsx    # 知识搜索
│   │   ├── chat/page.tsx      # 知识问答
│   │   ├── reports/page.tsx   # AI 报告
│   │   └── settings/page.tsx  # 设置
│   ├── components/
│   │   ├── ui/                # shadcn 组件
│   │   ├── sidebar.tsx        # 侧边栏导航
│   │   └── tag-list.tsx       # 标签展示组件
│   └── lib/
│       ├── api.ts             # 后端 API 客户端
│       └── utils.ts           # 工具函数
```

### API 客户端设计
- 封装所有后端接口(`/api/documents`,`/api/search`,`/api/chat` 等)
- 统一错误处理和 JSON 解析
- TypeScript 类型定义与后端 Pydantic 模型对应

### 组件复用
- `<TagList>`:展示文档四维标签,所有页面复用
- `<Sidebar>`:导航 + 后端状态指示灯,10 秒轮询 `/health`
- shadcn/ui 组件:Button、Card、Dialog、Tabs、Input、Textarea 等开箱即用

### 关键特性保留
- **内容预览**:文档管理页点击展开,通过搜索 API 拉取切片内容
- **二次确认删除**:Dialog 弹窗确认,防止误删
- **四维检索得分**:搜索结果显示综合/向量/关键词/时间/标签五项得分
- **RAG 来源追溯**:问答回答下方列出参考文档及相关度

---

## 优势

1. **视觉专业**:shadcn/ui 的极简现代风格,卡片阴影、圆角、hover 动效,答辩演示远超 Streamlit
2. **行业标准**:React + Next.js 是前端市场占有率第一的组合,可写进简历
3. **前后端解耦**:后端 FastAPI 代码一行不用改,前端独立迭代
4. **组件化开发**:组件库覆盖常见交互,无需深入研究 React 细节即可维护
5. **扩展性强**:未来可轻松加动画、拖拽、实时更新等 Streamlit 做不了的交互

---

## 劣势与风险

1. **依赖增多**:node_modules ~500MB(但磁盘剩余 37GB,可接受)
2. **两个服务**:需要同时跑后端(8000)+ 前端(3000),但可用脚本一键启动
3. **调试需要浏览器**:不像 Streamlit 自带热重载提示,需要开发者工具

---

## 迁移路径


**当前状态**(2026-07-30):
- Streamlit 已删除(`admin/` 目录)
- Next.js 前端在 `web/` 作为唯一前端界面
- `run.sh` 启动后端 + Next.js 全套,一条命令搞定


---

## 后果

### 正面
- 答辩演示效果显著提升,界面专业度达到商业产品水准
- 技术栈对齐行业标准,项目经历可用于求职
- 前端代码结构清晰,TypeScript 类型安全,易于扩展

### 中性
- 需要维护两个目录(`backend/` Python,`web/` TypeScript),但分工清晰,影响不大
- npm 装包首次较慢(已配置国内镜像 npmmirror.com 加速)

### 负面
- 无(用户已明确选择行业标准,AI 承担学习成本)

---

## 相关决策

- **ADR-0005**(被反转):选择 Streamlit 作为前端
- **ADR-0002**:本地优先存储(SQLite)— 前后端解耦使反转前端成为可能
- **ADR-0004**:采集器接口 — 后端 API 设计良好,前端切换无需重构

---

## 验证

- ✅ 6 个页面全部实现(概览/文档/搜索/问答/报告/设置)
- ✅ dev server 启动成功(http://localhost:3000)
- ✅ 首页 HTTP 200,无编译错误
- ✅ 后端 API 客户端封装完成,类型定义齐全
- ✅ shadcn/ui 组件库安装完成(11 个组件)

---

## 参考

- [Next.js 官方文档](https://nextjs.org/)
- [shadcn/ui 组件库](https://ui.shadcn.com/)
- [Tailwind CSS v4](https://tailwindcss.com/)
