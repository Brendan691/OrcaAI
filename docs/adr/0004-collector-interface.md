# 4. 采集器(Collector)抽象接口

- 状态:已接受
- 日期:2026-07-27

## 背景

当前能采集的来源:网页 URL、上传文件、粘贴文本。未来要支持"在小红书/抖音/公众号看到内容,一键识别并结构化入库"(见 ROADMAP)。

若每加一个来源就在路由里堆 `if source == "xxx"`,采集逻辑会散落各处,越加越乱——正是要避免的"一盘散沙"。

## 决策

定义统一的 **Collector 接口**:把"某来源的原始输入"转换成标准的 Document(标题、来源 URL、正文)。

```python
class Collector(Protocol):
    def can_handle(self, source: str) -> bool: ...
    def collect(self, source: str) -> RawDocument: ...
```

- 现有网页抓取、文件解析改造为 `WebCollector`、`FileCollector`,实现同一接口。
- 一个注册表按 `can_handle` 选择合适的采集器;入库管线(切片→向量化→标签→存储)对所有采集器共用,不重复。
- 未来的 `XiaohongshuCollector`、`DouyinCollector`、`WechatArticleCollector` 只需实现接口并注册,入库管线不动。

## 后果

- 好处:加新平台 = 加一个文件 + 注册一行,不碰核心管线。这是"多平台采集"能落地而不推翻架构的前提。
- 好处:每个采集器可独立测试(接口即测试面)。
- 代价:现在就要抽象,即使只有两个采集器。但"两个适配器 = 真实的 seam",投入正当。
- 关联:各平台采集的具体技术难点(抖音需解析、公众号防爬、小红书需登录态)记录在 ROADMAP,不在本 ADR。
