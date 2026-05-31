#!/bin/bash
# [ANCHOR: CH-16]
# Robyn Backend 自动化编译封存脚本 (PyInstaller)

echo "🚀 开始进行后端引擎交叉编译与物理固化..."

# 确保安装了 pyinstaller
uv pip install pyinstaller

# 清理历史产物
rm -rf build dist

# 利用 PyInstaller 进行 Onedir 封存打包
# 采用 onedir 而非 onefile 是为了追求毫秒级的冷启动速度，避免解压临时文件的开销
uv run pyinstaller --noconfirm \
    --onedir \
    --name robyn_engine \
    --hidden-import="sqlmodel" \
    --hidden-import="sqlalchemy_libsql" \
    --collect-all robyn \
    app.py

echo "✅ 后端引擎封存完毕！"
echo "👉 请在编译前端 ElectroBun 时，通过钩子或手动将 dist/robyn_engine 目录拷贝至 .app/Contents/MacOS/ 目录下。"
