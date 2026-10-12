# Scraping and acting on Gmail in Chrome

Only a Gmail account with no connector needs this. The connector mailbox uses
the Gmail MCP tools and never comes here.

The selectors below (`tr.zA`, `.bog`, `.xW`, `.y2`) are Gmail's own class names
as of late 2026 and are not a public interface. If a scrape returns nothing,
inspect a row and correct them before doing anything else. Dates in the
examples are examples: substitute the run's own.

Every script starts by forcing the view back to the inbox, because the tab
drifts between calls:

```js
location.hash='#inbox'; await new Promise(r=>setTimeout(r,3500));
```

## Scrape rows into classifier input

`javascript_tool` truncates output near 1000 characters. Scrape in slices and
keep the fields short.

```js
location.hash='#inbox'; await new Promise(r=>setTimeout(r,3500));
const cut = new Date('2026-09-16T12:00:00');   // window start
const rows = [...document.querySelectorAll('tr.zA')].map(r => ({
  id:   (r.querySelector('.xW span')?.getAttribute('title')||'') + '|' + (r.querySelector('.bog')?.textContent||'').slice(0,28),
  from: (r.querySelector('.yX,.yW span')?.textContent||'').slice(0,40),
  subject: (r.querySelector('.bog')?.textContent||'').slice(0,80),
  snippet: (r.querySelector('.y2')?.textContent||'').slice(0,120),
  date: r.querySelector('.xW span')?.getAttribute('title')||''
})).filter(x => new Date(x.date) >= cut);
JSON.stringify(rows.slice(0,16))   // next call: slice(16,32), and so on
```

The `id` is `full timestamp | first 28 chars of subject`. It is stable enough to
tick the same row again and it needs no Gmail internals.

## Tick the rows the classifier marked for archiving

```js
location.hash='#inbox'; await new Promise(r=>setTimeout(r,3500));
const IDS = new Set([/* ids with action archive or label_and_archive */]);
let ticked=0;
for (const r of document.querySelectorAll('tr.zA')) {
  const id = (r.querySelector('.xW span')?.getAttribute('title')||'') + '|' + (r.querySelector('.bog')?.textContent||'').slice(0,28);
  if (!IDS.has(id)) continue;
  const cb = r.querySelector('div[role=checkbox]');
  if (cb && cb.getAttribute('aria-checked') !== 'true') { cb.click(); ticked++; }
}
ticked
```

## Guard before archiving

Apply the `Triage/<date>` label first, then check that every ticked row carries
it. `bad` must be 0 before you archive:

```js
const sel = [...document.querySelectorAll('tr.zA')].filter(r => r.querySelector('div[role=checkbox][aria-checked=true]'));
({ selected: sel.length, bad: sel.filter(r => !/2026-09-21/.test(r.textContent)).length })   // the day label's date
```

Archive accepts a synthetic click:

```js
['mousedown','mouseup','click'].forEach(t =>
  document.querySelector('div[aria-label="Archive"]').dispatchEvent(new MouseEvent(t,{bubbles:true})));
```

## Things that bite

- The Labels menu does **not** open from a synthetic click. Take a screenshot and
  click the real toolbar coordinates.
- Creating a label: type the name, then click the row that reads
  `"Triage/<date>" (create new)`. The dialog that opens is already filled in, so
  only Create is left to press.
- Gmail refills the window with older rows after each archive. Re-scan and repeat
  until only keepers remain.
- Check which `u/<n>` in the URL is the mailbox you mean (`u/0` in the examples
  here). Other indexes may belong to someone else. Never read those.

## Three rules, each learned from a run that went wrong

**1. Scope every scrape to the visible pane.** Gmail keeps old result tables in
the DOM. A bare `document.querySelectorAll('tr.zA')` returned 150 rows of the
previous view no matter what the search box said, which made a label check
report success against rows that were not on screen.

```js
const main = document.querySelector('div[role=main]');
const rows = [...document.querySelectorAll('tr.zA')].filter(r => r.offsetParent && main.contains(r));
```

**2. Convert DOM coordinates before clicking.** The click frame and the page
viewport are different sizes. Multiply by the ratio or every click lands high
and left:

```js
const k = 1092 / innerWidth;           // 1092 = the width your screenshot tool reports; use yours
[Math.round((r.x + r.width/2) * k), Math.round((r.y + r.height/2) * k)]
```

**3. Never type until an input really has focus.** With rows selected and no
menu open, the typed label name becomes Gmail keyboard shortcuts: `e` archived
the whole selection and `t` opened a "create 12 tasks" confirmation. Check
first, every time:

```js
const m = [...document.querySelectorAll('div[role=menu]')].find(x => x.offsetParent);
const inp = m && m.querySelector('input');
({ menuOpen: !!m, inputFocused: !!inp && document.activeElement === inp })   // both must be true
```

## Creating the day label without the flaky menu

Do it in Settings, with synthetic clicks and the native value setter. This
worked when three real-click attempts did not:

```js
// at https://mail.google.com/mail/u/0/#settings/labels
const open = [...document.querySelectorAll('div[role=button],button')].find(e => /create new label/i.test(e.textContent));
['mousedown','mouseup','click'].forEach(t => open.dispatchEvent(new MouseEvent(t,{bubbles:true})));
// then, after a moment:
const inp = [...document.querySelectorAll('input[type=text]')].find(i => i.offsetParent && i.name !== 'q');
Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(inp, 'Triage/2026-09-22');
inp.dispatchEvent(new Event('input',{bubbles:true}));
const create = [...document.querySelectorAll('button,div[role=button]')].find(b => b.offsetParent && b.textContent.trim() === 'Create');
['mousedown','mouseup','click'].forEach(t => create.dispatchEvent(new MouseEvent(t,{bubbles:true})));
```

Once the label exists, applying it is safe: real-click the Labels toolbar icon,
confirm the menu input has focus, type the name, click the filtered row.
