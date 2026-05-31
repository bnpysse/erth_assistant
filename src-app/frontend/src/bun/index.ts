// [ANCHOR: CH-03]
// Description: 实现看门狗防线与自愈机制。将后端拉起逻辑封装为可重复执行的 startBackend 函数，通过每3秒的心跳探针 (fetch /ping) 判定健康状态。失联3次则执行 SIGTERM 战术重启并重新进行动态端口协商。
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

// [ANCHOR: CH-04]
// 零信任防线：动态生成一次性、高强度的 Opaque Token
const agentSecretToken = crypto.randomUUID();

let win: any = null; // ⚡ 提前声明，规避异步流匹配成功时由于“暂时性死区 (TDZ)”导致 win 未实例化报错
let backendProcess: any = null;
let portFound = false;
let backendPort = 0;
let timeoutTimer: any = null;
let watchdogInterval: any = null;
let failCount = 0;

// 兼容多版本 Robyn/Uvicorn 的端口匹配正则 (支持 http://127.0.0.1:xxxx 或 listening on: 0.0.0.0:xxxx)
const PORT_CAPTURE_REGEX = /http:\/\/127\.0\.0\.1:(\d+)|listening on: [^:]+:(\d+)/;

// Stderr 中的致命启动错误匹配正则 (如 Python 语法错误、依赖缺失或端口已被死锁占用)
const FATAL_ERRORS_REGEX = /Traceback \(most recent call last\)|ModuleNotFoundError|ImportError|AddrInUse|CRITICAL:|Error:/i;

// 3. 终极防线：精准回收子进程，杜绝孤儿与僵尸进程
const killBackendWithCode = (code = 0, autoRestart = false) => {
  if (timeoutTimer) {
    clearTimeout(timeoutTimer);
  }
  if (backendProcess && !backendProcess.killed) {
    console.log("\n🛑 [ElectroBun] 正在精准回收 Robyn 后端进程...");
    backendProcess.kill("SIGTERM");
  }
  if (!autoRestart) {
    if (watchdogInterval) {
      clearInterval(watchdogInterval);
    }
    process.exit(code);
  }
};

const killBackend = () => killBackendWithCode(0, false);

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
      killBackendWithCode(1, false);
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
          console.log(`[ElectroBun] 零信任 Opaque Token: ${agentSecretToken}`);
          
          // 开启/重置心跳探测看门狗
          startWatchdog();

          // [ANCHOR: CH-04]
          // 物理防线并轨：将最新的通讯端口与 Opaque Token 动态注入前台 Webview 容器，并派发就绪事件
          if (win && win.webview) {
            win.webview.executeJavascript(`
              window.__ENV__ = {
                BACKEND_PORT: ${backendPort},
                TOKEN: "${agentSecretToken}",
                BUN_PORT: ${bunHttpPort || 0}
              };
              window.dispatchEvent(new CustomEvent('backend-ready', { 
                detail: { port: ${backendPort}, token: "${agentSecretToken}", bunPort: ${bunHttpPort || 0} } 
              }));
            `);
          }
        }
      }
    }
  }
};

// 启动看门狗心跳监测
const startWatchdog = () => {
  if (watchdogInterval) {
    clearInterval(watchdogInterval);
  }
  failCount = 0;
  console.log(`📡 [Watchdog] 侦测雷达已开启，正在对端口 :${backendPort} 监听心跳...`);
  
  watchdogInterval = setInterval(async () => {
    if (!portFound || backendPort === 0) return;
    
    try {
      // 心跳探针：向后端 /ping 发起请求，设定 1000 毫秒极短超时阈值
      const res = await fetch(`http://127.0.0.1:${backendPort}/ping`, {
        headers: {
          "Authorization": `Bearer ${agentSecretToken}`
        },
        signal: AbortSignal.timeout(1000)
      });
      
      if (res.ok) {
        const data: any = await res.json();
        if (data.status === "pong") {
          failCount = 0; // 成功恢复通信，清零失败计数器
        } else {
          failCount++;
        }
      } else {
        failCount++;
      }
    } catch (e) {
      failCount++;
    }
    
    if (failCount >= 3) {
      console.log(`\n🚨 [Watchdog] 警告：Robyn 后端边车连续 3 次心跳丢失（或响应超时），判定边车假死！`);
      console.log(`🚨 [Watchdog] 正在触发自愈机制，执行战术重启...`);
      
      // 战术自愈：杀掉当前僵死子进程并重新拉起
      killBackendWithCode(0, true);
      startBackend();
    }
  }, 3000);
};

// [ANCHOR: CH-01]
// [ANCHOR: CH-02]
// 后端拉起函数
const startBackend = () => {
  portFound = false;
  backendPort = 0;
  
  console.log(`🚀 [ElectroBun] 正在静默拉起 Robyn 后端引擎，物理路径: ${backendPath}`);
  
  // [ANCHOR: CH-16: 物理路径提权与封存态侦测 (跨平台支持)]
  const isProd = process.env.NODE_ENV === "production" || process.execPath.includes("MacOS") || process.execPath.includes("Release");
  
  let engineExecutable = "";
  if (process.platform === "win32") {
      engineExecutable = resolve(process.execPath, "../robyn_engine/robyn_engine.exe");
  } else if (process.platform === "darwin") {
      engineExecutable = resolve(process.execPath, "../../MacOS/robyn_engine/robyn_engine");
  } else {
      engineExecutable = resolve(process.execPath, "../robyn_engine/robyn_engine");
  }
  
  const backendCmd = isProd 
      ? [engineExecutable] // 指向被封存的二进制引擎的【内部执行文件】
      : ["uv", "run", "python", "-u", "app.py"]; // 开发态动态路由

  backendProcess = spawn({
    cmd: backendCmd,
    cwd: backendPath,
    env: {
      ...process.env,
      AGENT_SECRET_TOKEN: agentSecretToken,
      PYTHONUNBUFFERED: "1"
    },
    stdout: "pipe",
    stderr: "pipe", 
  });
  
  handleOutput(backendProcess.stdout, "STDOUT");
  handleOutput(backendProcess.stderr, "STDERR");
  
  // 启动 10 秒超时熔断器：若在规定时间内未能成功解析并绑定有效随机端口，强制停机并抛出排错指引
  const LAUNCH_TIMEOUT_MS = 10000;
  if (timeoutTimer) {
    clearTimeout(timeoutTimer);
  }
  timeoutTimer = setTimeout(() => {
    if (!portFound) {
      console.error(`\n❌ [ElectroBun] 熔断器触发：后端引擎未能在 ${LAUNCH_TIMEOUT_MS / 1000} 秒内成功绑定有效端口，启动超时！`);
      console.error(`💡 [排错指引]：`);
      console.error(`   1. 请确认本地已通过 'uv' 安装相关 Python 依赖环境。`);
      console.error(`   2. 请尝试手动在终端执行: cd src-app/backend && uv run python app.py`);
      console.error(`   3. 检查是否有防火墙或安全规则限制了本机的网络端口分配。`);
      killBackendWithCode(1, false);
    }
  }, LAUNCH_TIMEOUT_MS);
};

// 首次拉起后端
startBackend();

// 监听常见系统退出信号，保障生命周期强一致性
process.on("SIGINT", killBackend);
process.on("SIGTERM", killBackend);
process.on("exit", killBackend);

// [ANCHOR: CH-14]
// 4. 挂载 Electrobun 原生视窗 (幽灵化)
win = new Electrobun.BrowserWindow({
    title: "ERTH Assistant",
    transparent: true,
    frame: {
        width: 900,
        height: 700
    },
    mac: {
        styleMask: {
            Borderless: true,
            UtilityWindow: true,
            HUDWindow: true
        }
    },
    url: "views://main/index.html"
});

// [ANCHOR: CH-14]
// 5. 组建超媒体退出桥 (HTTP Bridge) 与全局状态控制
let bunHttpPort = 0;
let isFocused = false;
let lastShowTime = 0;

const hideCommander = () => {
    if (win) {
        // Electrobun 原生方法可能为 hide() 或 setVisibility(false) 
        // 但通常隐藏/显示使用 hide() / show()
        win.hide();
        isFocused = false;
    }
};

const bunServer = Bun.serve({
    port: 0,
    fetch(req) {
        const url = new URL(req.url);
        // CORS 处理 (放行跨域)
        if (req.method === "OPTIONS") {
            return new Response(null, { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "*", "Access-Control-Allow-Headers": "*" } });
        }
        
        if (url.pathname === '/api/app/quit') {
            console.log("\\n🛑 [ElectroBun HTTP Bridge] 收到退出指令，正在平滑退场...");
            killBackendWithCode(0, false);
            return new Response("ok", { headers: { "Access-Control-Allow-Origin": "*" } });
        }
        if (url.pathname === '/api/commander/hide') {
            hideCommander();
            return new Response("ok", { headers: { "Access-Control-Allow-Origin": "*" } });
        }
        return new Response("not found", { status: 404, headers: { "Access-Control-Allow-Origin": "*" } });
    }
});
bunHttpPort = bunServer.port;
console.log(`[ElectroBun] 退出桥建立在端口: ${bunHttpPort}`);

// [ANCHOR: CH-04]
// 监听 Webview 的 DOM 就绪事件，确保在页面重载或滞后加载时，能够成功同步最新的后端端口
win.webview.on("dom-ready", () => {
    if (portFound && backendPort > 0) {
        win.webview.executeJavascript(`
            window.__ENV__ = {
                BACKEND_PORT: ${backendPort},
                TOKEN: "${agentSecretToken}",
                BUN_PORT: ${bunHttpPort}
            };
            window.dispatchEvent(new CustomEvent('backend-ready', { 
                detail: { port: ${backendPort}, token: "${agentSecretToken}", bunPort: ${bunHttpPort} } 
            }));
        `);
    }
});

// [ANCHOR: CH-14]
// 6. 幽灵唤醒机制与热键拦截
try {
    Electrobun.GlobalShortcut.register('Control+Shift+Space', () => {
        if (!win) return;
        if (isFocused) {
            console.log("⚡ [ElectroBun] 幽灵浮窗隐藏！");
            hideCommander();
        } else {
            console.log("⚡ [ElectroBun] 幽灵浮窗唤醒！");
            win.show();
            isFocused = true;
            lastShowTime = Date.now();
        }
    });

    win.on('focus', () => {
        isFocused = true;
    });

    win.on('blur', () => {
        // 为了方便测试和正常使用，暂时屏蔽失焦自动隐藏 (Ghost Window Blur Filter)
        // if (isFocused && (Date.now() - lastShowTime > 300)) {
        //     hideCommander();
        // }
    });
} catch (e) {
    console.error("[ElectroBun] GlobalShortcut 注册失败", e);
}





