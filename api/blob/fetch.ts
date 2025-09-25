// /api/blob/fetch.ts  —— 从 GCS 下载并回传字节（私有）
export const runtime = 'nodejs';

import type { VercelRequest, VercelResponse } from '@vercel/node';
import { makeGcsClient, bucketName } from '../../lib/gcs.js'; // 注意 .js 后缀

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    const rawPn =
      (body.pathname as string) ||
      (req.method === 'GET' ? (req.query?.pathname as string) : '');
    if (!rawPn) return res.status(400).json({ error: 'missing pathname' });

    const objectPath = rawPn.trim().replace(/^\/+/, '');
    console.log('[gcs:fetch][diag]', { objectPath });

    const storage = makeGcsClient();
    const file = storage.bucket(bucketName()).file(objectPath);

    const [exists] = await file.exists();
    if (!exists) return res.status(404).json({ error: 'not found' });

    const [meta] = await file.getMetadata().catch(
      () => [{ contentType: 'application/octet-stream' } as any]
    );
    const [buf] = await file.download();

    res.setHeader('Content-Type', meta?.contentType || 'application/octet-stream');
    return res.status(200).send(buf);
  } catch (e: any) {
    console.error('[gcs:fetch][fatal]', e?.message || e);
    return res.status(500).json({ error: String(e?.message || e) });
  }
}

