# [ANCHOR: CH-12]
# Description: Agent 行为流武装——Python 动态注册装饰器 @action_handler 的硬核实现
# Status: Verified

import inspect
import json
from typing import Callable, Any, Dict, Annotated, get_origin, get_args

class ActionRegistry:
    """
    元编程执纪：
    全局单例的行为注册中心。通过动态加载，将孤立的 Python 函数
    转化为大模型 Function Calling 所需的标准语义图谱。
    """
    _registry: Dict[str, dict] = {}

    @classmethod
    def register(cls, name: str, description: str):
        """
        核心装饰器：@action_handler
        利用 Python 闭包与元编程技术，在模块加载时自动抓取函数签名并沉淀入库。
        """
        def decorator(func: Callable):
            # 获取函数的原子级签名（参数列表、类型标注等）
            sig = inspect.signature(func)
            parameters = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                param_type_str = "string" # 默认推断为 string
                param_desc = f"参数 {param_name}" # 默认回退描述
                actual_type = param.annotation
                
                # 核心杀招：解析 Annotated[类型, "语义描述"]
                if get_origin(actual_type) is Annotated:
                    args = get_args(actual_type)
                    actual_type = args[0]  # 提取真实物理类型
                    if len(args) > 1 and isinstance(args[1], str):
                        param_desc = args[1] # 提取提供给大模型的语义描述
                
                # 基础物理类型扩容映射
                if actual_type == int:
                    param_type_str = "integer"
                elif actual_type == float:
                    param_type_str = "number"
                elif actual_type == bool:
                    param_type_str = "boolean"
                elif actual_type == list or get_origin(actual_type) == list:
                    param_type_str = "array"
                    
                parameters[param_name] = {
                    "type": param_type_str,
                    "description": param_desc
                }
                
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
                    
            # 组装为兼容 OpenAI/Ollama 的结构化 Schema
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": parameters,
                        "required": required
                    }
                }
            }
            
            cls._registry[name] = {
                "func": func,
                "schema": schema
            }
            
            print(f"[Action Handler] 🚀 物理挂载成功: {name} -> {func.__name__}")
            return func
            
        return decorator

    @classmethod
    def get_all_schemas(cls) -> list:
        """输出给大模型的行为意图图谱"""
        return [meta["schema"] for meta in cls._registry.values()]

    @classmethod
    async def execute(cls, action_name: str, arguments: dict) -> Any:
        """语义意图到物理执行的转换管道"""
        if action_name not in cls._registry:
            raise ValueError(f"Action '{action_name}' is not registered in the physical plane.")
            
        func = cls._registry[action_name]["func"]
        
        # 针对异步和同步函数的异构支持
        if inspect.iscoroutinefunction(func):
            result = await func(**arguments)
        else:
            result = func(**arguments)
            
        return result

# 暴露给上层的简洁别名
action_handler = ActionRegistry.register

# ==========================================
# 示例：注册一个基础原子能力
# ==========================================
@action_handler(name="get_system_time", description="获取本机当前的绝对物理时间")
def get_system_time() -> str:
    import datetime
    return datetime.datetime.now().isoformat()
