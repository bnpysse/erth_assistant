// [ANCHOR: CH-02]
// Description: Bun.spawn 动态接管后端 Robyn (Port 0) 进程，监听 stdout 日志流提取分配端口，配置 10s 超时熔断器与 stderr 致命异常侦测，完成双核并轨与生命周期闭环。
// Status: Verified

import Electrobun from "electrobun";
import { spawn } from "bun";
import { resolve } from "path";
import * as fs from "fs";

// 自适应查找 Robyn 后端物理路径，兼容本地开发与打包环境
const findBackendPath = () => {
    const paths = [
        resolve(__dirname, "../../../backend"),               // 本地直接运行开发环境
        resolve(__dirname, "../../../../../../backend"),       // electrobun dev 打包应用 Resources 环境
        resolve(process.cwd(), "../../../../../../backend"),   // 从 MacOS 目录回溯
        "/Users/woodman/dev/erth_assistant_reborn/src-app/backend" // 兜底绝对路径
    ];
    for (const p of paths) {
        if (fs.existsSync(resolve(p, "app.py"))) {
            return p;
        }
    }
    return "/Users/woodman/dev/erth_assistant_reborn/src-app/backend";
};

const backendPath = findBackendPath();
console.log(`🚀 [ElectroBun] 正在静默拉起 Robyn 后端引擎，物理路径: ${backendPath}`);

// 1. 进程级接管：启动子进程并截获 stdout 和 stderr
const backendProcess = spawn({
  cmd: ["uv", "run", "python", "app.py"],
  cwd: backendPath,
  stdout: "pipe",
  stderr: "pipe", 
});

let portFound = false;
let backendPort = 0;
let timeoutTimer: any = null;

// 兼容多版本 Robyn/Uvicorn 的端口匹配正则 (支持 http://127.0.0.1:xxxx 或 listening on: 0.0.0.0:xxxx)
const PORT_CAPTURE_REGEX = /http:\/\/127\.0\.0\.1:(\d+)|listening on: [^:]+:(\d+)/;

// Stderr 中的致命启动错误匹配正则 (如 Python 语法错误、依赖缺失或端口已被死锁占用)
const FATAL_ERRORS_REGEX = /Traceback \(most recent call last\)|ModuleNotFoundError|ImportError|AddrInUse|CRITICAL:|Error:/i;

// 3. 终极防线：精准回收子进程，杜绝孤儿与僵尸进程
const killBackendWithCode = (code = 0) => {
  if (timeoutTimer) {
    clearTimeout(timeoutTimer);
  }
  if (backendProcess && !backendProcess.killed) {
    console.log("\n🛑 [ElectroBun] 正在精准回收 Robyn 后端进程...");
    backendProcess.kill("SIGTERM");
  }
  process.exit(code);
};

const killBackend = () => killBackendWithCode(0);

// 2. 监听流数据，提取关键通讯参数
const handleOutput = async (stream: ReadableStream, label: string) => {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const text = decoder.decode(value);
    // 实时打印边车日志，供开发者与看门狗调试
    process.stdout.write(`[Robyn ${label}] ${text}`);
    
    // 致命错误熔断检测：如果 stderr 输出中包含致命的启动异常，立即紧急停机
    if (label === "STDERR" && FATAL_ERRORS_REGEX.test(text)) {
      console.error(`\n❌ [ElectroBun] 熔断器触发：侦测到后端致命启动错误，立即紧急停机！`);
      killBackendWithCode(1);
    }
    
    if (!portFound) {
      const match = text.match(PORT_CAPTURE_REGEX);
      if (match) {
        // match[1] 对应第一个括号捕获，match[2] 对应第二个括号捕获
        const rawPort = match[1] || match[2];
        const parsedPort = parseInt(rawPort, 10);
        // 排除前置占位端口 0，只捕获操作系统实际分配的有效高位端口
        if (parsedPort > 0) {
          backendPort = parsedPort;
          portFound = true;
          if (timeoutTimer) {
            clearTimeout(timeoutTimer); // 成功捕获有效端口，关闭启动超时定时器
          }
          console.log(`\n⚡ [ElectroBun] 守护进程已挂载，后端真实通信端口: ${backendPort}`);
          console.log(`[ElectroBun] 可通过 http://127.0.0.1:${backendPort} 访问`);
        }
      }
    }
  }
};

handleOutput(backendProcess.stdout, "STDOUT");
handleOutput(backendProcess.stderr, "STDERR");

// 启动 10 秒超时熔断器：若在规定时间内未能成功解析并绑定有效随机端口，强制停机并抛出排错指引
const LAUNCH_TIMEOUT_MS = 10000;
timeoutTimer = setTimeout(() => {
  if (!portFound) {
    console.error(`\n❌ [ElectroBun] 熔断器触发：后端引擎未能在 ${LAUNCH_TIMEOUT_MS / 1000} 秒内成功绑定有效端口，启动超时！`);
    console.error(`💡 [排错指引]：`);
    console.error(`   1. 请确认本地已通过 'uv' 安装相关 Python 依赖环境。`);
    console.error(`   2. 请尝试手动在终端执行: cd src-app/backend && uv run python app.py`);
    console.error(`   3. 检查是否有防火墙或安全规则限制了本机的网络端口分配。`);
    killBackendWithCode(1);
  }
}, LAUNCH_TIMEOUT_MS);

// 监听常见系统退出信号，保障生命周期强一致性
process.on("SIGINT", killBackend);
process.on("SIGTERM", killBackend);
process.on("exit", killBackend);

// 4. 挂载 Electrobun 原生视窗
const win = new Electrobun.BrowserWindow({
    title: "ERTH Assistant",
    frame: {
        width: 900,
        height: 700
    },
    url: "views://main/index.html" 
});

