import express from "express";
import cors from "cors";

// 你的三个 Vercel 风格的处理器（默认导出）
import fetchHandler from "../api/blob/fetch";
import signHandler from "../api/blob/sign";
import deleteHandler from "../api/blob/delete";

// 建一个 app（单进程 http 服务）
export const app = express();

// 一些常见中间件
app.use(cors()); // 如需更严格的 CORS，可改成 cors({ origin: /你的前端域名/ })
app.use(express.json({ limit: "10mb" })); // 让 req.body 可用
app.use(express.urlencoded({ extended: true }));

// 健康检查：App Runner 配置 HTTP /health
app.get("/health", (_req, res) => {
  res.status(200).send("OK");
});

// 适配层：把 Express 的 req/res 直接交给原有 Vercel 处理器
app.get("/api/blob/fetch", (req, res) => fetchHandler(req as any, res as any));
app.post("/api/blob/sign", (req, res) => signHandler(req as any, res as any));
app.delete("/api/blob/delete", (req, res) => deleteHandler(req as any, res as any));

// 你也可以继续增加其他路由映射…

