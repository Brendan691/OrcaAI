"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  FileText,
  Search,
  MessageCircle,
  FileBarChart,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "系统概览", icon: LayoutDashboard },
  { href: "/documents", label: "文档管理", icon: FileText },
  { href: "/search", label: "知识搜索", icon: Search },
  { href: "/chat", label: "知识问答", icon: MessageCircle },
  { href: "/reports", label: "AI 报告", icon: FileBarChart },
  { href: "/settings", label: "设置", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        await api.health();
        if (alive) setOnline(true);
      } catch {
        if (alive) setOnline(false);
      }
    };
    check();
    const timer = setInterval(check, 10000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <>
      <header className="sticky top-0 z-30 border-b bg-background md:hidden">
        <div className="flex h-12 items-center justify-between px-4">
          <div className="flex min-w-0 items-center gap-2 font-semibold">
            <span className="text-lg">🐳</span>
            <span className="truncate">小鲸 OrcaAI</span>
          </div>
          <span
            title={online ? "后端服务运行中" : "后端未连接"}
            className={cn(
              "h-2.5 w-2.5 shrink-0 rounded-full",
              online === null
                ? "animate-pulse bg-muted-foreground"
                : online
                  ? "bg-green-500"
                  : "bg-red-500"
            )}
          />
        </div>
        <nav className="flex h-11 items-center gap-1 overflow-x-auto px-2">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex h-8 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </Link>
            );
          })}
        </nav>
      </header>

      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r bg-sidebar px-4 py-6 md:flex">
      {/* 品牌 */}
      <div className="px-2">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <span className="text-2xl">🐳</span>
          <span>小鲸 OrcaAI</span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          为航运优化的知识管理工具
        </p>
      </div>

      {/* 导航 */}
      <nav className="mt-8 flex flex-1 flex-col gap-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* 状态 */}
      <div className="mt-4 rounded-lg border bg-card px-3 py-2.5">
        <div className="flex items-center gap-2 text-sm">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              online === null
                ? "bg-muted-foreground animate-pulse"
                : online
                  ? "bg-green-500"
                  : "bg-red-500"
            )}
          />
          <span className="text-muted-foreground">
            {online === null
              ? "检测中…"
              : online
                ? "后端服务运行中"
                : "后端未连接"}
          </span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground/70">v0.4.0</p>
      </div>
      </aside>
    </>
  );
}
