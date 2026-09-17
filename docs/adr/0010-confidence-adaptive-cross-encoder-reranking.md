# ADR-0010: 使用 CARE 做置信度自适应 Cross-Encoder 重排

- 状态: Accepted
- 日期: 2026-08-25

## 背景

AEF 能解释并审计向量、词项、时间和标签信号,但第一阶段检索器无法直接建模查询与候选文本的细粒度交互。开发实验还发现,通用聊天模型列表重排会降低检索质量,且平均延迟约 5.52 秒。

## 决策

在 AEF 之后增加可选 CARE 阶段。专用 `gte-rerank-v2` 对前 10 个候选打分。令 `m_a` 为 AEF top-1 与 top-2 分数间隔,`m_g` 为 GTE 对应间隔,逐查询融合权重为:

```text
alpha = clip(0.4 + 0.8 * m_g / (m_g + m_a + 1e-8), 0, 1)
```

最终排序融合 AEF reciprocal rank、GTE reciprocal rank 和 GTE relevance score。参数在第二开发集冻结,第三批独立确认集只评估一次。

## 结果边界

最终银标确认集包含 48 篇新文档和 94 条查询。CARE NDCG@5 为 0.9317,冻结四信号基线为 0.8731,差值 0.0586,95% CI 为 [0.0222,0.0974],`p=0.001`。CARE 对 GTE-raw 的差值仅 0.0025,`p=0.8806`,因此不能声称显著优于专用 cross-encoder。

## 降级约束

- 无 DashScope Key 时不调用 cross-encoder。
- 超时、HTTP 错误、缺字段、重复或缺失索引时返回原 AEF 结果。
- API Key 只从 `.env` 读取,响应和日志不得包含 Key。
- `RERANK_ENABLED=false` 可完全关闭 CARE。

## 后果

在线检索增加一次约 0.2 秒的托管重排调用。系统获得更高的最终银标检索指标,但仍需要人工多级 qrels 和授权语料验证外部有效性。
