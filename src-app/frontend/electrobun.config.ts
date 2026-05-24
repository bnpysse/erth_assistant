export default {
  app: {
    name: "ERTH Assistant",
    identifier: "dev.woodman.erth",
    version: "0.1.0"
  },
  build: {
    bun: {
      entrypoint: "src/bun/index.ts"
    }
  },
  views: {
    main: {
      entrypoint: "src/index.html"
    }
  }
};
