/* Supabase SDK and session controller are bundled together for a trusted origin. */
const { createClient } = require('@supabase/supabase-js');
const { createSession } = require('./session-factory.js');
window.CaseProofLiveAuth = Object.freeze({
  create: config => createSession({ ...config, createClient, office: Office, origin: location.origin }),
});
