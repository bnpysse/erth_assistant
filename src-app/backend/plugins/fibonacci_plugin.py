# [ANCHOR: CH-15]
"""
高维算法测试插件：斐波那契矩阵运算
验证系统级热插拔、执行拦截与运算隔离。
"""
import time

def setup(api_context):
    api_context.log("Fibonacci 算法引擎已挂载！")
    api_context.log("待命状态：等待传入高维运算指令...")

def execute(api_context, payload):
    api_context.log("接收到执行信号，启动斐波那契运算矩阵。")
    start_time = time.time()
    
    # 执行一个有实质体感的计算（第 35 位斐波那契数，纯 Python 递归约需一秒多）
    def fib(n):
        if n <= 1:
            return n
        return fib(n-1) + fib(n-2)
        
    target_n = payload.get("n", 35)
    result = fib(target_n)
    
    cost_time = (time.time() - start_time) * 1000
    api_context.log(f"运算完成: Fibonacci({target_n}) = {result}")
    api_context.log(f"耗时: {cost_time:.2f} ms")
    return result

def teardown(api_context):
    api_context.log("算法引擎剥离，释放计算资源。")
