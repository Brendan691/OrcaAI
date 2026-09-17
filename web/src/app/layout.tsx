import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: "小鲸 OrcaAI — 海事知识管理",
  description: "为航运知识管理优化的通用知识管理工具",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full bg-background text-foreground">
        <div className="flex min-h-screen flex-col md:flex-row">
          <Sidebar />
          <main className="min-w-0 flex-1 overflow-x-hidden">
            <div className="mx-auto max-w-5xl px-4 py-5 sm:px-6 md:px-10 md:py-8">
              {children}
            </div>
          </main>
        </div>
        <Toaster position="top-center" richColors />
      </body>
    </html>
  );
}
