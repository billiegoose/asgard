// Run: node --experimental-strip-types --test .pi/skills/ultrapowers/tests/routing.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import install from '../../../extensions/ultrapowers-pi.ts';

async function contextWith(environment, messages = []) {
  const saved = Object.fromEntries(Object.keys(environment).map(key => [key, process.env[key]]));
  try {
    for (const [key, value] of Object.entries(environment)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    const handlers = new Map();
    install({ on: (name, handler) => handlers.set(name, handler) });
    return await handlers.get('context')({ messages });
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function text(result) {
  return result.messages[0].content.map(block => block.text).join('\n');
}

test('Paseo parent receives visible-agent routing for planning and execution', async () => {
  const result = await contextWith({ PASEO_AGENT_ID: 'parent-id' });
  assert.match(text(result), /prefer Paseo-managed agents/i);
  assert.match(text(result), /planning.*review/i);
  assert.match(text(result), /OpenAI/);
  assert.match(text(result), /PASEO_CLI/);
  assert.doesNotMatch(text(result), /prefer.*Pi-native execution/);
});

for (const id of [undefined, '', '   ']) {
  test(`outside Paseo keeps Pi routing (agent ID ${JSON.stringify(id)})`, async () => {
    const result = await contextWith({ PASEO_AGENT_ID: id, PASEO_CLI: '/installed/paseo' });
    assert.match(text(result), /Outside Paseo/);
    assert.match(text(result), /Pi subagent workflows or Taskplane/);
    assert.doesNotMatch(text(result), /prefer Paseo-managed agents/i);
  });
}

test('Paseo routing preserves ownership and reports failures instead of switching', async () => {
  const result = await contextWith({ PASEO_AGENT_ID: 'parent-id' });
  assert.match(text(result), /no silent.*fallback/i);
  assert.match(text(result), /existing runs.*backend/i);
  assert.match(text(result), /capability.*boundaries/i);
});

test('injection preserves caller messages and is idempotent', async () => {
  const messages = [{ role: 'user', content: 'Execute the approved plan.', timestamp: 1 }];
  const snapshot = structuredClone(messages);
  const result = await contextWith({ PASEO_AGENT_ID: 'parent-id' }, messages);
  assert.deepEqual(messages, snapshot);
  assert.equal(result.messages.length, 2);
  assert.equal(result.messages[1], messages[0]);
  assert.equal(await contextWith({ PASEO_AGENT_ID: 'parent-id' }, result.messages), undefined);
});
