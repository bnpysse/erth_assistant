# ERTH Assistant 🪐

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-v1.0--Release-green.svg)
![Architecture](https://img.shields.io/badge/architecture-Dual--Core%20%7C%20Edge-orange.svg)

ERTH Assistant 是一款拥有“极客灵魂”的跨平台桌面应用。它脱胎于《全栈极客开发图鉴》（*The Full-Stack Geek's Guide*），展示了如何通过**异构双核架构**与**前端零 JS 约束**，打造一个极速、安全的下一代个人信息管理（PIM）与 AI 代理中枢。

## ✨ 核心亮点 (Core Features)

- ⚡️ **异构双核架构**：前端基于 [ElectroBun](https://electrobun.dev/) 极速渲染，后端基于 Python [Robyn](https://robyn.tech/) 强力驱动，彻底抛弃传统重型 Electron 框架。
- 🛡️ **前端零 JS 宪法**：完全采用 **HTMX** 进行局部超媒体 DOM 交互，界面由原生 HTML + Tailwind CSS 锻造，杜绝前端状态机混乱。
- 🧠 **本地大语言模型 (LLM)**：通过离线挂载 Ollama 模型，将 AI 算力留在本地，实现断网可用与极致隐私保护。
- 💾 **分布式边缘数据库**：采用 **Turso (libSQL)** 作为底层数据库，搭配 SQLModel 强类型约束，构建极速边缘数据流。
- 🪄 **幽灵面板交互**：注入 macOS 原生 Cocoa 框架，实现系统级全局快捷键唤醒与沉浸式毛玻璃悬浮视窗。
- 🧩 **动态热插拔插件**：系统级安全沙箱隔离，支持 Python 插件的动态挂载，业务扩展无需重新编译。
- 📦 **全平台降维分发**：利用 GitHub Actions 实现一键跨平台交叉编译（Windows / macOS / Linux），生成开箱即用的 `.app`、`.exe` 与二进制包。

## 🚀 极速体验 (Quick Start)

如果你不想配置开发环境，可以直接前往 [Releases 页面](../../releases) 下载对应操作系统的免安装独立包，双击即可运行。

## 🛠️ 开发指南 (Development)

本项目适合作为深入学习现代跨端开发架构的超级模板。

### 环境准备
1. 安装 [Bun](https://bun.sh/) 运行时 (推荐 `v1.1+`)
2. 安装 [UV](https://github.com/astral-sh/uv) (极速 Python 包管理器)
3. 确保拥有 Python 3.11+ 环境

### 本地启动
```bash
# 1. 克隆代码库
git clone https://github.com/你的用户名/erth_assistant.git
cd erth_assistant

# 2. 启动前端与主进程
cd src-app/frontend
bun install
bun run dev

# 注意：ElectroBun 的开发模式会自动拉起后端的 Python 进程，无需手动启动后端。
```

### 跨平台打包封存
我们在仓库内为您准备了跨平台的自动封存脚本：
- **Mac/Linux**: 进入 `src-app/backend`，运行 `bash build_backend.sh`
- **Windows**: 进入 `src-app/backend`，运行 `.\build_backend.ps1`

随后进入 `src-app/frontend` 执行 `bunx electrobun build` 即可完成最终的桌面端组装。

## 📖 关于《全栈极客开发图鉴》

本项目的架构推演、踩坑记录与设计哲学，全部完整记录于《全栈极客开发图鉴》一书中。代码库中的每个分支与 Tag，都对应着书稿中步步为营的战术演进。

## 📄 许可证 (License)

本项目基于 [MIT License](LICENSE) 开源，您可以自由地使用、修改和分发。
