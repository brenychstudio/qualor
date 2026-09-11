import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

/**
 * The approved judge flow, driven through the real API in a real browser.
 *
 * Everything asserted here was produced by the server from one owned FIXTURE file:
 * the recommendation, the evidence, the approval and the pack are all read back over
 * HTTP. The test never stubs a response and never asserts a value it supplied itself.
 */

const SUBMISSION_WORDS = /\bsubmit|\bsend\b|apply now|\bpublish|dispatch|\bemail\b|devpost|autofill/i;

test.beforeEach(async ({ page }) => {
  await page.goto('/inbox');
});

test('the first screen shows the decision hierarchy before any detail is opened', async ({ page }) => {
  const row = page.getByRole('link', { name: /AWS Agents for Humans/ });
  await expect(row).toBeVisible();

  await row.click();
  await expect(page).toHaveURL(/\/inbox\/opp_/);

  // First-five-seconds hierarchy: recommendation, project, effort and deadline are all
  // legible without opening the proof layer.
  await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
  await expect(page.getByText('Recommendation: APPLY')).toBeVisible();
  const facts = page.getByRole('group', { name: 'Decision signals' });
  await expect(facts).toBeVisible();
  await expect(page.getByRole('group', { name: 'Deadline' })).toBeVisible();

  // Strategy is prioritisation, never a probability of winning.
  const strategy = page.getByRole('group', { name: 'Strategy priority' });
  await expect(strategy).toContainText(/prioritization/i);
  await expect(strategy).not.toContainText(/win probability|chance/i);

  // The proof layer is still closed at this point.
  await expect(page.getByRole('region', { name: 'Decision proof' })).toHaveCount(0);
});

test('fixture work is labelled FIXTURE and never presented as live research', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  const operational = page.getByLabel('Current decision state');
  await expect(operational).toContainText('FIXTURE');
  await expect(operational).not.toContainText('LIVE');
  await expect(page.locator('body')).not.toContainText(/Bedrock|AgentCore/i);

  // Refining the rail must not let recorded fixture history read as live work. The rail states
  // the recorded mode and the run's own outcome, and claims no retrieval it did not perform.
  const rail = page.getByRole('region', { name: 'Intelligence' });
  await expect(rail).toContainText('FIXTURE');
  await expect(rail).toContainText('COMPLETED');
  await expect(rail).not.toContainText(/\bLIVE\b/);
  await expect(rail).not.toContainText(/searching|in progress|running now|live research/i);
});

test('the Intelligence Rail reads as the operational trail behind this decision', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  const rail = page.getByRole('region', { name: 'Intelligence' });

  // Exactly the three observations the server persisted, in the recorded sequence. The seeded
  // run stamps all three with one instant, so the order has to come from the sequence.
  const recorded = await page.request.get('/api/v1/runs').then(response => response.json());
  const rows = rail.getByRole('list', { name: /recorded activity/i }).getByRole('listitem');
  await expect(rows).toHaveCount(recorded.events.length);
  // Read from each event's own persisted sequence, which restarts per run, rather than from its
  // position in the response.
  await expect(rows.locator('.event-order')).toHaveText(
    recorded.events.map((event: { sequence: number }) => String(event.sequence).padStart(2, '0')));
  await expect(rows.locator('.event-title')).toHaveText(
    ['Opportunity discovered', 'Evidence recorded', 'Decision updated']);
  // Only the recorded decision update is marked as the decision outcome.
  await expect(rail.locator('li[data-outcome="true"]')).toHaveCount(1);
  await expect(rail.locator('li[data-outcome="true"] .event-title')).toHaveText('Decision updated');

  // The run's own counters, scoped to the run and matching what the server recorded. Nothing is
  // borrowed from the evidence sheet to make the rail look busier than the run actually was.
  const metrics = rail.getByRole('group', { name: /recorded in this run/i });
  await expect(metrics.locator('dd')).toHaveText(['0', '0', '0', '0']);
  expect(recorded.runs.at(-1)).toMatchObject({
    search_calls: 0, fetched_documents: 0, official_source_count: 0, verified_claim_count: 0,
  });
  await expect(metrics).toContainText(/no retrieval or verification call is recorded/i);

  // The recorded stop reason reads as copy; the canonical code stays available, not displayed.
  const termination = rail.locator('.run-termination');
  await expect(termination).toHaveText(/critical evidence/i);
  await expect(rail).not.toContainText('SUFFICIENT_CRITICAL_EVIDENCE');
  await expect(termination).toHaveAttribute('title', 'SUFFICIENT_CRITICAL_EVIDENCE');
});

test.describe('reduced-motion rail', () => {
  test.use({ reducedMotion: 'reduce' });
  test('the recorded trail is complete and in order without any motion', async ({ page }) => {
    await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
    const rail = page.getByRole('region', { name: 'Intelligence' });
    const rows = rail.getByRole('list', { name: /recorded activity/i }).getByRole('listitem');
    await expect(rows.locator('.event-title')).toHaveText(
      ['Opportunity discovered', 'Evidence recorded', 'Decision updated']);
    // The entry keyframes start at opacity 0 and fill both, so a row frozen invisible would
    // still satisfy a visibility check. The painted state is asserted directly instead.
    const painted = await rows.evaluateAll(items => items.map(item => ({
      opacity: getComputedStyle(item).opacity,
      animations: item.getAnimations().length,
    })));
    expect(painted).toEqual([
      { opacity: '1', animations: 0 }, { opacity: '1', animations: 0 }, { opacity: '1', animations: 0 },
    ]);
    await expect(rail).toContainText(/no retrieval or verification call is recorded/i);
  });
});

test('Why this decision opens source-grounded proof and returns to the dark workspace', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();

  const trigger = page.getByRole('button', { name: /why this decision/i });
  await trigger.click();

  const plane = page.getByRole('region', { name: 'Decision proof' });
  await expect(plane).toBeVisible();
  await expect(plane.getByRole('region', { name: 'Eligibility' })).toBeVisible();

  // The exact official citation the Evidence Sheet contract preserves.
  const citation = plane.getByRole('link', { name: /view original/i }).first();
  await expect(citation).toBeVisible();
  await expect(citation).toHaveAttribute('href', /^https:\/\/rules\.aws-agents-for-humans\.example\//);
  await expect(citation).toHaveAttribute('target', '_blank');
  await expect(citation).toHaveAttribute('rel', /noopener/);

  // An exact excerpt is quoted rather than paraphrased.
  await expect(plane.locator('blockquote').first()).not.toBeEmpty();

  // Proof is bounded to the Decision + Why/Proof span it belongs to. It replaces the decision
  // content and stops at the proof/intelligence boundary, so the judge keeps the surrounding
  // four-zone context: the selected opportunity on one side, recorded activity on the other.
  const rail = page.getByRole('complementary', { name: 'Workspace context' });
  const queue = page.getByRole('complementary', { name: 'Opportunity inbox' });
  await expect(rail).toBeVisible();
  await expect(queue).toBeVisible();
  // Settled geometry, after any entry choreography has finished. Containment over the whole
  // course of that entry is asserted separately, in the integrated reader tests below.
  await plane.evaluate(element => Promise.all(element.getAnimations().map(a => a.finished.catch(() => {}))));
  const [planeBox, railBox, queueBox, width] = await Promise.all([
    plane.boundingBox(), rail.boundingBox(), queue.boundingBox(),
    page.evaluate(() => window.innerWidth),
  ]);
  expect(planeBox!.x + planeBox!.width).toBeLessThanOrEqual(railBox!.x + 1);
  expect(planeBox!.x + planeBox!.width).toBeLessThan(width);
  expect(planeBox!.x).toBeGreaterThanOrEqual(queueBox!.x + queueBox!.width - 1);

  await page.keyboard.press('Escape');
  await expect(plane).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
});

test('recorded activity is visible and claims no progress it did not make', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  const rail = page.getByRole('region', { name: 'Intelligence' });
  await expect(rail).toBeVisible();
  await expect(rail).toContainText('FIXTURE');
  await expect(rail.getByRole('list', { name: /recorded activity/i })).toBeVisible();
  await expect(rail).not.toContainText(/searching now|in progress/i);
});

test('the whole approved story ends at a prepared pack, never at a submission', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();

  // The approval entry point offered by the deterministic result.
  const action = page.getByRole('button', { name: 'Approve application' });
  await expect(action).toBeEnabled();
  await action.click();

  const checkpoint = page.getByRole('region', { name: 'Human approval' });
  await expect(checkpoint).toBeVisible();
  await expect(checkpoint).toContainText('PENDING_APPROVAL');
  await expect(checkpoint).toContainText('GENERATE_DRAFT_PACK');
  await expect(checkpoint).toContainText(/nothing is submitted externally/i);
  await expect(checkpoint).toContainText(/opportunity version/i);

  // No control anywhere in the checkpoint implies sending anything outward.
  for (const control of await checkpoint.getByRole('button').all()) {
    expect(await control.textContent() ?? '').not.toMatch(SUBMISSION_WORDS);
  }

  await checkpoint.getByRole('button', { name: /confirm approval/i }).click();
  await expect(checkpoint).toContainText('DRAFT_READY');

  const openPack = checkpoint.getByRole('link', { name: /open draft pack/i });
  await expect(openPack).toBeVisible();
  await openPack.click();

  const pack = page.getByRole('article', { name: 'Application pack' });
  await expect(pack).toBeVisible();
  await expect(page).toHaveURL(/\/draft-packs\/.+/);

  const packUrl = page.url();
  const sections = pack.getByRole('region');
  await expect(sections).toHaveCount(7);
  await expect(sections.nth(0)).toHaveAttribute('data-section-key', 'SUBMISSION_SUMMARY');
  await expect(sections.nth(6)).toHaveAttribute('data-section-key', 'SUGGESTED_APPLICATION_ANSWERS');

  await expect(pack.getByRole('group', { name: /bound versions/i })).toBeVisible();
  await expect(pack.getByRole('group', { name: /missing information/i })).toBeVisible();
  await expect(pack.getByRole('group', { name: /source and evidence references/i })).toBeVisible();
  await expect(pack).toContainText('DRAFT_FOR_HUMAN_REVIEW');
  await expect(pack).toContainText('FIXTURE');

  // Nothing in the finished document offers an external action.
  for (const control of await pack.getByRole('link').all()) {
    expect(await control.textContent() ?? '').not.toMatch(SUBMISSION_WORDS);
  }
  await expect(pack.getByRole('button')).toHaveCount(0);

  // A direct reload rebuilds the same persisted pack with no prior app state.
  await page.goto(packUrl);
  const reloaded = page.getByRole('article', { name: 'Application pack' });
  await expect(reloaded).toBeVisible();
  await expect(reloaded.getByRole('region')).toHaveCount(7);
  await expect(reloaded).toContainText('DRAFT_FOR_HUMAN_REVIEW');
});

test('the wide workspace body keeps its canonical four zones', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();

  // ADR 0004: at 1280px and above the body is inbox, canvas, proof and rail. Proof and
  // telemetry are separate authorities, so the Evidence Plane holds its own zone and is
  // never folded back into the Intelligence Rail.
  await expect(page.getByRole('complementary', { name: 'Opportunity inbox' })).toBeVisible();
  await expect(page.getByRole('main')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Why & proof' })).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Workspace context' })).toBeVisible();

  // The workspace body is the grid; the header is navigation, not a zone. Asserting the
  // computed area projection rather than a child count means a regression to
  // `queue canvas rail` fails here instead of passing quietly.
  const areas = await page
    .locator('.workspace-grid')
    .evaluate(element => getComputedStyle(element).gridTemplateAreas);
  expect(areas.replace(/"/g, ' ').replace(/\s+/g, ' ').trim()).toBe('queue canvas proof rail');

  // Each zone is a direct child of the body grid, so proof sits beside the rail, not inside it.
  for (const zone of ['Opportunity inbox', 'Why & proof', 'Workspace context']) {
    await expect(page.locator(`.workspace-grid > [aria-label="${zone}"]`)).toBeVisible();
  }
});

test('the browser never receives an action token it could leak', async ({ page }) => {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  await page.getByRole('button', { name: 'Approve application' }).click();
  await expect(page.getByRole('region', { name: 'Human approval' })).toContainText('PENDING_APPROVAL');

  // The token travels in a request header only: never a URL, never browser storage.
  expect(page.url()).not.toMatch(/token/i);
  const stored = await page.evaluate(() => ({
    local: JSON.stringify(window.localStorage),
    session: JSON.stringify(window.sessionStorage),
  }));
  expect(stored.local).not.toMatch(/token/i);
  expect(stored.session).not.toMatch(/token/i);
});

/* --------------------------------------------------------------------------------------------
 * The integrated evidence reader.
 *
 * The previous composition passed every element-bound assertion and still failed as a picture:
 * opaque box-shadow bars painted 16px into the Inbox and 10px into the Rail, and the closed
 * central view leaked a card cap above the reader and a Decision Trace fragment below it.
 * Neither defect is visible to a boundingBox() check, because box-shadow paints outside the
 * border box and a covered fragment is still inside its own zone. These assertions read the
 * rendered pixels and the reader's real grid anchor instead.
 * ------------------------------------------------------------------------------------------ */

type Band = { x0: number; x1: number; y0: number; y1: number };

/** Brightest pixel each band contains, measured from the actual rendered frame. The screenshot
 *  is decoded by the same browser that produced it, so no image dependency is introduced. */
async function brightestInBands(page: Page, bands: Band[]): Promise<number[]> {
  const frame = (await page.screenshot()).toString('base64');
  return page.evaluate(async ({ frame, bands }) => {
    const image = new Image();
    image.src = `data:image/png;base64,${frame}`;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext('2d')!;
    context.drawImage(image, 0, 0);
    return bands.map(band => {
      const width = Math.max(1, Math.round(band.x1 - band.x0));
      const height = Math.max(1, Math.round(band.y1 - band.y0));
      const { data } = context.getImageData(Math.round(band.x0), Math.round(band.y0), width, height);
      let brightest = 0;
      for (let index = 0; index < data.length; index += 4) {
        const luminance = 0.2126 * data[index] + 0.7152 * data[index + 1] + 0.0722 * data[index + 2];
        if (luminance > brightest) brightest = luminance;
      }
      return Math.round(brightest);
    });
  }, { frame, bands });
}

/** Side gutters taken from the frozen zone geometry: the last clear pixels of the Inbox padding
 *  and the first clear pixels of the Rail padding, either side of the central span. */
async function sideGutters(page: Page): Promise<Band[]> {
  const [queue, rail, header, height] = await Promise.all([
    page.getByRole('complementary', { name: 'Opportunity inbox' }).boundingBox(),
    page.getByRole('complementary', { name: 'Workspace context' }).boundingBox(),
    page.locator('.workspace-header').boundingBox(),
    page.evaluate(() => window.innerHeight),
  ]);
  const y0 = header!.y + header!.height + 30;
  const y1 = height - 30;
  return [
    { x0: queue!.x + queue!.width - 20, x1: queue!.x + queue!.width - 2, y0, y1 },
    { x0: rail!.x + 2, x1: rail!.x + 16, y0, y1 },
  ];
}

async function selectOpportunity(page: Page) {
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

test('the open reader paints only inside the central span, entry included', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 810 });
  await selectOpportunity(page);

  const gutters = await sideGutters(page);
  const closed = await brightestInBands(page, gutters);

  // Record the reader's painted position every frame, so the entry choreography is measured
  // over its whole course rather than after getAnimations() has settled.
  await page.evaluate(() => {
    const store = window as unknown as { readerFrames: { left: number; right: number; top: number; bottom: number }[] };
    store.readerFrames = [];
    const tick = () => {
      const element = document.querySelector('.evidence-plane');
      if (element) {
        const box = element.getBoundingClientRect();
        store.readerFrames.push({ left: box.left, right: box.right, top: box.top, bottom: box.bottom });
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  await page.getByRole('button', { name: /why this decision/i }).click();
  await expect(page.getByRole('region', { name: 'Decision proof' })).toBeVisible();

  // Mid-entry frames: the paper must never reach the Inbox or the Rail on its way in.
  const entering = [
    await brightestInBands(page, gutters),
    await brightestInBands(page, gutters),
    await brightestInBands(page, gutters),
  ];
  await page.waitForTimeout(700);

  const [queue, rail, header, reader, frames, viewport] = await Promise.all([
    page.getByRole('complementary', { name: 'Opportunity inbox' }).boundingBox(),
    page.getByRole('complementary', { name: 'Workspace context' }).boundingBox(),
    page.locator('.workspace-header').boundingBox(),
    page.getByRole('region', { name: 'Decision proof' }).boundingBox(),
    page.evaluate(() => (window as unknown as { readerFrames: { left: number; right: number; top: number; bottom: number }[] }).readerFrames),
    page.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight })),
  ]);

  // Anchored to the real Decision + Why/Proof grid span, not to viewport percentages, and
  // filling the central host so no closed content can show above or below it. The host's tracks
  // are declared in judge-impact.css and the body grid's in base.css, so the span only lands on
  // the zone boundaries while the two resolve identically: that is asserted, not assumed.
  const tracks = await page.evaluate(() => ['.workspace-grid', '.evidence-host']
    .map(selector => getComputedStyle(document.querySelector(selector)!).gridTemplateColumns));
  expect(tracks[1]).toBe(tracks[0]);
  expect(reader!.x).toBeCloseTo(queue!.x + queue!.width, 0);
  expect(reader!.x + reader!.width).toBeCloseTo(rail!.x, 0);
  expect(reader!.y).toBeCloseTo(header!.y + header!.height, 0);
  expect(reader!.y + reader!.height).toBeCloseTo(viewport.height, 0);

  expect(frames.length).toBeGreaterThan(5);
  for (const frame of frames) {
    expect(frame.left).toBeGreaterThanOrEqual(queue!.x + queue!.width - 1);
    expect(frame.right).toBeLessThanOrEqual(rail!.x + 1);
    expect(frame.top).toBeGreaterThanOrEqual(header!.y + header!.height - 1);
    expect(frame.bottom).toBeLessThanOrEqual(viewport.height + 1);
  }

  // Painted proof: the gutters either side stay exactly as dark as they were before the reader
  // opened. The 16px / 10px opaque edge bars raised these to paper luminance.
  const settled = await brightestInBands(page, gutters);
  for (const [index, baseline] of closed.entries()) {
    for (const sample of [...entering, settled]) expect(sample[index]).toBeLessThanOrEqual(baseline + 6);
  }

  // No fragment of the closed central view survives around the reader.
  const fragments = await page.evaluate(({ reader }) => {
    const leaks: { selector: string; rect: Record<string, number> }[] = [];
    for (const selector of ['.canvas-topline', '.proof-context', '.section-rule.trace-heading', '.decision-trace', '.proof-trigger', '.recommendation-surface']) {
      for (const element of document.querySelectorAll(selector)) {
        const box = element.getBoundingClientRect();
        if (box.width === 0 && box.height === 0) continue;
        const onScreen = {
          top: Math.max(box.top, 0), bottom: Math.min(box.bottom, window.innerHeight),
          left: Math.max(box.left, 0), right: Math.min(box.right, window.innerWidth),
        };
        if (onScreen.bottom <= onScreen.top || onScreen.right <= onScreen.left) continue;
        const covered = onScreen.top >= reader.top - 0.5 && onScreen.bottom <= reader.bottom + 0.5
          && onScreen.left >= reader.left - 0.5 && onScreen.right <= reader.right + 0.5;
        if (!covered) leaks.push({ selector, rect: onScreen });
      }
    }
    return leaks;
  }, { reader: { top: reader!.y, bottom: reader!.y + reader!.height, left: reader!.x, right: reader!.x + reader!.width } });
  expect(fragments).toEqual([]);
});

test('the reader states its own subject and keeps one scrolling document', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 810 });
  await selectOpportunity(page);
  await page.getByRole('button', { name: /why this decision/i }).click();
  const reader = page.getByRole('region', { name: 'Decision proof' });
  await expect(reader).toBeVisible();

  // The context strip names the same selected opportunity and its recorded mode, and carries
  // the one Close proof control. Nothing is fetched for the strip alone.
  const strip = reader.locator('.evidence-plane-heading');
  await expect(strip).toContainText('AWS Agents for Humans');
  await expect(strip).toContainText('FIXTURE');
  await expect(strip).not.toContainText(/LIVE/);
  const close = reader.getByRole('button', { name: /close proof/i });
  await expect(close).toHaveCount(1);
  await expect(strip.getByRole('button', { name: /close proof/i })).toHaveCount(1);

  const citation = reader.getByRole('link', { name: /view original/i }).first();
  await expect(citation).toHaveAttribute('href', 'https://rules.aws-agents-for-humans.example/rules');
  await expect(reader.locator('blockquote').first()).not.toBeEmpty();

  // The first quotation and the source action it belongs to are readable without scrolling,
  // with real clearance from the reader's bottom edge.
  const documentRegion = reader.locator('.evidence-document');
  const [quote, link, paper] = await Promise.all([
    reader.locator('blockquote').first().boundingBox(),
    citation.boundingBox(),
    documentRegion.boundingBox(),
  ]);
  expect(quote!.y + quote!.height).toBeLessThan(paper!.y + paper!.height - 16);
  expect(link!.y + link!.height).toBeLessThan(paper!.y + paper!.height - 16);

  // One scroll region: the document scrolls, the reader shell does not, and the page never does.
  const scrolling = await page.evaluate(() => {
    const shell = document.querySelector('.evidence-plane')!;
    const paper = document.querySelector('.evidence-document')!;
    return {
      shellScrolls: shell.scrollHeight > shell.clientHeight + 1,
      paperScrolls: paper.scrollHeight > paper.clientHeight + 1,
      paperSideways: paper.scrollWidth > paper.clientWidth + 1,
    };
  });
  expect(scrolling).toEqual({ shellScrolls: false, paperScrolls: true, paperSideways: false });

  // Scrolled to the very end, the last recorded claim is inside the reader's own viewport, not
  // merely present in a box the document clips away, and Close proof is still there.
  await page.evaluate(() => { const paper = document.querySelector('.evidence-document')!; paper.scrollTop = paper.scrollHeight; });
  await expect(reader.getByRole('region', { name: 'Reward & Deadline' })).toBeInViewport();
  await expect(reader.getByText(/An unknown deadline is never read as open/i)).toBeInViewport();
  await expect(close).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollTop)).toBe(0);

  // Nothing the reader covers stays reachable by keyboard or screen reader, and the two zones
  // it deliberately leaves on screen stay operable: a bounded evidence mode, not a modal.
  const reachability = await page.evaluate(() => {
    const focusables = (zone: string) => [...document.querySelectorAll<HTMLElement>(
      `${zone} button:not(:disabled), ${zone} a[href], ${zone} input:not(:disabled), ${zone} [tabindex="0"]`)];
    const reachable = (elements: HTMLElement[]) => elements.filter(element => {
      element.focus();
      return document.activeElement === element;
    }).length;
    const coveredControls = [...focusables('.workspace-canvas'), ...focusables('.proof-context')];
    return {
      coveredControls: coveredControls.length,
      coveredReachable: reachable(coveredControls),
      inboxReachable: reachable(focusables('.workspace-queue')) > 0,
      railReachable: reachable(focusables('.workspace-rail')) > 0,
    };
  });
  expect(reachability.coveredControls).toBeGreaterThan(0);
  expect(reachability.coveredReachable).toBe(0);
  expect(reachability.inboxReachable).toBe(true);
  expect(reachability.railReachable).toBe(true);

  // Selection and keyboard operation survive the composition.
  await expect(documentRegion).toHaveCSS('user-select', /^(auto|text)$/);
  await close.focus();
  await expect(close).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('region', { name: 'Decision proof' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /why this decision/i })).toBeFocused();
  const afterClose = await brightestInBands(page, await sideGutters(page));
  for (const sample of afterClose) expect(sample).toBeLessThan(120);
});

test.describe('reduced motion', () => {
  test.use({ reducedMotion: 'reduce' });
  test('the reduced-motion reader lands in the same contained composition', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 810 });
    await selectOpportunity(page);
    const gutters = await sideGutters(page);
    const closed = await brightestInBands(page, gutters);
    await page.getByRole('button', { name: /why this decision/i }).click();
    const reader = page.getByRole('region', { name: 'Decision proof' });
    await expect(reader).toBeVisible();

    const [queue, rail, box, running] = await Promise.all([
      page.getByRole('complementary', { name: 'Opportunity inbox' }).boundingBox(),
      page.getByRole('complementary', { name: 'Workspace context' }).boundingBox(),
      reader.boundingBox(),
      reader.evaluate(element => [element, ...element.querySelectorAll('*')]
        .flatMap(node => node.getAnimations().map(animation => animation.playState))),
    ]);
    expect(running).toEqual([]);
    expect(box!.x).toBeCloseTo(queue!.x + queue!.width, 0);
    expect(box!.x + box!.width).toBeCloseTo(rail!.x, 0);

    // The entry keyframes start at opacity 0 and fill both. With animations disabled the reader
    // has to render at its natural state, not be frozen invisible: a bounding box alone would
    // not notice, so the painted state is asserted directly.
    const painted = await page.evaluate(() => ['.evidence-plane', '.evidence-document'].map(selector => {
      const style = getComputedStyle(document.querySelector(selector)!);
      return { selector, opacity: style.opacity, transform: style.transform };
    }));
    for (const layer of painted) {
      expect(layer.opacity, `${layer.selector} opacity`).toBe('1');
      expect(layer.transform, `${layer.selector} transform`).toBe('none');
    }
    await expect(reader.getByRole('link', { name: /view original/i }).first()).toBeVisible();
    const open = await brightestInBands(page, gutters);
    for (const [index, baseline] of closed.entries()) expect(open[index]).toBeLessThanOrEqual(baseline + 6);
  });
});

/* Horizontal scroll area the CLOSED workspace produces, measured at each width. It used to be
   1px at 1440 and 22px at 1280, both from `SUFFICIENT_CRITICAL_EVIDENCE` — one unbreakable token
   overflowing the narrowed Intelligence Rail as an inline run, which is why no element's own box
   ever exceeded the viewport. Presenting that reason as copy removed it at every width, so the
   maxima are now zero and any return of the defect fails here. */
const FROZEN_CLOSED_OVERFLOW: Record<number, number> = { 1440: 0, 1280: 0, 1024: 0, 768: 0, 320: 0 };

test('the reader stays inside every supported width without horizontal overflow', async ({ page }) => {
  for (const width of [1440, 1280, 1024, 768, 320]) {
    await page.setViewportSize({ width, height: 810 });
    await page.goto('/inbox');
    await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();

    // What this asserts is that opening the reader adds nothing to the scroll area the closed
    // workspace already has, and that the closed workspace has not got worse either.
    const closedOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

    // Watch the document's scroll area across the whole entry. Below 1280 the accepted
    // projection still slides the proof plane in from the right viewport edge, so its box is
    // briefly past that edge; because the plane is viewport-fixed there, the scroll area must
    // not grow at any frame. That, not a mid-transition box, is what horizontal overflow means.
    await page.evaluate(() => {
      const store = window as unknown as { entryScroll: number[] };
      store.entryScroll = [];
      const tick = () => {
        store.entryScroll.push(document.documentElement.scrollWidth - window.innerWidth);
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });

    await page.getByRole('button', { name: /why this decision/i }).click();
    const reader = page.getByRole('region', { name: 'Decision proof' });
    await expect(reader).toBeVisible();
    await expect(reader.getByRole('button', { name: /close proof/i })).toBeVisible();
    // Settled projection: the entry containment the integrated reader owns is asserted in full,
    // frame by frame, in the judge-viewport test above.
    await reader.evaluate(element => Promise.all([element, ...element.querySelectorAll('*')]
      .flatMap(node => node.getAnimations().map(animation => animation.finished.catch(() => {})))));

    const measured = await page.evaluate(() => {
      const shell = document.querySelector('.evidence-plane') as HTMLElement;
      const paper = (document.querySelector('.evidence-document') ?? shell) as HTMLElement;
      const box = shell.getBoundingClientRect();
      return {
        pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
        readerOverflow: Math.max(0, Math.round(box.right - window.innerWidth)) + Math.max(0, Math.round(-box.left)),
        paperSideways: paper.scrollWidth - paper.clientWidth,
        railVisible: document.querySelector('.workspace-rail')!.checkVisibility(),
        entryOverflow: Math.max(...(window as unknown as { entryScroll: number[] }).entryScroll),
        entryFrames: (window as unknown as { entryScroll: number[] }).entryScroll.length,
      };
    });
    expect(closedOverflow, `closed overflow at ${width}`).toBeLessThanOrEqual(FROZEN_CLOSED_OVERFLOW[width]);
    expect(measured.entryFrames, `sampled entry frames at ${width}`).toBeGreaterThan(5);
    expect(measured.entryOverflow, `overflow during entry at ${width}`).toBeLessThanOrEqual(Math.max(0, closedOverflow));
    expect(measured.pageOverflow, `page overflow at ${width}`).toBeLessThanOrEqual(Math.max(0, closedOverflow));
    expect(measured.readerOverflow, `reader overflow at ${width}`).toBe(0);
    expect(measured.paperSideways, `document sideways overflow at ${width}`).toBeLessThanOrEqual(0);
    // The frozen responsive contract: a persistent desktop Rail at 1280 and above, a contextual
    // Rail that stays closed in the 768-1279 projection, and a stacked Rail in the narrow flow.
    expect(measured.railVisible, `rail visibility at ${width}`).toBe(width >= 1280 || width < 768);
  }
});

/* --------------------------------------------------------------------------------------------
 * Wide workspace cohesion.
 *
 * Three defects the owner could see and no existing assertion could: the four causal signals
 * rendered flush against each other, every connector started up to 44px away from the lane tip
 * it belongs to, and the Intelligence Rail ran past the viewport so its last section was sliced
 * by the window edge. All three are geometry, so all three are measured here.
 * ------------------------------------------------------------------------------------------ */

/** The lane's visible shape is a stretched background SVG whose arrow tip sits at 339/340 of the
 *  lane width and 29.5/60 of its height. That tip, not the box edge, is what a connector meets. */
async function decisionFieldGeometry(page: Page) {
  return page.evaluate(() => {
    const round = (n: number) => Math.round(n * 100) / 100;
    const lanes = [...document.querySelectorAll('.signal-lane')].map(lane => {
      const r = lane.getBoundingClientRect();
      return {
        label: lane.querySelector('dt')?.textContent ?? '',
        y: r.y, bottom: r.bottom, height: r.height,
        tip: { x: r.x + r.width * (339 / 340), y: r.y + r.height * (29.5 / 60) },
      };
    });
    const svg = document.querySelector('.decision-convergence') as SVGSVGElement | null;
    const ctm = svg?.getScreenCTM() ?? null;
    const sources = ctm
      ? [...svg!.querySelectorAll('path')].slice(0, 4).map(path => {
        const point = path.getPointAtLength(0).matrixTransform(ctm);
        return { x: point.x, y: point.y };
      })
      : [];
    return {
      laneHeights: lanes.map(lane => round(lane.height)),
      gaps: lanes.slice(1).map((lane, index) => round(lane.y - lanes[index].bottom)),
      attachment: sources.map((source, index) => ({
        lane: lanes[index].label,
        dx: round(source.x - lanes[index].tip.x),
        dy: round(source.y - lanes[index].tip.y),
        distance: round(Math.hypot(source.x - lanes[index].tip.x, source.y - lanes[index].tip.y)),
      })),
      signatureWidth: round(document.querySelector('.decision-signature')!.getBoundingClientRect().width),
      connectorEnd: (() => {
        if (!ctm) return { x: 0, y: 0 };
        const path = svg!.querySelectorAll('path')[0];
        const point = path.getPointAtLength(path.getTotalLength()).matrixTransform(ctm);
        return { x: round(point.x), y: round(point.y) };
      })(),
      recommendation: (() => {
        const r = document.querySelector('.recommendation-surface')!.getBoundingClientRect();
        return { x: round(r.x), width: round(r.width), height: round(r.height) };
      })(),
    };
  });
}

test('the four causal signals read as a rhythm and every connector meets its lane', async ({ page }) => {
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 810 });
    await page.goto('/inbox');
    await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);

    const field = await decisionFieldGeometry(page);

    // The lane height the connector overlay is derived from. If base.css ever changes it, the
    // overlay arithmetic has to be revisited rather than silently drifting.
    expect(field.laneHeights, `lane heights at ${width}`).toEqual([62, 62, 62, 62]);

    // Deliberate separation, not a stack and not four floating cards.
    expect(field.gaps, `signal gaps at ${width}`).toHaveLength(3);
    for (const gap of field.gaps) {
      expect(gap, `signal gap at ${width}`).toBeGreaterThanOrEqual(8);
      expect(gap, `signal gap at ${width}`).toBeLessThanOrEqual(13);
    }
    expect(Math.max(...field.gaps) - Math.min(...field.gaps), `gap evenness at ${width}`).toBeLessThanOrEqual(1);

    // Every connector's first painted point sits on the tip of the lane it continues. The
    // defect measured up to 44px of vertical drift, worst at the outer lanes.
    expect(field.attachment, `connector count at ${width}`).toHaveLength(4);
    for (const anchor of field.attachment) {
      expect(Math.abs(anchor.dy), `${anchor.lane} connector dy at ${width}`).toBeLessThanOrEqual(2);
      expect(anchor.distance, `${anchor.lane} connector distance at ${width}`).toBeLessThanOrEqual(2.5);
    }

    // The lane stack grew inside the existing field rather than pushing the recommendation:
    // the surface still starts where the connectors end, so the composition kept its footprint.
    expect(field.recommendation.x, `recommendation left at ${width}`)
      .toBeGreaterThanOrEqual(field.connectorEnd.x - 2);
  }
});

test('the Intelligence Rail finishes inside its own panel rather than at the window edge', async ({ page }) => {
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 810 });
    await page.goto('/inbox');
    await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();

    const rail = page.getByRole('complementary', { name: 'Workspace context' });
    const measured = await rail.evaluate(element => {
      const style = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      const sections = [...element.querySelectorAll<HTMLElement>('.rail-section')];
      const last = sections.at(-1)!;
      return {
        overflowY: style.overflowY,
        // The wheel has to hand back to the document at the panel's end: the page scrolls too.
        overscroll: style.overscrollBehaviorY,
        tabIndex: element.tabIndex,
        scrolls: element.scrollHeight > element.clientHeight + 1,
        bottom: box.bottom,
        viewportHeight: window.innerHeight,
        // Breathing room under the last section inside the panel's own scrollable content. It
        // has to clear the fade, or the fade lands on the final line instead of on the padding.
        contentBottomGap: element.scrollHeight - (last.offsetTop + last.offsetHeight),
        fade: /calc\((?:100% - )?(\d+)px\)/.exec(style.maskImage || '')?.[1] ?? null,
        sideways: element.scrollWidth - element.clientWidth,
      };
    });

    // One intentional rail scroll region: the panel ends at the viewport, not past it. The
    // mechanism may be `auto` or `scroll`; what matters is that it scrolls and stays inside.
    expect(measured.overflowY, `rail overflow at ${width}`).toMatch(/^(auto|scroll)$/);
    expect(measured.scrolls, `rail scrolls at ${width}`).toBe(true);
    expect(measured.bottom, `rail bottom at ${width}`).toBeLessThanOrEqual(measured.viewportHeight + 1);
    expect(measured.sideways, `rail sideways overflow at ${width}`).toBeLessThanOrEqual(0);
    // A pointer-only scroll region is a keyboard dead end, and trapping the wheel at its end
    // strands a reader whose cursor happens to be over the rail.
    expect(measured.tabIndex, `rail is keyboard reachable at ${width}`).toBe(0);
    expect(measured.overscroll, `rail overscroll at ${width}`).toBe('auto');
    // Deliberate breathing room under the last section, deeper than the fade it has to clear.
    expect(Number(measured.fade), `rail fade length at ${width}`).toBeGreaterThan(0);
    expect(measured.contentBottomGap, `rail bottom clearance at ${width}`)
      .toBeGreaterThanOrEqual(Number(measured.fade));

    // Scrolled to its end the footer is whole, not merely partly on screen: ratio 1, because a
    // line sliced by the panel edge is exactly the defect and would satisfy the default.
    await rail.evaluate(element => { element.scrollTop = element.scrollHeight; });
    await expect(rail.getByRole('link', { name: /view activity/i })).toBeInViewport({ ratio: 1 });
    // And the section the owner marked is reachable and whole on the way there.
    await rail.evaluate(element => {
      element.querySelector('.rail-section:nth-of-type(2)')?.scrollIntoView({ block: 'center' });
    });
    await expect(rail.getByText('Local controller connected')).toBeInViewport({ ratio: 1 });
    await expect(rail.getByText(/A local connection does not indicate LIVE research/i)).toBeInViewport({ ratio: 1 });
    // The page itself never scrolled sideways to achieve any of this.
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  }
});
