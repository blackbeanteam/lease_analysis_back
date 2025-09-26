# ========== build stage ==========
FROM node:20-alpine AS builder
WORKDIR /app

# 仅复制 node-api 构建相关清单
COPY node-api/package.json node-api/tsconfig.json ./
RUN npm ci

# 复制源码：node-api/src + api 源（编译时要用到）
COPY node-api/src ./src
COPY api ./api

# 编译到 dist/
RUN npm run build

# ========== runtime stage ==========
FROM node:20-alpine
WORKDIR /app

# 仅装运行期依赖
COPY node-api/package.json ./
RUN npm ci --omit=dev

# 放入编译好的 dist
COPY --from=builder /app/dist ./dist

# 端口 8000；App Runner 健康检查用 /health
ENV NODE_ENV=production
ENV PORT=8000
EXPOSE 8000

CMD ["npm", "start"]
