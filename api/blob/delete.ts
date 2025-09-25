// /api/blob/delete.ts
export const runtime = 'nodejs';

import type { VercelRequest, VercelResponse } from '@vercel/node';
import { makeGcsClient, bucketName } from '../../lib/gcs.js';

type DeleteReq =
  | { pathname: string }                         // 单个
  | { paths: string[] }                          // 批量
  | { pathname?: string; paths?: string[] };     // 容错

function boolEnv(name: string, def = false) {
  const v = (process.env[name] || '').toLowerCase().trim();
  if (['1', 'true', 'yes', 'y', 'on'].includes(v)) return true;
  if (['0', 'false', 'no', 'n', 'off'].includes(v)) return false;
  return def;
}

function normalizePath(p: string) {
  return p.trim().replace(/^\/+/, ''); // 去掉开头的斜杠
}

function allowedByPrefix(p: string, prefix?: string) {
  if (!prefix) return true; // 未设置就不限制
  return p.startsWith(prefix);
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    if (req.method !== 'POST') {
      return res.status(405).json({ error: 'Method Not Allowed' });
    }

    const enabled = boolEnv('GCS_DELETE_ENABLED', false);
    const restrictPrefix = (process.env.GCS_DOC_PREFIX || '').replace(/^\/+/, '');

    // 支持 JSON body 或表单；优先 JSON
    const body: DeleteReq = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    let targets: string[] = [];
    if (Array.isArray((body as any).paths)) targets = (body as any).paths as string[];
    if (!targets.length && typeof (body as any).pathname === 'string') targets = [(body as any).pathname as string];

    targets = targets.map(normalizePath).filter(Boolean);

    if (!targets.length) {
      return res.status(400).json({ error: 'missing pathname or paths' });
    }

    // 前置校验：前缀限制
    const denied = restrictPrefix ? targets.filter(p => !allowedByPrefix(p, restrictPrefix)) : [];
    if (denied.length) {
      return res.status(400).json({
        error: 'some paths are not allowed by GCS_DELETE_PREFIX',
        prefix: restrictPrefix,
        denied,
      });
    }

    // 删除未启用：直接返回“跳过”，不触发任何操作
    if (!enabled) {
      console.warn('[gcs:delete][disabled]', { count: targets.length, example: targets[0] });
      return res.status(202).json({
        ok: false,
        deleted: [],
        skipped: targets,
        message: 'delete is disabled by GCS_DELETE_ENABLED=false',
      });
    }

    // 真正执行删除
    const storage = makeGcsClient();
    const bkt = storage.bucket(bucketName());

    const results = await Promise.all(
      targets.map(async (p) => {
        try {
          await bkt.file(p).delete({ ignoreNotFound: true });
          return { path: p, ok: true };
        } catch (e: any) {
          return { path: p, ok: false, error: String(e?.message || e) };
        }
      })
    );

    const ok = results.filter(r => r.ok).map(r => r.path);
    const failed = results.filter(r => !r.ok);

    console.groupCollapsed('[gcs:delete][result]');
    console.log('enabled:', enabled);
    console.log('bucket:', bucketName());
    if (restrictPrefix) console.log('prefix:', restrictPrefix);
    console.log('deleted:', ok.length);
    if (failed.length) console.log('failed:', failed);
    console.groupEnd();

    return res.status(200).json({
      ok: failed.length === 0,
      deleted: ok,
      failed,
    });
  } catch (e: any) {
    console.error('[gcs:delete][fatal]', e?.message || e);
    return res.status(500).json({ error: String(e?.message || e) });
  }
}

