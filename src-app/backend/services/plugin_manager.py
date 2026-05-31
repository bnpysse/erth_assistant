# [ANCHOR: CH-15]
import os
import importlib.util
import sys
import traceback
from typing import Dict, Any

# 安全常量：限定插件加载的绝对根路径，防范目录穿越 (Directory Traversal)
if getattr(sys, 'frozen', False):
    # 生产封存态：指向物理用户的边缘存储目录
    PLUGIN_DIR = os.path.expanduser("~/.erth_assistant/plugins")
else:
    # 开发态：指向源码树内的沙箱
    PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugins"))

# 插件注册表：持久化存储当前挂载的热插拔插件
_plugin_registry: Dict[str, Any] = {}

class APIContext:
    """提供给插件受限执行的沙箱上下文对象"""
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.log_stream = []

    def log(self, message: str):
        print(f"[Plugin:{self.plugin_name}] {message}")
        self.log_stream.append(message)
        
    def get_logs(self):
        return self.log_stream

def _wash_plugin_path(plugin_name: str) -> str:
    """路径安全洗涤：利用 abspath 防爆，死锁越权加载"""
    # 强制限定只能是 .py 结尾
    if not plugin_name.endswith('.py'):
        plugin_name = plugin_name + '.py'
        
    # 防止黑客传入 ../../../etc/passwd 之类的脏数据
    target_path = os.path.abspath(os.path.join(PLUGIN_DIR, plugin_name))
    
    # 【权限死锁】：如果计算后的绝对路径不以我们的安全沙箱目录开头，直接物理阻断
    if not target_path.startswith(PLUGIN_DIR):
        raise PermissionError(f"【越权警告】沙箱拦截：试图跳出环境隔离边界！非法路径：{target_path}")
        
    return target_path

def load_plugin(plugin_name: str) -> bool:
    """
    通过 importlib 动态注入并激活第三方模块
    """
    try:
        target_path = _wash_plugin_path(plugin_name)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"插件不存在: {target_path}")
            
        module_name = plugin_name.replace(".py", "")
        
        # 1. 创建模块规范
        spec = importlib.util.spec_from_file_location(module_name, target_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法生成模块规范: {module_name}")
            
        # 2. 从规范中实例化模块
        module = importlib.util.module_from_spec(spec)
        
        # 3. 强制加入 sys.modules 防止重复加载错乱
        sys.modules[module_name] = module
        
        # 4. 执行模块代码 (此时尚未调用内部钩子)
        spec.loader.exec_module(module)
        
        # 5. 沙箱上下文注入与生命周期点火
        if hasattr(module, 'setup'):
            context = APIContext(module_name)
            module.setup(context)
            _plugin_registry[module_name] = {
                "module": module,
                "context": context,
                "status": "active"
            }
            return True
        else:
            raise AttributeError(f"插件 {module_name} 缺失标准的 setup 生命周期钩子！")
            
    except Exception as e:
        print(f"[Plugin Error] 挂载 {plugin_name} 失败: {e}")
        traceback.print_exc()
        return False

def unload_plugin(plugin_name: str) -> bool:
    """安全剥离热插拔插件"""
    module_name = plugin_name.replace(".py", "")
    if module_name in _plugin_registry:
        plugin_data = _plugin_registry[module_name]
        module = plugin_data["module"]
        context = plugin_data["context"]
        
        try:
            # 触发 teardown 生命周期以释放资源
            if hasattr(module, 'teardown'):
                module.teardown(context)
                
            # 从注册表与系统模块表中无情抹除
            del _plugin_registry[module_name]
            if module_name in sys.modules:
                del sys.modules[module_name]
            return True
        except Exception as e:
            print(f"[Plugin Error] 卸载 {module_name} 失败: {e}")
            return False
    return False

def execute_plugin(plugin_name: str, payload: dict = None) -> Any:
    """向存活的插件下发执行指令"""
    module_name = plugin_name.replace(".py", "")
    if module_name in _plugin_registry:
        plugin_data = _plugin_registry[module_name]
        module = plugin_data["module"]
        context = plugin_data["context"]
        
        if hasattr(module, 'execute'):
            try:
                # 记录执行动作
                context.log(">>> [统帅下发执行指令]")
                return module.execute(context, payload or {})
            except Exception as e:
                context.log(f"[执行异常] 物理崩溃：{e}")
                return None
        else:
            context.log("[拒绝执行] 模块尚未装载 execute 运算钩子。")
            return None
    return None

def get_loaded_plugins() -> dict:
    return {name: data["status"] for name, data in _plugin_registry.items()}
    
def get_available_plugins() -> list:
    """物理扫描 plugins/ 下所有合法的 python 文件"""
    if not os.path.exists(PLUGIN_DIR):
        os.makedirs(PLUGIN_DIR)
        
    plugins = []
    for file in os.listdir(PLUGIN_DIR):
        if file.endswith(".py") and not file.startswith("__"):
            plugins.append(file)
    return plugins
