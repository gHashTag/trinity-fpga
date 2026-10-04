// Prune the Actions cache so the 10 GB budget holds entries that can still be
// restored. gHashTag/trinity-fpga#844.
//
// Two kinds of entry are dead weight:
//
// - Entries saved on a pull request's merge ref. Only that pull request can
//   restore them, so once it is closed nothing reads them again. The same holds
//   for a branch that has been deleted.
// - Older entries of a key that ends in the run id. mlugg/setup-zig saves
//   `setup-zig-cache-v2-<job>-...--<run_id>-<attempt>` on every run and restores
//   by prefix, which takes the newest match, so every older entry of the same
//   series on the same ref is never read.
//
// Everything else is kept: fixed keys (setup-zig-tarball-*, the chipdb keyed on
// part + image) and the newest entry of every series on every live ref.

'use strict';

// A run id (8 or more digits) at the end of a key, with an optional attempt.
const RUN_SUFFIX = /-\d{8,}(?:-\d+)?$/;

// The key with its run id removed, or null when the key is fixed.
function seriesOf(key) {
  const perRun = RUN_SUFFIX.test(key);
  if (!perRun) return null;
  return key.replace(RUN_SUFFIX, '');
}

function prNumberOf(ref) {
  const m = /^refs\/pull\/(\d+)\/merge$/.exec(ref);
  const isPr = m !== null;
  if (!isPr) return null;
  return Number(m[1]);
}

function newestFirst(a, b) {
  const sameTime = a.created_at === b.created_at;
  if (sameTime) return b.id - a.id;
  return a.created_at < b.created_at ? 1 : -1;
}

// caches:   [{id, key, ref, size_in_bytes, created_at}] as the REST API returns them
// closed:   Set of pull request numbers that are closed
// goneRefs: Set of branch refs (refs/heads/...) that no longer exist
// Returns {drop: [{entry, reason}], keep: [entry]}.
function plan(caches, closed, goneRefs) {
  const drop = [];
  const keep = [];
  const series = new Map();
  for (const c of caches) {
    const pr = prNumberOf(c.ref);
    const prClosed = pr !== null && closed.has(pr);
    if (prClosed) {
      drop.push({ entry: c, reason: `pull request #${pr} is closed` });
      continue;
    }
    const refGone = goneRefs.has(c.ref);
    if (refGone) {
      drop.push({ entry: c, reason: `${c.ref} no longer exists` });
      continue;
    }
    const s = seriesOf(c.key);
    const fixedKey = s === null;
    if (fixedKey) {
      keep.push(c);
      continue;
    }
    const slot = `${c.ref}\n${s}`;
    const known = series.has(slot);
    if (!known) series.set(slot, []);
    series.get(slot).push(c);
  }
  for (const [slot, entries] of series) {
    entries.sort(newestFirst);
    keep.push(entries[0]);
    const newest = entries[0].key;
    for (const c of entries.slice(1)) {
      drop.push({ entry: c, reason: `superseded by ${newest} on ${slot.split('\n')[0]}` });
    }
  }
  return { drop, keep };
}

function bytes(list) {
  return list.reduce((n, c) => n + c.size_in_bytes, 0);
}

function gb(n) {
  return (n / 1e9).toFixed(2);
}

async function run({ github, context, core, dryRun }) {
  const { owner, repo } = context.repo;
  const caches = await github.paginate(github.rest.actions.getActionsCacheList, {
    owner, repo, per_page: 100,
  });

  const closed = new Set();
  const prs = new Set(caches.map((c) => prNumberOf(c.ref)).filter((n) => n !== null));
  for (const pull_number of prs) {
    const { data } = await github.rest.pulls.get({ owner, repo, pull_number });
    const isClosed = data.state === 'closed';
    if (isClosed) closed.add(pull_number);
  }

  const goneRefs = new Set();
  const branchRefs = new Set(caches.map((c) => c.ref).filter((r) => r.startsWith('refs/heads/')));
  for (const ref of branchRefs) {
    const branch = ref.slice('refs/heads/'.length);
    try {
      await github.rest.repos.getBranch({ owner, repo, branch });
    } catch (e) {
      const missing = e.status === 404;
      if (!missing) throw e;
      goneRefs.add(ref);
    }
  }

  const { drop, keep } = plan(caches, closed, goneRefs);
  core.info(`${caches.length} entries, ${gb(bytes(caches))} GB; ` +
    `drop ${drop.length} (${gb(bytes(drop.map((d) => d.entry)))} GB), keep ${keep.length} (${gb(bytes(keep))} GB)` +
    (dryRun ? ' [dry run]' : ''));

  let deleted = 0;
  let deletedBytes = 0;
  let failed = 0;
  for (const { entry, reason } of drop) {
    core.info(`${dryRun ? 'would drop' : 'drop'} ${entry.id} ${entry.ref} ${entry.key}: ${reason}`);
    if (dryRun) continue;
    try {
      await github.rest.actions.deleteActionsCacheById({ owner, repo, cache_id: entry.id });
      deleted += 1;
      deletedBytes += entry.size_in_bytes;
    } catch (e) {
      // A concurrent prune may have taken it first.
      const alreadyGone = e.status === 404;
      if (alreadyGone) continue;
      failed += 1;
      core.warning(`could not delete ${entry.id} ${entry.key}: ${e.message}`);
    }
  }

  await core.summary
    .addHeading('Actions cache prune', 3)
    .addTable([
      [{ data: '', header: true }, { data: 'entries', header: true }, { data: 'GB', header: true }],
      ['before', `${caches.length}`, gb(bytes(caches))],
      [dryRun ? 'would drop' : 'dropped', `${dryRun ? drop.length : deleted}`, gb(dryRun ? bytes(drop.map((d) => d.entry)) : deletedBytes)],
      ['kept', `${keep.length}`, gb(bytes(keep))],
    ])
    .write();
  if (failed > 0) core.setFailed(`${failed} cache entries could not be deleted`);
}

module.exports = { plan, run, seriesOf, prNumberOf };
