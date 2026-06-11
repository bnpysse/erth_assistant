# ERTH Assistant 🪐

[English](./README.md) | [简体中文]

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-v1.0--Release-green.svg)
[![Leanpub 电子书](https://img.shields.io/badge/Leanpub-%E8%B4%AD%E4%B9%B0%E7%94%B5%E5%AD%90%E4%B9%A6-orange?style=for-the-badge)](https://leanpub.com/erth_assistant)

**ERTH Assistant** 是一款拥有“极客灵魂”的跨平台桌面应用。它脱胎于《全栈极客开发图鉴》（*The Full-Stack Geek's Guide*），是正式出版书籍 [**"ERTH Assistant: Local-First + AI Sidecar Desktop Architecture"**](https://leanpub.com/erth_assistant) 的官方配套开源代码库。

本项目展示了如何通过**异构双核架构**与**前端零 JS 约束**，打造一个极速、安全的下一代个人信息管理（PIM）与 AI 代理中枢。

---

## 📖 配套著作

本项目的完整架构推演、踩坑记录与设计哲学，均详细记录于我们的官方著作中：

👉 **[在 Leanpub 上阅读本书（包含前五章免费试读版）](https://leanpub.com/erth_assistant)**

代码库中的每个分支与 Tag，都对应着书稿中步步为营的战术演进里程碑。

---

## ✨ 核心亮点

- ⚡️ **异构双核架构**：前端基于 [ElectroBun](https://electrobun.dev/) 极速渲染（基于操作系统原生 WebKit 绑定），后端基于 Python [Robyn](https://robyn.tech/) 强力驱动（基于 Rust 核心的异步引擎），彻底抛弃传统重型 Electron 框架。
- 🛡️ **前端零 JS 宪法**：完全采用 **HTMX** 进行局部超媒体 DOM 交互，界面由原生 HTML + Tailwind CSS 锻造，杜绝前端状态机混乱。
- 🧠 **本地大语言模型 (Edge AI)**：通过离线挂载 Ollama 模型，将 AI 算力留在本地，实现断网可用与极致隐私保护。
- 💾 **本地优先边缘数据库**：采用 **Turso (libSQL)** 作为底层数据库，搭配 SQLModel 强类型约束，构建极速边缘数据流（本地物理读写延迟 0.1ms，后台自动进行云边同步）。
- 🪄 **幽灵面板交互**：注入 macOS 原生 Cocoa 框架，实现系统级全局快捷键唤醒与沉浸式毛玻璃悬浮视窗（NSPanel）。
- 🧩 **动态热插拔插件**：系统级安全沙箱隔离，支持 Python 插件的动态挂载，业务扩展无需重新编译或重启核心进程。
- 📦 **全平台降维分发**：利用 GitHub Actions 实现一键跨平台交叉编译（macOS / Windows / Linux），生成体积仅 128MB、双击即用的 `.app` 与 `.exe` 独立包。

---

## 🚀 极速体验

如果你不想配置开发环境，可以直接前往 [Releases 页面](../../releases) 下载对应操作系统的免安装独立包，双击即可运行。

---

## 🛠️ 开发指南

本项目适合作为深入学习现代跨端开发架构的超级模板。

### 环境准备
1. 安装 [Bun](https://bun.sh/) 运行时 (推荐 `v1.1+`)
2. 安装 [uv](https://github.com/astral-sh/uv) (极速 Python 包管理器)
3. 确保拥有 Python 3.11+ 环境

### 本地启动
```bash
# 1. 克隆代码库
git clone https://github.com/bnpysse/erth_assistant.git
cd erth_assistant

# 2. 启动前端与主进程 (开发模式)
cd src-app/frontend
bun install
bun run dev

# 注意：ElectroBun 的开发模式会自动拉起后端的 Python 边车进程，无需手动启动后端。
```

### 跨平台打包封存
我们在仓库内为您准备了跨平台的自动封存脚本：
- **Mac/Linux**: 进入 `src-app/backend`，运行 `bash build_backend.sh`
- **Windows**: 进入 `src-app/backend`，运行 `.\build_backend.ps1`

随后进入 `src-app/frontend` 执行 `bunx electrobun build` 即可完成最终的桌面端组装。

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源，您可以自由地使用、修改和分发。
