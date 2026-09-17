"use client";

import { Card, CardContent } from "@/components/ui/card";
import { API_BASE } from "@/lib/api";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">设置</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          系统配置与版本信息
        </p>
      </div>

      <div className="space-y-4">
        <Card>
          <CardContent className="space-y-3 py-5">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">项目名称</span>
              <span className="font-medium">小鲸 OrcaAI</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">版本</span>
              <span className="font-mono">v0.4.0</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">定位</span>
              <span>为航运优化的通用知识管理工具</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 py-5">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">后端 API</span>
              <span className="font-mono text-xs">{API_BASE}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">前端框架</span>
              <span>Next.js 16 + React 19 + Tailwind v4</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">组件库</span>
              <span>shadcn/ui</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-5">
            <div className="text-sm text-muted-foreground">
              <p className="mb-2 font-medium text-foreground">核心特性</p>
              <ul className="ml-4 list-disc space-y-1">
                <li>通用内核 + 可替换领域包(maritime ↔ example)</li>
                <li>混合检索:向量 + 关键词 + 时间 + 标签四维加权</li>
                <li>离线降级:零 API Key 也能完整演示</li>
                <li>采集器接口:多平台内容采集基础</li>
                <li>中文 bigram 分词增强关键词检索</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        <div className="text-center text-xs text-muted-foreground">
          Made by @Brendan691 · 2026
        </div>
      </div>
    </div>
  );
}
