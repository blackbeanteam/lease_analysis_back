// pages/api/blob/sign.ts  或  app/api/blob/sign/route.ts（需 runtime: 'nodejs'）
// 作用：返回 GCS 直传的 V4 预签名 PUT URL
import type { VercelRequest, VercelResponse } from '@vercel/node';
import { Storage } from '@google-cloud/storage';

// 必备环境变量：
// - GCS_BUCKET         桶名
// - GCS_PROJECT_ID     GCP 项目 ID
// - GCS_SA_KEY_B64     Base64 的 Service Account JSON（整份），内部会解码并修复私钥换行
// 建议：
// - CORS_ALLOW_ORIGIN  允许的前端来源（开发: http://localhost:5173；上线加你的正式域名）
// - SIGN_TTL_S         预签名有效期秒数（默认 60）
// - GCS_DOC_PREFIX  上传前缀/“文件夹”（默认 tmp/，末尾自动补 /）

const BUCKET = process.env.GCS_BUCKET!;
const PROJECT_ID = process.env.GCS_PROJECT_ID!;
const SIGN_TTL_S = parseInt(process.env.SIGN_TTL_S || '60', 10);
const ORIGIN = process.env.CORS_ALLOW_ORIGIN || '*';
const PREFIX = (process.env.GCS_DOC_PREFIX)
  .replace(/^\/+/, '')
  .replace(/\/?$/, '/');

function setCors(res: VercelResponse) {
  res.setHeader('Access-Control-Allow-Origin', ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
}

function readSaFromB64() {
  const b64 = process.env.GCS_SA_KEY_B64;
  if (!b64) return null;
  const json = Buffer.from(b64, 'base64').toString('utf8');
  const obj = JSON.parse(json);
  if (obj.private_key) obj.private_key = String(obj.private_key).replace(/\\n/g, '\n');
  return obj;
}

// YYYYMMDD_HHMMSS（本机时区）
function ymdHms(d = new Date()) {
  const p = (n: number) => String(n).padStart(2, '0');
  return (
    d.getFullYear().toString() +
    p(d.getMonth() + 1) +
    p(d.getDate()) + '_' +
    p(d.getHours()) +
    p(d.getMinutes()) +
    p(d.getSeconds())
  );
}

const storage = new Storage({
  projectId: PROJECT_ID,
  credentials: readSaFromB64() || undefined,
});

export default async function handler(req: VercelRequest, res: VercelResponse) {
  setCors(res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST')   return res.status(405).json({ error: 'Method Not Allowed' });

  try {
    const { name, size, type } = (req.body || {}) as { name?: string; size?: number; type?: string };
    if (!name || typeof size !== 'number' || !type) {
      return res.status(400).json({ error: 'name/size/type required' });
    }
    if (size > 25 * 1024 * 1024) return res.status(413).json({ error: 'file too large' });
    if (!/^application\/pdf$/i.test(type)) return res.status(415).json({ error: 'only pdf allowed' });

    const safeBase = String(name).replace(/[^\w.\-]+/g, '_');
    // 按你的要求：<PREFIX><YYYYMMDD_HHMMSS>_<原文件名>
    const key = `${PREFIX}${ymdHms()}_${safeBase}`;

    const file = storage.bucket(BUCKET).file(key);
    const [uploadUrl] = await file.getSignedUrl({
      version: 'v4',
      action: 'write',
      expires: Date.now() + SIGN_TTL_S * 1000,
      contentType: type,
    });

    setCors(res);
    return res.status(200).json({
      uploadUrl,
      key,
      expireAt: Date.now() + SIGN_TTL_S * 1000,
      headers: { 'Content-Type': type },
    });
  } catch (err: any) {
    console.error('[sign] error:', err);
    setCors(res);
    return res.status(500).json({ error: err?.message || 'sign failed' });
  }
}
