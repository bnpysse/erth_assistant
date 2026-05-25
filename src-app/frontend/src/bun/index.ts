// 修改后的 src-app/frontend/src/bun/index.ts
import Electrobun from "electrobun";

console.log("🚀 [ElectroBun] 前端控制台启动，后端已交由人工接管...");

const win = new Electrobun.BrowserWindow({
    title: "ERTH Assistant",
    frame: {
        width: 900,
        height: 700
    },
    url: "views://main/index.html" 
});

// 移除 spawn Robyn 的逻辑，避免它在打包环境中报错
