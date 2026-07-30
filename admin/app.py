#!/usr/bin/env python3
# ============================================================
# 文件：admin/app.py
# 作用：小鲸 OrcaAI 的 Web 管理后台（基于 Streamlit）
# 用法：streamlit run admin/app.py
#       然后在浏览器打开 http://localhost:8501
# 依赖：pip install streamlit
# ============================================================
"""小鲸 OrcaAI - Web 管理后台

这个文件提供可视化的知识库管理界面，包括：
- 系统概览：查看文档数量、系统状态
- 文档管理：上传、查看、删除文档
- 知识搜索：搜索知识库内容
- 知识问答：直接向知识库提问
"""

import json
import sys
from pathlib import Path

import requests
import streamlit as st

# 将 backend/src 加入路径，以便直接运行
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="小鲸 OrcaAI - 管理后台",
    page_icon="🐳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 样式
# ============================================================
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #1a73e8; margin-bottom: 0.5rem; }
    .stat-card { background: #f0f7ff; border-radius: 12px; padding: 20px; text-align: center; }
    .stat-value { font-size: 2rem; font-weight: 700; color: #1a73e8; }
    .stat-label { font-size: 0.9rem; color: #666; }
    .doc-card { background: #fff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
    .tag-chip { display: inline-block; background: #e8f0fe; color: #1a73e8; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; margin: 2px; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 辅助函数
# ============================================================
def get_api_base():
    """获取后端 API 地址（可在设置页修改）"""
    return st.session_state.get("api_base", "http://localhost:8000")


def api_call(method, path, **kwargs):
    """统一的 API 调用封装"""
    url = f"{get_api_base()}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10, **kwargs.get("req_kw", {}))
        elif method == "POST":
            resp = requests.post(url, json=kwargs.get("data"), timeout=30)
        elif method == "DELETE":
            resp = requests.delete(url, timeout=10)
        else:
            return None
        return resp.json() if resp.ok else None
    except Exception:
        return None


def render_tags(tags):
    """渲染标签"""
    all_tags = []
    if isinstance(tags, dict):
        for dim, values in tags.items():
            all_tags.extend(values)
    elif isinstance(tags, list):
        all_tags = tags
    html = "".join(f'<span class="tag-chip">{t}</span>' for t in all_tags[:8])
    st.markdown(html, unsafe_allow_html=True) if html else st.text("无标签")


# ============================================================
# 侧边栏导航
# ============================================================
with st.sidebar:
    st.markdown("## 🐳 小鲸 OrcaAI")
    st.markdown("*海事知识管理平台*")
    st.divider()

    page = st.radio(
        "导航",
        ["📊 系统概览", "📄 文档管理", "🔍 知识搜索", "💬 知识问答", "🧩 插件安装", "⚙️ 设置"],
        label_visibility="collapsed",
    )

    st.divider()
    # 系统状态指示灯
    status_data = api_call("GET", "/health")
    if status_data and status_data.get("status") == "healthy":
        st.success("🟢 后端服务运行中")
    else:
        st.error("🔴 后端未连接\n\n请在项目根目录运行 `bash run.sh` 启动")

    st.caption(f"API: {get_api_base()}")
    st.caption("v0.3.0 | Made with ❤️")

# ============================================================
# 页面 1：系统概览
# ============================================================
if page == "📊 系统概览":
    st.markdown('<p class="main-header">📊 系统概览</p>', unsafe_allow_html=True)
    st.markdown("快速了解知识库的整体状况")

    # 获取状态
    sys_status = api_call("GET", "/api/status")
    docs_list = api_call("GET", "/api/documents")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        doc_count = sys_status.get("document_count", 0) if sys_status else 0
        st.markdown(f'<p class="stat-value">{doc_count}</p>', unsafe_allow_html=True)
        st.markdown('<p class="stat-label">文档切片数</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        total = docs_list.get("total", 0) if docs_list else 0
        st.markdown(f'<p class="stat-value">{total}</p>', unsafe_allow_html=True)
        st.markdown('<p class="stat-label">收藏文档数</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.markdown('<p class="stat-value">4</p>', unsafe_allow_html=True)
        st.markdown('<p class="stat-label">标签维度</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        tag_data = api_call("GET", "/api/tags")
        total_tags = sum(len(v["values"]) for v in tag_data.get("dimensions", {}).values()) if tag_data else 0
        st.markdown(f'<p class="stat-value">{total_tags}</p>', unsafe_allow_html=True)
        st.markdown('<p class="stat-label">标签总数</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 最近文档
    st.markdown("### 📋 最近收藏的文档")
    if docs_list and docs_list.get("documents"):
        for doc in docs_list["documents"][:10]:
            with st.expander(f"{doc.get('title', '未命名')}  [{doc.get('doc_id', '')[:8]}...]"):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"**来源**: {doc.get('url', '直接输入')}")
                    st.markdown(f"**时间**: {doc.get('created_at', '未知')}")
                    st.markdown("**标签**:")
                    render_tags(doc.get("tags", {}))
                with col_b:
                    if st.button("🗑️ 删除", key=f"del_{doc['doc_id']}"):
                        api_call("DELETE", f"/api/documents/{doc['doc_id']}")
                        st.rerun()
    else:
        st.info("还没有收藏任何文档。使用 Chrome 插件一键收藏，或前往「文档管理」手动添加。")


# ============================================================
# 页面 2：文档管理
# ============================================================
elif page == "📄 文档管理":
    st.markdown('<p class="main-header">📄 文档管理</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 文档列表", "➕ 手动添加"])

    with tab1:
        docs_list = api_call("GET", "/api/documents")
        if docs_list and docs_list.get("documents"):
            st.markdown(f"共 {docs_list['total']} 篇文档")

            for doc in docs_list["documents"]:
                with st.container():
                    col1, col2, col3 = st.columns([5, 1, 1])
                    with col1:
                        st.markdown(f"**{doc.get('title', '未命名')}**")
                        st.caption(f"ID: {doc.get('doc_id', '')[:16]}...")
                        render_tags(doc.get("tags", {}))
                    with col2:
                        if doc.get("url"):
                            st.markdown(f"[🔗 原文]({doc['url']})")
                    with col3:
                        if st.button("🗑️", key=f"del2_{doc['doc_id']}"):
                            result = api_call("DELETE", f"/api/documents/{doc['doc_id']}")
                            if result:
                                st.success("已删除")
                                st.rerun()
                    st.divider()
        else:
            st.info("知识库还是空的，去添加第一篇文档吧！")

    with tab2:
        st.markdown("### 手动添加文档")

        add_method = st.radio("添加方式", ["粘贴网页链接", "直接输入文本"], horizontal=True)

        if add_method == "粘贴网页链接":
            url = st.text_input("网页链接", placeholder="https://...")
            if st.button("📥 解析并保存", type="primary") and url:
                with st.spinner("正在解析网页..."):
                    result = api_call("POST", "/api/documents/upload", data={"url": url})
                if result and result.get("success"):
                    st.success(f"✅ 保存成功！文档 ID: {result['doc_id']}")
                    if result.get("tags"):
                        st.markdown("**自动标签：**")
                        render_tags(result["tags"].get("business_type", []) +
                                    result["tags"].get("topic_category", [])[:2])
                else:
                    st.error(f"保存失败：{result.get('message', '未知错误') if result else '后端未连接'}")

        else:
            title = st.text_input("标题（可选）", placeholder="输入文档标题")
            content = st.text_area("文本内容", height=200, placeholder="粘贴要收藏的文本内容...")
            if st.button("📝 保存到知识库", type="primary") and content:
                with st.spinner("正在处理..."):
                    result = api_call("POST", "/api/documents/upload",
                                      data={"content": content, "title": title or None})
                if result and result.get("success"):
                    st.success(f"✅ 保存成功！")
                    if result.get("tags"):
                        st.markdown("**自动标签：**")
                        all_tags = []
                        tags = result["tags"]
                        for dim in ["business_type", "geographic_region", "topic_category", "event_nature"]:
                            all_tags.extend(tags.get(dim, []))
                        render_tags(all_tags)
                else:
                    st.error(f"保存失败：{result.get('message', '未知错误') if result else '后端未连接'}")


# ============================================================
# 页面 3：知识搜索
# ============================================================
elif page == "🔍 知识搜索":
    st.markdown('<p class="main-header">🔍 知识搜索</p>', unsafe_allow_html=True)
    st.markdown("搜索已收藏的海事知识，支持语义搜索 + 关键词匹配")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("搜索关键词", placeholder="例如：集装箱运价走势、港口拥堵情况...")
    with col2:
        top_k = st.selectbox("返回数量", [3, 5, 10, 20], index=1)

    if query and st.button("🔍 搜索", type="primary"):
        with st.spinner("正在检索..."):
            result = api_call("POST", "/api/search", data={"query": query, "top_k": top_k})

        if result and result.get("results"):
            st.markdown(f"找到 {result['total']} 条相关结果：")

            for i, hit in enumerate(result["results"], 1):
                with st.container():
                    st.markdown(f"### {i}. {hit.get('title', '未命名')}")
                    st.markdown(f"**综合得分**: {hit.get('score', 0):.3f} | "
                                f"向量: {hit.get('vector_score', 0):.3f} | "
                                f"关键词: {hit.get('keyword_score', 0):.3f}")
                    st.markdown(hit.get("content", "")[:300] + "..." if len(hit.get("content", "")) > 300 else hit.get("content", ""))
                    if hit.get("url"):
                        st.caption(f"来源: {hit['url']}")
                    st.divider()
        elif result:
            st.info("未找到相关内容，尝试其他关键词。")
        else:
            st.error("搜索失败，请检查后端是否运行。")


# ============================================================
# 页面 4：知识问答
# ============================================================
elif page == "💬 知识问答":
    st.markdown('<p class="main-header">💬 知识问答</p>', unsafe_allow_html=True)
    st.markdown("基于收藏的知识库进行 AI 问答。AI 只会根据你收藏的内容回答。")

    # 聊天历史
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 显示历史消息
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 输入框
    question = st.chat_input("向知识库提问...")
    if question:
        # 显示用户消息
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state.chat_history.append({"role": "user", "content": question})

        # 调用 API
        with st.chat_message("assistant"):
            with st.spinner("小鲸正在思考..."):
                result = api_call("POST", "/api/chat", data={"message": question})

            if result and result.get("answer"):
                answer = result["answer"]
                if result.get("sources"):
                    answer += "\n\n---\n**📚 参考来源：**"
                    for i, src in enumerate(result["sources"], 1):
                        answer += f"\n- [{i}] {src.get('title', '未知')}（相关度: {src.get('score', 0):.0%}）"
                st.markdown(answer)
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
            else:
                error_msg = "抱歉，后端服务未连接或知识库为空。请检查后端是否运行。" if not result else "知识库中暂未找到相关内容。"
                st.error(error_msg)
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

    if st.button("🗑️ 清空对话"):
        st.session_state.chat_history = []
        st.rerun()


# ============================================================
# 页面 5：插件安装
# ============================================================
elif page == "🧩 插件安装":
    st.markdown('<p class="main-header">🧩 Chrome 插件安装指南</p>', unsafe_allow_html=True)
    st.markdown("安装浏览器插件后，浏览网页时一键收藏到知识库")

    st.markdown("---")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### 📌 安装步骤")
        st.markdown("""
        **1.** 打开 Chrome 浏览器

        **2.** 地址栏输入：
        `chrome://extensions/`

        **3.** 打开右上角
        **开发者模式** 开关

        **4.** 点击左上角
        **加载已解压的扩展程序**

        **5.** 选择项目的
        `extension/` 文件夹

        **6.** 完成！工具栏出现
        小鲸图标 🐳
        """)

    with col2:
        st.info("""
        💡 **找不到图标？**

        点击 Chrome 工具栏右侧的拼图图标 🧩，找到"小鲸OrcaAI"，点图钉 📌 固定到工具栏。

        ---

        ⚙️ **后端地址设置**

        插件默认连接 `http://localhost:8000`。
        如果后端部署在其他地址（如服务器），点击插件图标后在下方的设置中修改。

        ---

        🔄 **插件更新**

        改完插件代码后，到 `chrome://extensions/` 找到插件，点右下角的刷新按钮 🔄 即可。
        """)

    st.markdown("---")
    st.markdown("### 🎯 使用方法")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**📥 收藏网页**")
        st.markdown("浏览航运文章 → 点插件图标 → 点「收藏到知识库」→ AI 自动打标签")
    with col_b:
        st.markdown("**💬 知识问答**")
        st.markdown("点插件图标 → 下方问答框输入问题 → 回车 → AI 从知识库找答案")
    with col_c:
        st.markdown("**🔍 管理知识**")
        st.markdown("打开管理后台 → 查看/搜索/删除已收藏的文档")

    st.markdown("---")
    st.caption("💡 提示：插件和后端必须同时运行。如果收藏失败，检查 `bash run.sh` 是否在运行。")

# ============================================================
# 页面 6：设置
# ============================================================
elif page == "⚙️ 设置":
    st.markdown('<p class="main-header">⚙️ 设置</p>', unsafe_allow_html=True)

    # API 地址
    st.markdown("### 🔗 后端 API 地址")
    api_base = st.text_input(
        "API 地址",
        value=st.session_state.get("api_base", "http://localhost:8000"),
        placeholder="http://localhost:8000",
        help="后端服务的地址。本地开发默认 http://localhost:8000"
    )
    if api_base != st.session_state.get("api_base"):
        st.session_state.api_base = api_base
        st.success("已更新")

    st.divider()

    # 标签体系展示
    st.markdown("### 🏷️ 海事四维标签体系")
    tag_data = api_call("GET", "/api/tags")

    if tag_data:
        dims = tag_data.get("dimensions", {})
        cols = st.columns(4)
        dim_icons = {"business_type": "🚢", "geographic_region": "🌍",
                     "topic_category": "📰", "event_nature": "⚡"}
        dim_names = {"business_type": "业务类型", "geographic_region": "地理区域",
                     "topic_category": "主题类别", "event_nature": "事件性质"}

        for idx, (dim_key, dim_info) in enumerate(dims.items()):
            with cols[idx]:
                icon = dim_icons.get(dim_key, "📌")
                name = dim_names.get(dim_key, dim_info.get("display_name", dim_key))
                st.markdown(f"**{icon} {name}**")
                values = dim_info.get("values", [])
                for v in values:
                    st.markdown(f"- {v}")
    else:
        st.warning("无法获取标签体系，请检查后端是否运行。")

    st.divider()

    # 关于
    st.markdown("### ℹ️ 关于小鲸 OrcaAI")
    st.markdown("""
    **小鲸 OrcaAI** 是一款 AI 驱动的一站式海事知识管理工具，专为航运、物流、供应链领域的从业者和研究者设计。

    **核心功能：**
    - 🔖 一键收藏网页，AI 自动打标签
    - 💬 知识库 AI 问答
    - 🔍 混合相似度智能搜索
    - 🏷️ 海事四维标签体系

    **技术栈：** FastAPI + Chroma + 通义千问 + Streamlit

    **版本：** v0.3.0（通用内核 + 领域包架构）
    """)
