# ERTH Assistant 🪐

[English] | [简体中文](./README_zh.md)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-v1.0--Release-green.svg)
[![Leanpub Book](https://img.shields.io/badge/Leanpub-Buy%20the%20Book-orange?style=for-the-badge)](https://leanpub.com/erth_assistant)

**ERTH Assistant** is a cross-platform desktop application with a "geek soul." It serves as the official companion repository for the book [**"ERTH Assistant: Local-First + AI Sidecar Desktop Architecture"**](https://leanpub.com/erth_assistant).

It showcases how to build an ultra-fast, secure, next-generation Personal Information Management (PIM) and AI agent hub by utilizing a **heterogeneous dual-core architecture** and **zero-JS frontend constraints**.

---

## 📖 The Companion Book

The architectural evolution, troubleshooting logs, and core design philosophies of this project are documented page-for-page in our official book:

👉 **[Read the Book on Leanpub (Includes a Free 5-Chapter Preview Edition)](https://leanpub.com/erth-assistant)**

Every branch and tag in this repository corresponds directly to a specific chapter's tactical milestone in the book.

---

## ✨ Core Highlights

- ⚡️ **Heterogeneous Dual-Core**: Frontend rendering is driven by the ultra-fast [ElectroBun](https://electrobun.dev/) shell (native OS WebKit bindings), while high-dimensional business logic is powered by a Python [Robyn](https://robyn.tech/) sidecar backend, eliminating heavy Electron dependencies.
- 🛡️ **Zero-JS Frontend Constitution**: Leverages **HTMX** for local hypermedia DOM swaps. The UI is built using clean native HTML + Tailwind CSS, completely bypassing complex client-side state machines.
- 🧠 **Local LLM (Edge AI)**: Integrates with an offline Ollama engine to keep all AI computation local, achieving absolute privacy and offline capability.
- 💾 **Local-First Edge Database**: Powered by **Turso (libSQL)** with SQLModel type safety, ensuring instant local reads/writes (0.1ms latency) with background cloud-edge synchronization.
- 🪄 **Ghost Float Window**: Interfaces directly with native macOS Cocoa frameworks to implement global shortcut wakeups and a sleek, translucent glassmorphic floating NSPanel.
- 🧩 **Dynamic Hot-Swapping Plugins**: Supports runtime mounting of Python plugins inside a secure execution sandbox without recompilation or application restarts.
- 📦 **Cross-Platform Distribution**: Configured with automated GitHub Actions for cross-platform compilation (macOS / Windows / Linux) into single-binary, double-click-to-run `.app` and `.exe` bundles of just 128MB.

---

## 🚀 Quick Start

If you wish to run the app immediately without setting up a development environment:
1. Go to the [Releases Page](../../releases).
2. Download the standalone bundle package matching your operating system.
3. Extract and double-click to run!

---

## 🛠️ Development Guide

This repository is designed as a template for studying modern lightweight desktop architectures.

### Prerequisites
1. Install [Bun](https://bun.sh/) runtime (`v1.1+` recommended).
2. Install [uv](https://github.com/astral-sh/uv) (fast Python package manager).
3. Ensure Python 3.11+ is installed locally.

### Local Ignition
```bash
# 1. Clone the repository
git clone https://github.com/bnpysse/erth_assistant.git
cd erth_assistant

# 2. Start the application (development mode)
cd src-app/frontend
bun install
bun run dev

# Note: ElectroBun's dev mode automatically spawns the Robyn Python backend sidecar.
# No manual python startup is required.
```

### Standalone Compilation
We provide automated build scripts in the repository:
- **macOS / Linux**: Go to `src-app/backend` and run `bash build_backend.sh`
- **Windows**: Go to `src-app/backend` and run `.\build_backend.ps1`

Then go to `src-app/frontend` and run `bunx electrobun build` to compile the final standalone desktop application.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) - you are free to use, modify, and distribute it.
