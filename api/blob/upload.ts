// /api/blob/upload.ts
export const runtime = 'nodejs';

import type { VercelRequest, VercelResponse } from '@vercel/node';
import { makeGcsClient, bucketName } from '../../lib/gcs.js'; // 注意 .js 后缀（ESM 运行时）

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    if (req.method !== 'POST') return res.status(405).end('Method Not Allowed');

    // 文件名：原名 + 时间戳；目录：test/
    const rawName = ((req.query?.name as string) || 'Lease.pdf').trim();
    const dot = rawName.lastIndexOf('.');
    const base = dot >= 0 ? rawName.slice(0, dot) : rawName;
    const ext  = dot >= 0 ? rawName.slice(dot) : '';
    const ts   = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14); // 20250922192740
    const filename = `${base}-${ts}${ext}`;
    const objectPath = `test/${filename}`;
    const contentType = String(req.headers['content-type'] || 'application/octet-stream');

    // 读取 body
    const chunks: Buffer[] = [];
    await new Promise<void>((resolve, reject) => {
      req.on('data', (c) => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
      req.on('end', resolve);
      req.on('error', reject);
    });
    const buf = Buffer.concat(chunks);
    if (!buf.length) {
      console.warn('[gcs:upload][warn] empty body');
      return res.status(400).json({ error: 'empty body' });
    }

    // 上传到 GCS（默认私有）
    const storage = makeGcsClient();
    const bucket = storage.bucket(bucketName());
    const file = bucket.file(objectPath);

    await file.save(buf, {
      resumable: false,
      contentType,
      metadata: { contentType },
    });

    console.groupCollapsed('[gcs:upload][ok]');
    console.log('bucket:', bucketName());
    console.log('objectPath:', objectPath);
    console.log('contentType:', contentType);
    console.log('size(bytes):', buf.length);
    console.groupEnd();

    return res.status(200).json({ pathname: objectPath, size: buf.length });
  } catch (e: any) {
    console.error('[gcs:upload][fatal]', e?.message || e);
    return res.status(500).json({ error: String(e?.message || e) });
  }
}
