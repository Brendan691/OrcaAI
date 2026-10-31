"""pytest 共享配置"""
import os
import sys
from pathlib import Path

# 将 backend 目录加入 Python 路径
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 测试时不调用真实 LLM，使用规则引擎。显式覆盖 .env，避免测试进程继承真实凭证。
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["QWEN38_API_KEY"] = ""
os.environ["QWEN38_BASE_URL"] = ""
os.environ["QWEN38_MODEL"] = ""

# 单元测试不依赖外部 sidecar：固定走 dashscope 分支（无 Key 时自动降级为 mock）。
# 否则 `.env` 里的 EMBEDDING_BACKEND=local 会让 mock 向量测试实际去请求 8765，
# 在 sidecar 未起或磁盘短暂不可用时随机失败。
os.environ["EMBEDDING_BACKEND"] = "dashscope"
os.environ["RERANK_ENABLED"] = "false"
