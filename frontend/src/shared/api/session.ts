import validate from './session-generated-validator';
export function parseSession(value: unknown) {
  if (
    !validate(value) ||
    /\s/.test(value.access_token) ||
    value.expires_at * 1000 <= Date.now()
  )
    throw new Error('The sign-in response could not be validated. Try again.');
  return value;
}
