# [ANCHOR: CH-15]
"""
极简测试插件：Hello Plugin
验证系统级热插拔与沙箱隔离防御。
"""

def setup(api_context):
    api_context.log("系统级挂载成功！")
    api_context.log("Hello Plugin 准备就绪，随时响应统帅调用。")
    # 可以在此执行初始化逻辑（如挂载中间件或启动子线程）

def teardown(api_context):
    api_context.log("正在剥离，释放占用内存...")
    # 可以在此执行资源回收逻辑
