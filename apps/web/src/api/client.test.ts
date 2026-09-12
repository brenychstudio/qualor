import { expect, test, vi, afterEach } from 'vitest';
import { apiRequest, ApiError, getLiveRunStatus, startLiveRun } from './client';
afterEach(() => vi.unstubAllGlobals());
test('sends a protected versioned update only to the local API', async () => {
  let received: RequestInit | undefined;
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => { received = init; return Response.json({ founder: null, projects: [] }); }));
  await apiRequest('/profile', { method: 'PUT', actionToken: 'test-process-token', body: { expected_version: 3 } });
  expect(new Headers(received?.headers).get('X-Qualor-Action-Token')).toBe('test-process-token');
  expect(received?.body).toBe('{"expected_version":3}');
  expect(received?.credentials).toBe('same-origin');
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});
test('refuses a mutation without an action token before transport', async () => {
  let transported = false;
  vi.stubGlobal('fetch', vi.fn(async () => { transported = true; return Response.json({}); }));
  await expect(apiRequest('/profile', { method: 'PUT', body: {} })).rejects.toMatchObject({ code: 'ACTION_FORBIDDEN' });
  expect(transported).toBe(false);
});
test('returns typed conflict errors without exposing response bodies', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ code: 'VERSION_MISMATCH', detail: 'private server state' }, { status: 409 })));
  const error = await apiRequest('/portfolio').catch(e => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ code: 'VERSION_MISMATCH', status: 409 });
  if (error instanceof Error) expect(error.message).not.toContain('private');
});
test('handles non-JSON failures and disconnected transport with bounded messages', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('private trace', { status: 500 })));
  await expect(apiRequest('/portfolio')).rejects.toMatchObject({ code: 'INTERNAL_ERROR' });
  vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('private transport'); }));
  await expect(apiRequest('/portfolio')).rejects.toMatchObject({ code: 'LOCAL_DISCONNECTED' });
});
test('rejects external or traversing request paths before exposing a token', async () => {
  for (const path of ['https://example.com', '//example.com', '/../session', '/profile?next=https://example.com']) {
    await expect(apiRequest(path, { method: 'PUT', actionToken: 'test-token' })).rejects.toMatchObject({ code: 'INVALID_REQUEST' });
  }
});

test('sends encoded canonical project identities without allowing path traversal', async () => {
  let destination = '';
  vi.stubGlobal('fetch', vi.fn(async (url: string) => { destination = url; return Response.json({}); }));
  await apiRequest('/projects/project%3Aone', { method: 'PUT', actionToken: 'test-token', body: {} });
  expect(destination).toBe('/api/v1/projects/project%3Aone');
  for (const path of ['/projects/%2e%2e', '/projects/%2Fother', '/projects/%5Cother', '/projects/%invalid']) {
    await expect(apiRequest(path, { method: 'PUT', actionToken: 'test-token' })).rejects.toMatchObject({ code: 'INVALID_REQUEST' });
  }
});

test('distinguishes an unavailable local proxy from a genuine backend failure', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ code: 'LOCAL_DISCONNECTED' }, { status: 502 })));
  await expect(apiRequest('/portfolio')).rejects.toMatchObject({ code: 'LOCAL_DISCONNECTED', message: 'Local controller disconnected' });
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ code: 'INTERNAL_ERROR' }, { status: 500 })));
  await expect(apiRequest('/portfolio')).rejects.toMatchObject({ code: 'INTERNAL_ERROR', status: 500 });
});

test('preserves generated error codes without custom display copy', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ code: 'READ_LIMIT_EXCEEDED' }, { status: 422 })));
  await expect(apiRequest('/portfolio')).rejects.toMatchObject({ code: 'READ_LIMIT_EXCEEDED', status: 422 });
});
test('rejects prototype and arbitrary codes without rendering unsafe response values', async () => {
  for (const code of ['toString', '__proto__', 'private error detail']) {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ code }, { status: 500 })));
    const error = await apiRequest('/portfolio').catch(error => error);
    expect(error).toMatchObject({ code: 'INTERNAL_ERROR' });
    expect(String(error)).not.toContain(code);
  }
});

test('starts hosted research with only the official URL and no browser-held capability', async () => {
  let destination = '';
  let received: RequestInit | undefined;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init) => {
    destination = url; received = init;
    return Response.json({ run_id: 'run-one', status: 'STARTING' }, { status: 202 });
  }));

  await expect(startLiveRun('https://example.org/opportunity/rules')).resolves.toEqual({
    run_id: 'run-one', status: 'STARTING',
  });

  const headers = new Headers(received?.headers);
  expect(destination).toBe('/api/v1/live-runs');
  expect(received?.method).toBe('POST');
  expect(received?.body).toBe('{"official_url":"https://example.org/opportunity/rules"}');
  expect(headers.get('X-Qualor-Action-Token')).toBeNull();
  expect(headers.get('X-QUALOR-Origin-Auth')).toBeNull();
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});

test('polls one encoded live run status through the same-origin API', async () => {
  let destination = '';
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    destination = url;
    return Response.json({
      run_id: 'run-one', status: 'RESEARCHING', mode: 'LIVE',
      started_at: '2026-09-12T12:00:00Z',
    });
  }));
  await expect(getLiveRunStatus('run-one')).resolves.toMatchObject({ status: 'RESEARCHING' });
  expect(destination).toBe('/api/v1/live-runs/run-one');
});

test('maps hosted run failures to bounded copy and never exposes server detail', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({
    code: 'LIVE_PROVIDER_FAILED', detail: 'private AWS request and endpoint',
  }, { status: 500 })));
  const error = await startLiveRun('https://example.org/rules').catch(value => value);
  expect(error).toMatchObject({ code: 'LIVE_PROVIDER_FAILED', message: 'Research could not complete.' });
  expect(String(error)).not.toContain('private AWS');
});
