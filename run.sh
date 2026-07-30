#!/bin/bash
# ============================================================
# 小鲸 OrcaAI — 一键启动(本地零依赖模式,见 docs/adr/0002)
#   bash run.sh          启动后端 + 管理后台
#   bash run.sh stop     停止
#   bash run.sh status   查看状态
# 生产部署(Postgres/MinIO 等)见 docker-compose.yml 与 README。
# ============================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'

if [ "$1" = "stop" ]; then
  pkill -f "uvicorn src.main:app" 2>/dev/null || true
  pkill -f "streamlit run" 2>/dev/null || true
  echo -e "${GREEN}✅ 已停止${NC}"; exit 0
fi

if [ "$1" = "status" ]; then
  curl -s http://localhost:8000/health >/dev/null 2>&1 \
    && echo -e "  🟢 后端 API  http://localhost:8000" \
    || echo -e "  🔴 后端 API  未运行"
  curl -s http://localhost:8501 >/dev/null 2>&1 \
    && echo -e "  🟢 管理后台  http://localhost:8501" \
    || echo -e "  🔴 管理后台  未运行"
  exit 0
fi

echo -e "${BLUE}  🐳 小鲸 OrcaAI —— 为航运知识管理优化的通用知识管理工具${NC}"

# 1) 首次运行:准备 .env
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo -e "${YELLOW}📋 已生成 .env。请填入 DASHSCOPE_API_KEY 后重跑(无 Key 也能启动,走离线降级)。${NC}"
fi

# 2) 虚拟环境
if [ ! -d ".venv" ]; then
  echo -e "${YELLOW}📦 创建虚拟环境...${NC}"
  python3 -m venv .venv
fi

# 3) 依赖(用清华源加速;已装则跳过)
if ! .venv/bin/python -c "import fastapi, chromadb, streamlit" 2>/dev/null; then
  echo -e "${YELLOW}📥 安装依赖(清华源)...${NC}"
  PIP_INDEX_URL=${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple} \
    .venv/bin/python -m pip install -q -r backend/requirements.txt
fi

# 4) 生成插件图标(若缺)
if [ ! -f "extension/icons/icon16.png" ]; then
  .venv/bin/python extension/icons/generate_icons.py 2>/dev/null || true
fi

# 5) 启动后端(在 backend/ 目录,确保相对路径一致)
echo -e "${BLUE}🚀 启动后端...${NC}"
( cd backend && nohup ../.venv/bin/python -m uvicorn src.main:app \
    --host 0.0.0.0 --port 8000 --reload > /tmp/orcaai-backend.log 2>&1 & )

# 等后端就绪
for i in $(seq 1 30); do
  curl -s http://localhost:8000/health >/dev/null 2>&1 && break
  sleep 0.5
done

# 6) 启动管理后台
echo -e "${BLUE}🚀 启动管理后台...${NC}"
nohup .venv/bin/python -m streamlit run admin/app.py \
  --server.port 8501 --server.headless true \
  --browser.gatherUsageStats false > /tmp/orcaai-admin.log 2>&1 &

sleep 3
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 已启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  📡 后端 API   ${BLUE}http://localhost:8000${NC}"
echo -e "  📖 API 文档   ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  📊 管理后台   ${BLUE}http://localhost:8501${NC}"
echo -e "  停止:${YELLOW}bash run.sh stop${NC}   状态:${YELLOW}bash run.sh status${NC}"

command -v open >/dev/null && { sleep 1; open http://localhost:8501 2>/dev/null || true; }
