const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createClient } = require('@supabase/supabase-js');
const { createMemoryStorage } = require('./session-factory.js');

test('actual Supabase SDK creates PKCE flow using isolated storage', async () => {
  const storage = createMemoryStorage();
  const client = createClient('https://example.supabase.co', 'sb_publishable_test', {
    auth: { flowType: 'pkce', storage, persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
  });
  const result = await client.auth.signInWithOAuth({ provider: 'google', options: {
    redirectTo: 'https://word.example/auth-callback.html', skipBrowserRedirect: true,
  } });
  assert.equal(result.error, null);
  const url = new URL(result.data.url);
  assert.equal(url.origin, 'https://example.supabase.co');
  assert.equal(url.searchParams.get('code_challenge_method'), 's256');
  assert.ok(url.searchParams.get('code_challenge'));
  assert.equal(url.searchParams.get('redirect_to'), 'https://word.example/auth-callback.html');
});
