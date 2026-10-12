// Unit tests for the copilot context helper: node --test tests/hoard-copilot.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { buildContext, changedRegionFields, rebaseProject, reportView, view } from '../src/hoard-copilot.ts';

const project = {
  id: 'abcdef012345',
  name: 'Dragon',
  revision: 4,
  approved: false,
  proposal: null,
  models: [{ id: 'm1', name: 'dragon.glb', file: 'm1.glb' }],
  assets: [
    {
      id: 'tex0000001',
      name: 'body.png',
      approved: false,
      regions: [
        { id: 0, name: 'Skin', height: 128, geometry: 'painted', confidence: 0.8 },
        { id: 1, name: 'Eyes', height: 90, geometry: 'modeled', confidence: null },
      ],
    },
    { id: 'tex0000002', name: 'wings.png', approved: true, regions: [] },
  ],
};
const loader = (data) => async (path) => {
  if (path === `/api/projects/${project.id}`) return structuredClone(data);
  throw new Error('404');
};
const state = (patch = {}) => ({
  projectId: project.id,
  assetId: null,
  regionId: null,
  surface: 'model',
  mode: 'original',
  tab: 'regions',
  panel: 'workspace',
  regionDraft: null,
  commandDraft: '',
  ...patch,
});

test('a pending project read keeps the originating view and nested draft', async () => {
  const current = state({ assetId: 'tex0000001', regionId: 1, regionDraft: { name: 'A draft', height: 60 }, commandDraft: 'A instruction' });
  let resolve;
  const pending = new Promise((done) => { resolve = done; });
  const answer = buildContext(current, () => pending);
  current.regionDraft.name = 'B nested draft';
  Object.assign(current, { projectId: 'bbbbbbbbbbbb', assetId: 'b1', regionId: 2, surface: 'uv', tab: 'other', panel: 'control', commandDraft: 'B instruction' });
  resolve(structuredClone(project));
  const ctx = await answer;
  assert.equal(ctx.project.external_project_id, project.id);
  assert.equal(ctx.view.page, 'project');
  assert.equal(ctx.view.surface, 'model');
  assert.equal(ctx.view.inspector_tab, 'regions');
  assert.equal(ctx.view.editor.fields.name, 'A draft');
  assert.deepEqual(ctx.active_objects.map((x) => [x.kind, x.object_id]), [['project', project.id], ['texture', 'tex0000001'], ['region', 'tex0000001:1']]);
});

test('refresh adopts an agent height while preserving the user name and a save acknowledges only its snapshot', () => {
  const base = structuredClone(project);
  const draft = structuredClone(base);
  draft.assets[0].regions[1].name = 'User draft';
  const fresh = structuredClone(base);
  fresh.assets[0].regions[1].height = 88;
  const merged = rebaseProject(base, fresh, draft);
  assert.equal(merged.assets[0].regions[1].name, 'User draft');
  assert.equal(merged.assets[0].regions[1].height, 88);
  assert.deepEqual(changedRegionFields(fresh.assets[0].regions[1], merged.assets[0].regions[1]), { name: 'User draft' });
  const later = structuredClone(merged);
  later.assets[0].regions[1].name = 'Later typing';
  const saved = structuredClone(fresh);
  saved.assets[0].regions[1].name = 'User draft';
  assert.equal(rebaseProject(merged, saved, later).assets[0].regions[1].name, 'Later typing');
  assert.equal(rebaseProject(base, { ...fresh, id: 'other' }, draft).id, 'other');
});

test('context distinguishes user edits from a server field changed during its read', async () => {
  const fresh = structuredClone(project);
  fresh.assets[0].regions[1].height = 88;
  const current = state({ assetId: 'tex0000001', regionId: 1, regionDraft: { name: 'Eyes', height: 90 }, regionChanges: {} });
  assert.equal((await buildContext(current, loader(fresh))).view.editor, undefined);
  current.regionChanges = { name: 'User draft' };
  assert.deepEqual((await buildContext(current, loader(fresh))).view.editor.fields, { name: 'User draft' });
});

test('a project view returns the real project, texture and omits nothing it knows', async () => {
  const ctx = await buildContext(state(), loader(project));
  assert.equal(ctx.project.external_project_id, project.id);
  assert.equal(ctx.project.title, 'Dragon');
  assert.deepEqual(
    ctx.active_objects.map((o) => [o.kind, o.object_id]),
    [
      ['project', project.id],
      ['texture', 'tex0000001'],
    ],
  );
  assert.equal(ctx.view.page, 'project');
});

test('the selected region is an object named like the command editor does', async () => {
  const ctx = await buildContext(state({ assetId: 'tex0000001', regionId: 1 }), loader(project));
  const region = ctx.active_objects.find((o) => o.kind === 'region');
  assert.deepEqual([region.object_id, region.title, region.height], ['tex0000001:1', 'Eyes', 90]);
});

test('an unsaved region edit goes to view.editor with the saved values beside it', async () => {
  const draft = { name: 'Eyes deeper', height: 60, displacementColor: null };
  const ctx = await buildContext(
    state({ assetId: 'tex0000001', regionId: 1, regionDraft: draft }),
    loader(project),
  );
  assert.equal(ctx.view.editor.kind, 'region');
  assert.equal(ctx.view.editor.dirty, true);
  assert.equal(ctx.view.editor.fields.name, 'Eyes deeper');
  assert.equal(ctx.view.editor.saved.name, 'Eyes');
  const clean = await buildContext(
    state({
      assetId: 'tex0000001',
      regionId: 1,
      regionDraft: { name: 'Eyes', height: 90, displacementColor: null },
    }),
    loader(project),
  );
  assert.equal(clean.view.editor, undefined);
});

test('an unsent instruction is an editor too', async () => {
  const ctx = await buildContext(state({ commandDraft: 'Eyes deeper' }), loader(project));
  assert.deepEqual(ctx.view.editor, {
    kind: 'command',
    dirty: true,
    fields: { instruction: 'Eyes deeper' },
  });
});

test('no project, an unknown id or a failing API gives empty objects and no project key', async () => {
  for (const s of [
    state({ projectId: null }),
    state({ projectId: 'ffffffffffff' }),
    state({ projectId: 'not-an-id' }),
  ]) {
    const ctx = await buildContext(s, loader(project));
    assert.deepEqual(ctx.active_objects, []);
    assert.equal('project' in ctx, false);
  }
  const broken = await buildContext(state(), async () => {
    throw new Error('down');
  });
  assert.deepEqual(broken.active_objects, []);
});

test('the pose and team panels are pages of their own', async () => {
  assert.equal((await buildContext(state({ panel: 'pose' }), loader(project))).view.page, 'pose');
  assert.equal(
    (await buildContext(state({ panel: 'control' }), loader(project))).view.page,
    'control',
  );
});

test('reportView keeps the state and announces a project change once', () => {
  const events = [];
  globalThis.window = { dispatchEvent: (e) => events.push(e.type) };
  reportView({ projectId: 'a' });
  reportView({ projectId: 'a', surface: 'uv' });
  reportView({ projectId: 'b' });
  assert.deepEqual(events, ['hoard:copilot-context-changed', 'hoard:copilot-context-changed']);
  assert.equal(view.surface, 'uv');
  delete globalThis.window;
});
