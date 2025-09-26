import express from 'express'
import cors from 'cors'

// 直接引入你现有的 handler 模块（保持原路径）
import * as fetchMod from '../../api/blob/fetch'
import * as signMod from '../../api/blob/sign'
import * as delMod from '../../api/blob/delete'

const app = express()

// 常见中间件（按需）
app.use(express.json({ limit: '10mb' }))
app.use(express.urlencoded({ extended: true }))

// CORS（按需）——如果浏览器会直接调用这些接口
const allowList = (process.env.CORS_ALLOW_ORIGIN || '*')
  .split(',')
  .map(s => s.trim())
app.use(
  cors({
    origin: (origin, cb) => {
      if (!origin || allowList.includes('*') || allowList.includes(origin)) return cb(null, true)
      cb(new Error('Not allowed by CORS'))
    },
    credentials: true,
  })
)

// 健康检查
app.get('/health', (_, res) => res.status(200).send('ok'))

// —— 把你的 handler“挂”到路由 ——
// 兼容两种导出风格：
// (1) 默认导出：export default (req,res) => {...}
// (2) 按方法导出：export const GET/POST/DELETE = (req,res) => {...}

function mount(path: string, mod: any) {
  if (typeof mod?.default === 'function') {
    app.all(path, mod.default) // 直接用默认导出
  } else {
    if (typeof mod.GET === 'function') app.get(path, mod.GET)
    if (typeof mod.POST === 'function') app.post(path, mod.POST)
    if (typeof mod.DELETE === 'function') app.delete(path, mod.DELETE)
    if (typeof mod.PUT === 'function') app.put(path, mod.PUT)
    if (typeof mod.PATCH === 'function') app.patch(path, mod.PATCH)
    if (typeof mod.OPTIONS === 'function') app.options(path, mod.OPTIONS)
  }
}

mount('/api/blob/fetch',  fetchMod)
mount('/api/blob/sign',   signMod)
mount('/api/blob/delete', delMod)

export default app
