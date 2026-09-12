import { expect, test } from 'vitest';
import { injectHostedOriginAuth, localProxyError, sessionOrigin } from '../devProxy';
test('bridges only same-origin session reads from an approved local development host', () => {
  expect(sessionOrigin({ method: 'GET', url: '/api/v1/session', headers: { host: '127.0.0.1:5173', 'sec-fetch-site': 'same-origin' } })).toBe('http://127.0.0.1:5173');
  expect(sessionOrigin({ method: 'GET', url: '/api/v1/session', headers: { host: 'localhost:5173', 'sec-fetch-site': 'same-origin' } })).toBe('http://localhost:5173');
});
test.each([
  { method: 'PUT', url: '/api/v1/session', headers: { host: 'localhost:5173', 'sec-fetch-site': 'same-origin' } },
  { method: 'GET', url: '/api/v1/profile', headers: { host: 'localhost:5173', 'sec-fetch-site': 'same-origin' } },
  { method: 'GET', url: '/api/v1/session', headers: { host: 'localhost:5173' } },
  { method: 'GET', url: '/api/v1/session', headers: { host: 'evil.example', 'sec-fetch-site': 'same-origin' } },
  { method: 'GET', url: '/api/v1/session', headers: { host: 'localhost:5173', 'sec-fetch-site': 'cross-site' } },
  { method: 'GET', url: '/api/v1/session', headers: { host: 'localhost:5173', 'sec-fetch-site': 'same-origin', origin: 'https://evil.example' } },
])('never manufactures authority for unsafe request %j', request => { expect(sessionOrigin(request)).toBeUndefined(); });

test('maps only local connection refusal to a disconnected proxy response', () => {
  expect(localProxyError({ code: 'ECONNREFUSED' })).toEqual({ status: 502, body: { code: 'LOCAL_DISCONNECTED' } });
  expect(localProxyError({ code: 'OTHER' })).toBeUndefined();
  expect(localProxyError(new Error('private failure detail'))).toBeUndefined();
});

test('development proxy overwrites browser origin auth only when an explicit server secret exists', () => {
  const changes: string[] = [];
  const request = {
    removeHeader(name: string) { changes.push(`remove:${name}`); },
    setHeader(name: string, value: string) { changes.push(`set:${name}:${value}`); },
  };
  injectHostedOriginAuth(request, 'test-only-server-secret-xxxxxxxxxxxxxxxx');
  expect(changes).toEqual([
    'remove:X-QUALOR-Origin-Auth',
    'set:X-QUALOR-Origin-Auth:test-only-server-secret-xxxxxxxxxxxxxxxx',
  ]);
  changes.length = 0;
  injectHostedOriginAuth(request, undefined);
  expect(changes).toEqual(['remove:X-QUALOR-Origin-Auth']);
});
