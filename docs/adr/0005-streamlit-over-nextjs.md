# 5. 主界面用 Streamlit,移除未完成的 Next.js 前端

- 状态:已接受
- 日期:2026-07-27

## 背景

代码库里同时存在三个前端入口:Chrome 插件、Streamlit 管理后台、`web/` 下的 Next.js 应用。其中 `web/` 只有 5 个文件(`layout.tsx` / `page.tsx` / `globals.css` / `ThemeProvider.tsx` / `api.ts`),没有文档列表、搜索、问答任何实际页面,README 从未提及——是个未完成的空壳。

维护者是一名代码初学者、Python 尚不熟练,由一人维护。同时维护 Python 后端 + React/TypeScript 前端两套技术栈不现实。

## 决策

- **移除 `web/`**(Next.js 空壳)。
- 用 **Streamlit** 作为主界面:纯 Python,维护者能读能改;概览/文档管理/搜索/问答四个页面已具雏形。
- 保留 **Chrome 插件**作为核心的"一键收藏"入口。

完整的用户闭环由此成立:

```
Chrome 插件(收藏) → FastAPI 后端(打标签+入库) → Streamlit 后台(浏览/搜索/问答)
```

## 后果

- 好处:只需一套技术栈(Python),学习负担减半;省去 `node_modules`(约 500MB)。
- 好处:删掉空壳目录,消除"毛坯感"来源之一。
- 代价:界面观感不如定制 React。可接受——Streamlit 能改主题,四页做扎实足以支撑演示与答辩。
- 边界:若未来需要面向公众的高定制 Web 端,再引入前端框架,届时后端 API 已就绪(插件已在用)。
