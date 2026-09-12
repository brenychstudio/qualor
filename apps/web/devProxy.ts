import type { IncomingMessage } from 'node:http';

interface ProxyRequestHeaders {
  removeHeader(name: string): void;
  setHeader(name: string, value: string): void;
}

/** Development-server boundary only; QUALOR_DEV_* values are never bundled by Vite. */
export function injectHostedOriginAuth(request: ProxyRequestHeaders, secret: string | undefined) {
  request.removeHeader('X-QUALOR-Origin-Auth');
  if (secret) request.setHeader('X-QUALOR-Origin-Auth', secret);
}

// Same-origin GET does not carry Origin in browsers. This development-only
// bridge admits the session handshake, never mutations or cross-site requests.
export function sessionOrigin(request: Pick<IncomingMessage, 'method' | 'url' | 'headers'>): string | undefined {
  if (request.method !== 'GET' || request.url !== '/api/v1/session' ||
      request.headers.origin !== undefined || request.headers['sec-fetch-site'] !== 'same-origin') return;
  const host = request.headers.host;
  if (host === '127.0.0.1:5173' || host === 'localhost:5173') return `http://${host}`;
}

export function localProxyError(error: unknown): { status: number; body: { code: 'LOCAL_DISCONNECTED' } } | undefined {
  if (error && typeof error === 'object' && 'code' in error && error.code === 'ECONNREFUSED') {
    return { status: 502, body: { code: 'LOCAL_DISCONNECTED' } };
  }
}
