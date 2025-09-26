import { app } from "./index";

// App Runner / 容器会把端口传到 PORT（App Runner 默认会探测 EXPOSE 的端口）
// 我们固定 8000，也兼容 PORT 变量
const PORT = Number(process.env.PORT || 8000);

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Blob API adapter listening on http://0.0.0.0:${PORT}`);
});

