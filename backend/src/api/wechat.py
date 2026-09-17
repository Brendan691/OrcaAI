"""微信机器人 API — 微信公众号接入"""
import hashlib
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..core.config import settings
from ..services.rag_service import rag_service
from ..services.document_processor import document_processor
from ..services.tag_classifier import tag_classifier
from ..services.embedding_service import embedding_service
from ..services.chroma_store import chroma_store

router = APIRouter(prefix="/api/wechat", tags=["微信"])


class WechatMessage(BaseModel):
    """微信公众号消息"""
    ToUserName: str = ""
    FromUserName: str = ""
    CreateTime: int = 0
    MsgType: str = "text"
    Content: str = ""
    MsgId: int = 0
    MediaId: str = ""
    Format: str = ""
    Recognition: str = ""


@router.get("/callback")
async def wechat_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """微信服务器验证"""
    token = settings.WECHAT_TOKEN
    tmp_list = sorted([token, timestamp, nonce])
    tmp_str = "".join(tmp_list)
    tmp_str = hashlib.sha1(tmp_str.encode()).hexdigest()

    if tmp_str == signature:
        return echostr
    raise HTTPException(403, "验证失败")


@router.post("/callback")
async def wechat_callback(request: Request):
    """处理微信消息"""
    body = await request.body()
    # 解析 XML 消息
    xml_text = body.decode("utf-8")
    # 简化处理：提取文本内容
    import re
    content_match = re.search(r"<Content><!\[CDATA\[(.*?)\]\]></Content>", xml_text)
    from_user_match = re.search(r"<FromUserName><!\[CDATA\[(.*?)\]\]></FromUserName>", xml_text)
    to_user_match = re.search(r"<ToUserName><!\[CDATA\[(.*?)\]\]></ToUserName>", xml_text)
    msg_type_match = re.search(r"<MsgType><!\[CDATA\[(.*?)\]\]></MsgType>", xml_text)

    if not content_match or not from_user_match or not to_user_match:
        return "success"

    content = content_match.group(1)
    from_user = from_user_match.group(1)
    to_user = to_user_match.group(1)
    msg_type = msg_type_match.group(1) if msg_type_match else "text"

    reply = ""

    # 语音消息
    if msg_type == "voice":
        recognition_match = re.search(r"<Recognition><!\[CDATA\[(.*?)\]\]></Recognition>", xml_text)
        if recognition_match:
            content = recognition_match.group(1)
        else:
            reply = "收到语音消息，但未能识别文字内容。请尝试发送文字。"
            return _build_text_reply(from_user, to_user, reply)

    # 处理命令
    if content.startswith("/") or content.startswith("。"):
        reply = await _handle_command(content, from_user)
    else:
        # 默认：知识库问答
        reply = await _handle_qa(content)

    return _build_text_reply(from_user, to_user, reply)


def _build_text_reply(to_user: str, from_user: str, content: str) -> str:
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


async def _handle_command(content: str, user_id: str) -> str:
    """处理用户命令"""
    content = content.lstrip("/。")

    if content in ("帮助", "help"):
        return """🐳 小鲸 OrcaAI — 海事知识助手

命令列表：
• /帮助 — 显示此消息
• /问答 <问题> — 向知识库提问
• /周报 — 生成航运市场周报
• /标签 <内容> — 分析海事分类标签

你也可以直接发送问题，我会从知识库中寻找答案。"""

    if content.startswith("问答") or content.startswith("qa"):
        question = content.replace("问答", "").replace("qa", "").strip()
        if question:
            return await _handle_qa(question)
        return "请在 /问答 后输入你的问题。"

    if content in ("周报", "weekly"):
        return "周报生成功能开发中。请前往 Web 管理后台使用完整报告生成功能。\nhttp://localhost:8501"

    if content.startswith("标签"):
        text = content.replace("标签", "").strip()
        if text:
            tags = tag_classifier.classify(text, use_llm=True)
            return f"""📊 标签分析结果：
🚢 业务类型：{', '.join(tags.business_type) or '未识别'}
🌍 地理区域：{', '.join(tags.geographic_region) or '未识别'}
📰 主题类别：{', '.join(tags.topic_category) or '未识别'}
⚡ 事件性质：{', '.join(tags.event_nature) or '未识别'}
置信度：{tags.confidence:.0%}"""
        return "请在 /标签 后输入需要分析的内容。"

    return await _handle_qa(content)


async def _handle_qa(question: str) -> str:
    """知识库问答"""
    if not question.strip():
        return "请输入你的问题。"

    try:
        from ..models.document import ChatRequest
        result = await rag_service.chat(ChatRequest(message=question))

        if result.confidence < 0.3:
            return f"{result.answer}\n\n⚠️ 知识库中相关度较低，建议补充相关资料后再提问。"

        source_info = ""
        if result.sources:
            source_info = "\n\n📚 参考来源："
            for i, src in enumerate(result.sources[:3], 1):
                source_info += f"\n{i}. {src.title}"

        return result.answer + source_info
    except Exception as e:
        return f"问答服务暂不可用：{str(e)}\n请检查后端服务是否正在运行。"
