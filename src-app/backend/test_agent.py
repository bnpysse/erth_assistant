import asyncio
import json
from services.action_registry import ActionRegistry, action_handler

# 模拟大模型意图下发
async def main():
    print("\n--- 1. 抓取大模型 Function Calling Schemas ---")
    schemas = ActionRegistry.get_all_schemas()
    print(json.dumps(schemas, indent=2, ensure_ascii=False))
    
    print("\n--- 2. 模拟大模型意图命中，执行物理调用 ---")
    action_name = "get_system_time"
    args = {}
    print(f"⚡ 收到意图指令: {action_name} | 参数: {args}")
    
    result = await ActionRegistry.execute(action_name, args)
    print(f"✅ 执行结果: {result}\n")

if __name__ == "__main__":
    asyncio.run(main())
