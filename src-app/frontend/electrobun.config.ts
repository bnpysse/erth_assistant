export default {
  app: {
    name: "ERTH Assistant",
    identifier: "dev.woodman.erth.v1",
    version: "0.1.0"
  },
  build: {
    bun: {
      // ⚖️ 必须是相对路径字符串！不准用 path.join！
      entrypoint: "src/bun/index.ts" 
    },
    copy: {
      // ⚖️ 必须是相对路径字符串！不准用 path.join！
      "src/index.html": "views/main/index.html"
    }
  }
};
