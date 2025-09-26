import { Storage } from '@google-cloud/storage';

let _storage: Storage | null = null;
let _bucketName: string | null = null;

export function makeGcsClient(): Storage {
  if (_storage) return _storage;

  const b64 = process.env.GCS_SA_KEY_B64;
  const projectId = process.env.GCS_PROJECT_ID;
  const bucket = process.env.GCS_BUCKET;

  if (!b64) throw new Error('Missing GCS_SA_KEY_B64');
  if (!projectId) throw new Error('Missing GCS_PROJECT_ID');
  if (!bucket) throw new Error('Missing GCS_BUCKET');

  const creds = JSON.parse(Buffer.from(b64, 'base64').toString('utf8'));

  _storage = new Storage({
    projectId,
    credentials: {
      client_email: creds.client_email,
      private_key: creds.private_key,
    },
  });
  _bucketName = bucket;
  return _storage;
}

export function bucketName(): string {
  if (!_bucketName) {
    const b = process.env.GCS_BUCKET;
    if (!b) throw new Error('Missing GCS_BUCKET');
    _bucketName = b;
  }
  return _bucketName!;
}
