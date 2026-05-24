import { BrowserWindow } from "electrobun";

console.log("[ElectroBun] 前端桌面主控引擎启动中...");

const win = new BrowserWindow({
  title: "ERTH Assistant",
  width: 900,
  height: 700,
  html: "views://main/index.html"
});

console.log("[ElectroBun] 原生窗口已成功挂载。");
