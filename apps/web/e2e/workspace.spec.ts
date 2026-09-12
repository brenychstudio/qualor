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

    // Every connector runs out of the lane it continues, on that lane's own centreline. The
    // defect measured up to 44px of vertical drift, worst at the outer lanes.
    expect(field.attachment, `connector count at ${width}`).toHaveLength(4);
    for (const anchor of field.attachment) {
      expect(Math.abs(anchor.dy), `${anchor.lane} connector dy at ${width}`).toBeLessThanOrEqual(2);
      // The path begins behind the lane's tip, not at it: it is painted over the lane and
      // ramps up from nothing across the handoff, so its first point is deliberately hidden
      // and a start that fell short of the tip would be the seam this replaced. Bounded on
      // the other side too — far enough in and it would paint a hairline across the body
      // before the ramp reaches it. Where the line actually becomes visible is a question
      // about pixels, and the junction test measures it there.
      expect(anchor.dx, `${anchor.lane} connector starts inside its lane at ${width}`).toBeLessThanOrEqual(0);
      expect(anchor.dx, `${anchor.lane} connector start depth at ${width}`).toBeGreaterThanOrEqual(-26);
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

/* --------------------------------------------------------------------------------------------
 * Responsive integrity.
 *
 * Two invariants, both measured rather than eyeballed. A recorded value must stay inside the
 * lane that owns it and out of the corridor its connector runs in — at 768 and 1024 the value
 * column was 65px wide, so the recorded project name wrapped to four lines and broke out of its
 * own 62px lane. And the Intelligence Rail's first screen must end on something deliberate: a
 * section that begins crisply and is then cut by the panel edge reads as broken, whatever the
 * content underneath is doing.
 * ------------------------------------------------------------------------------------------ */

/** Lane regions, the connector corridor beside each lane, and whether either escapes the other.
 *  Corridor points come from the rendered path through the SVG's screen CTM: at 768 the painted
 *  connector is the mobile bracket, whose return leg runs far to the left of the lane stack, so
 *  a single leftmost-x would be a corridor that does not exist. */
async function laneIntegrity(page: Page) {
  return page.evaluate(() => {
    const r2 = (n: number) => Math.round(n * 100) / 100;
    const visible = (el: Element | null) => el && getComputedStyle(el).display !== 'none' ? el as SVGSVGElement : null;
    const svg = visible(document.querySelector('.decision-convergence'))
      ?? visible(document.querySelector('.mobile-convergence'));
    const ctm = svg?.getScreenCTM() ?? null;
    const stroke = svg ? parseFloat(getComputedStyle(svg).strokeWidth) || 1 : 0;
    const samples: { x: number; y: number }[] = [];
    if (ctm && svg) {
      for (const path of svg.querySelectorAll('path')) {
        const total = path.getTotalLength();
        for (let i = 0; i <= 60; i++) {
          const p = path.getPointAtLength((total * i) / 60).matrixTransform(ctm);
          samples.push({ x: p.x, y: p.y });
        }
      }
    }
    return [...document.querySelectorAll('.signal-lane')].map(lane => {
      const laneBox = lane.getBoundingClientRect();
      const value = lane.querySelector('dd strong')!;
      const valueBox = value.getBoundingClientRect();
      const range = document.createRange();
      range.selectNodeContents(value);
      const lines = new Set([...range.getClientRects()].map(line => Math.round(line.top))).size;
      const beside = samples.filter(s => s.y >= valueBox.top - 1 && s.y <= valueBox.bottom + 1).map(s => s.x);
      const corridorLeft = beside.length ? Math.min(...beside) - stroke / 2 : null;
      return {
        label: lane.querySelector('dt')?.textContent ?? '',
        lines,
        // How far the value's painted box escapes the lane that owns it.
        escapesTop: r2(laneBox.top - valueBox.top),
        escapesBottom: r2(valueBox.bottom - laneBox.bottom),
        escapesRight: r2(valueBox.right - laneBox.right),
        corridorLeft: corridorLeft === null ? null : r2(corridorLeft),
        valueToCorridor: corridorLeft === null ? null : r2(corridorLeft - valueBox.right),
        // Any sampled connector point painted inside the value's own box.
        pathInsideValue: samples.filter(s =>
          s.x >= valueBox.left - stroke && s.x <= valueBox.right + stroke
          && s.y >= valueBox.top - stroke && s.y <= valueBox.bottom + stroke).length,
      };
    });
  });
}

async function selectW01(page: Page, width: number) {
  await page.setViewportSize({ width, height: 810 });
  await page.goto('/inbox');
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

test('a recorded value stays inside its lane and out of the connector corridor at every width', async ({ page }) => {
  // 901 is the narrowest lane in the 768-1279 band, not 768: below 901 the signature stacks and
  // the lanes go nearly full width. 320 is outside this fix but monitored, so a value that grew
  // long enough to break out of the narrow lane fails here instead of being discovered visually.
  for (const width of [1440, 1280, 1024, 901, 768, 320]) {
    await selectW01(page, width);
    const lanes = await laneIntegrity(page);
    expect(lanes, `lane count at ${width}`).toHaveLength(4);
    expect(lanes.some(lane => lane.corridorLeft !== null), `connector sampled beside a lane at ${width}`).toBe(true);
    for (const lane of lanes) {
      // The value is painted inside the lane that owns it. At 768 and 1024 the longest recorded
      // project name wrapped to four lines and its box ran past the lane's bottom edge.
      expect(lane.escapesTop, `${lane.label} escapes lane top at ${width}`).toBeLessThanOrEqual(0);
      expect(lane.escapesBottom, `${lane.label} escapes lane bottom at ${width}`).toBeLessThanOrEqual(0);
      expect(lane.escapesRight, `${lane.label} escapes lane right at ${width}`).toBeLessThanOrEqual(0);
      // The lane reserves the corridor with its own right padding, so this holds whatever the
      // value says; what it guards is that the reservation is still there and still clears the
      // connector the SVG actually paints beside this lane.
      if (lane.corridorLeft !== null) {
        expect(lane.valueToCorridor, `${lane.label} value to corridor at ${width}`).toBeGreaterThan(0);
      }
      expect(lane.pathInsideValue, `${lane.label} path inside value at ${width}`).toBe(0);
    }
  }
});

test('the accepted wide Decision Field geometry holds around the signal-lane correction', async ({ page }) => {
  // 1440 and 1280 are regression anchors for the frame the lane sits in: the lane stack's own
  // width and rhythm, and where the hero begins. The value column is inside that frame and is
  // re-accepted here — it was a fixed 83px, which is what put the recorded name in the
  // arrowhead; it is now the lane's own proportional share, or the slot's floor where an even
  // share would be narrower than a compact value needs — which is what 1280 resolves to. The
  // floor is what is left after the label's eyebrow, which must not wrap: at 96px it did, and
  // the two-line label block then escaped its own lane and shifted the icon off centre.
  for (const [width, expected] of [[1440, { lane: 320.63, value: 99.75 }], [1280, { lane: 282.23, value: 91 }]] as const) {
    await selectW01(page, width);
    const measured = await page.evaluate(() => {
      const r2 = (n: number) => Math.round(n * 100) / 100;
      const lanes = [...document.querySelectorAll('.signal-lane')];
      const boxes = lanes.map(lane => lane.getBoundingClientRect());
      const columns = getComputedStyle(lanes[0]).gridTemplateColumns.split(' ').map(parseFloat);
      const rect = (selector: string) => {
        const box = document.querySelector(selector)!.getBoundingClientRect();
        return { x: r2(box.x), y: r2(box.y), w: r2(box.width) };
      };
      const svg = document.querySelector('.decision-convergence') as SVGSVGElement;
      const ctm = svg.getScreenCTM()!;
      const first = svg.querySelectorAll('path')[0];
      return {
        laneWidth: r2(boxes[0].width),
        valueColumn: r2(columns.at(-1)!),
        gaps: boxes.slice(1).map((box, index) => r2(box.top - boxes[index].bottom)),
        recommendation: rect('.recommendation-surface'),
        connectorEnd: r2(first.getPointAtLength(first.getTotalLength()).matrixTransform(ctm).x),
      };
    });
    // Pinned measurements, deliberately: a change to the canvas padding or the body track
    // ratios should fail here and be re-accepted rather than pass unnoticed.
    expect(measured.laneWidth, `lane width at ${width}`).toBeCloseTo(expected.lane, 0);
    expect(measured.valueColumn, `value column at ${width}`).toBeCloseTo(expected.value, 0);
    for (const gap of measured.gaps) expect(gap, `signal gap at ${width}`).toBeCloseTo(10, 1);
    // The recommendation still starts where the connectors end, so the medium correction did
    // not move the hero. Its right edge is the canvas edge by construction, so that is not
    // worth asserting; where it begins is.
    expect(measured.recommendation.x, `recommendation left at ${width}`)
      .toBeGreaterThanOrEqual(measured.connectorEnd - 2);
  }
});


/* Where the panel's edge falls relative to a section boundary is a function of the window's
 * height and of how much text the rail wraps at that width, so no spacing value can place it —
 * measured, a section boundary lands past the fade at 1280 and 1440 x 810 and at 1366 x 768 but
 * not at 1440 x 900, and at 1440 x 700 the Activity section is taller than the panel and must be
 * cut. What the layer does guarantee, and what the owner actually reported, is that no line of
 * recorded text is ever guillotined: the fade is deeper than any line the rail renders, so a
 * line can only cross the panel edge from inside the fade. That is asserted across the whole
 * size matrix rather than at the width it was tuned for. */
const RAIL_SIZES = [
  [1920, 810], [1600, 810], [1440, 810], [1366, 768], [1280, 810],
  [1440, 1080], [1440, 900], [1440, 700], [1280, 660],
] as const;

test('no recorded line is ever cut while it is still crisply painted', async ({ page }) => {
  for (const [width, height] of RAIL_SIZES) {
    await page.setViewportSize({ width, height });
    await page.goto('/inbox');
    await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);

    const rail = page.getByRole('complementary', { name: 'Workspace context' });
    const fold = await rail.evaluate(element => {
      const panel = element.getBoundingClientRect();
      const fadeLength = Number(/calc\(100% - (\d+)px\)/.exec(getComputedStyle(element).maskImage || '')?.[1] ?? 0);
      const foldStart = panel.bottom - fadeLength;
      const cut: { text: string; top: number }[] = [];
      let tallestLine = 0;
      // Real line boxes, from a Range over each text node: getClientRects() on a block element
      // returns its border box, which would report a wrapped paragraph as one very tall "line".
      for (const node of element.querySelectorAll('h3, p, dt, dd, b, span, a, time')) {
        if (!node.textContent?.trim() || node.children.length) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        for (const line of range.getClientRects()) {
          if (line.height === 0) continue;
          tallestLine = Math.max(tallestLine, line.height);
          // Crossing the panel edge while still above the point the fade begins.
          if (line.top < panel.bottom - 0.5 && line.bottom > panel.bottom + 0.5 && line.top < foldStart - 0.5) {
            cut.push({ text: node.textContent.trim().slice(0, 40), top: Math.round(line.top) });
          }
        }
      }
      return { fadeLength, scrollTop: element.scrollTop, tallestLine: Math.round(tallestLine), cut };
    });

    expect(fold.scrollTop, `rail starts at the top at ${width}x${height}`).toBe(0);
    // The guarantee rests on the fade outreaching a line, so that relation is asserted too.
    expect(fold.fadeLength, `fade clears the tallest line at ${width}x${height}`)
      .toBeGreaterThan(fold.tallestLine);
    expect(fold.cut, `crisply cut lines at ${width}x${height}`).toEqual([]);
  }
});

test('no supported width scrolls the document sideways', async ({ page }) => {
  for (const width of [1440, 1280, 1024, 901, 768, 320]) {
    await page.setViewportSize({ width, height: 810 });
    await page.goto('/inbox');
    await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'APPLY' })).toBeVisible();
    // clientWidth, not innerWidth: innerWidth includes a classic scrollbar and would hide a
    // real overflow of up to its width.
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `horizontal overflow at ${width}`).toBeLessThanOrEqual(0);
  }
});

/* --------------------------------------------------------------------------------------------
 * Signal-lane text integrity.
 *
 * The invariant above — a value box that does not intersect the connector path — is necessary
 * and was not sufficient, because it measures against `lane.getBoundingClientRect()`. A lane's
 * border box runs to the tip of its arrowhead, so text can sit deep inside the taper, touch
 * nothing, and still read as crushed against the point. Measured at HEAD the recorded project
 * name overran the taper by 34.67px at 1440, 26.99 at 1280, 19.8 at 1024 and 66.88 at 768.
 *
 * What follows models the shape the lane actually paints. `.signal-lane::before` is an SVG
 * background on a 340x60 viewBox with `preserveAspectRatio='none'`, stretched to the border box:
 * the body's top edge runs flat to x=272 and then a cubic carries it to the tip at (339, 29.5),
 * with the bottom edge mirrored. So the rightmost x a lane can hold depends on how tall the
 * text is — a single line has most of the taper available, a three-line block almost none. The
 * boundary is solved per line box from that cubic rather than approximated by a percentage,
 * which is what makes this fail when text is moved into the taper without touching a connector.
 * ------------------------------------------------------------------------------------------ */

/** The lane's painted right boundary at each value line, and how far the text clears it. */
async function taperIntegrity(page: Page) {
  return page.evaluate(() => {
    const r2 = (n: number) => Math.round(n * 100) / 100;
    // The `::before` path, in its own viewBox units. Kept beside the stylesheet's copy: if the
    // shape is ever redrawn this model has to be redrawn with it, and the numbers below say so.
    const VB_W = 340, VB_H = 60, BODY_END = 272, TIP_X = 339, TIP_Y = 29.5;
    const P = [{ x: BODY_END, y: 0.5 }, { x: 303, y: 0.5 }, { x: 306, y: TIP_Y }, { x: TIP_X, y: TIP_Y }];
    const at = (k: 'x' | 'y', t: number) => {
      const u = 1 - t;
      return u * u * u * P[0][k] + 3 * u * u * t * P[1][k] + 3 * u * t * t * P[2][k] + t * t * t * P[3][k];
    };
    /** Rightmost x, in viewBox units, at which the shape still spans the given y. */
    const boundaryAt = (y: number) => {
      const top = Math.min(y, VB_H - y);          // mirrored about the tip's centreline
      if (top <= P[0].y) return BODY_END;          // above the body's top edge: nothing is painted
      if (top >= TIP_Y) return TIP_X;              // on the centreline the shape reaches the tip
      let lo = 0, hi = 1;                          // y(t) is monotonic over this segment
      for (let i = 0; i < 60; i++) {
        const mid = (lo + hi) / 2;
        if (at('y', mid) < top) lo = mid; else hi = mid;
      }
      return at('x', (lo + hi) / 2);
    };
    return [...document.querySelectorAll('.signal-lane')].map(lane => {
      const box = lane.getBoundingClientRect();
      const toScreenX = (vx: number) => box.left + (vx / VB_W) * box.width;
      const toViewY = (sy: number) => ((sy - box.top) / box.height) * VB_H;
      const value = lane.querySelector('dd strong')!;
      const range = document.createRange();
      range.selectNodeContents(value);
      const lines = [...range.getClientRects()].filter(line => line.width > 0);
      // Every line is checked against the boundary at its own top and bottom, so a tall block is
      // held to a stricter limit than a short one — which is how the shape actually behaves.
      const clearances = lines.map(line => Math.min(
        toScreenX(boundaryAt(toViewY(line.top))) - line.right,
        toScreenX(boundaryAt(toViewY(line.bottom))) - line.right));

      // Word integrity: a source word must paint as one contiguous run, never split mid-word.
      const node = value.firstChild;
      const fragmented: string[] = [];
      if (node && node.nodeType === Node.TEXT_NODE) {
        for (const match of (node.textContent ?? '').matchAll(/\S+/g)) {
          const word = document.createRange();
          word.setStart(node, match.index!);
          word.setEnd(node, match.index! + match[0].length);
          if ([...word.getClientRects()].filter(r => r.width > 0).length > 1) fragmented.push(match[0]);
        }
      }
      const meaning = lane.querySelector('.signal-meaning')!;
      // The rule underlines the value, so it is held to the same boundary, solved at its own
      // height — which is below the centreline, where the shape has already begun to narrow.
      const rule = lane.querySelector('.signal-rule')!.getBoundingClientRect();
      const widest = Math.max(...lines.map(line => line.width));
      return {
        label: lane.querySelector('dt')?.textContent ?? '',
        clearance: r2(Math.min(...clearances)),
        ruleClearance: r2(Math.min(
          toScreenX(boundaryAt(toViewY(rule.top))) - rule.right,
          toScreenX(boundaryAt(toViewY(rule.bottom))) - rule.right)),
        ruleEscapesTop: r2(box.top - rule.top),
        ruleEscapesBottom: r2(rule.bottom - box.bottom),
        ruleWiderThanValue: r2(rule.width - widest),
        lineCount: lines.length,
        fragmented,
        // The label keeps its own side of the lane: the value never starts inside it.
        labelOverlap: r2(meaning.getBoundingClientRect().right - Math.min(...lines.map(l => l.left))),
        escapesTop: r2(box.top - Math.min(...lines.map(l => l.top))),
        escapesBottom: r2(Math.max(...lines.map(l => l.bottom)) - box.bottom),
      };
    });
  });
}

// One optical unit of air between the last painted glyph and the shape's edge. The lane's own
// column gap is 8-9px, so this is the same rhythm the lane already spaces its regions with.
const TAPER_SAFE_GAP = 8;

test('a recorded value keeps clear of the lane it is painted in, taper included', async ({ page }) => {
  // 901 is in the list for the same reason it is in the test above: it is the narrowest lane
  // the layout ever produces — the signature still splits at 48% there but the canvas has
  // nearly closed — so it is the width where a proportional reservation is under most pressure.
  for (const width of [1440, 1280, 1024, 901, 768]) {
    await selectW01(page, width);
    const lanes = await taperIntegrity(page);
    expect(lanes, `lane count at ${width}`).toHaveLength(4);
    for (const lane of lanes) {
      // The defect the owner could see: text sitting inside the arrowhead. Negative clearance
      // means the glyphs are painted past the edge the shape still has at their own height.
      expect(lane.clearance, `${lane.label} clears the taper at ${width}`)
        .toBeGreaterThanOrEqual(TAPER_SAFE_GAP);
      // An ordinary word never breaks mid-word; it may wrap at spaces onto as many lines as it
      // needs, so the line count is deliberately not asserted.
      expect(lane.fragmented, `${lane.label} keeps whole words at ${width}`).toEqual([]);
      expect(lane.labelOverlap, `${lane.label} value clears its label at ${width}`).toBeLessThanOrEqual(0);
      expect(lane.escapesTop, `${lane.label} escapes lane top at ${width}`).toBeLessThanOrEqual(0);
      expect(lane.escapesBottom, `${lane.label} escapes lane bottom at ${width}`).toBeLessThanOrEqual(0);
    }
  }
});

/* --------------------------------------------------------------------------------------------
 * The causal junction, and the value block that hangs off it.
 *
 * Three defects that survived every geometry assertion so far because none of them is about a
 * box. Measured at HEAD:
 *
 *   1. A one-pixel dark column between each lane and its connector. The lane's shape is a
 *      340-unit viewBox whose tip is drawn at x=339, so it stops 1/340 of the lane's width
 *      short of its own border box; the connector's viewBox starts its paths at x=480 of 1000,
 *      which is exactly 48% — the lane stack's border-box right edge. The two are a shade under
 *      1px apart at 1440 and the background shows through: luminance runs 206, 85, 187 across
 *      the junction at 1440 and 201, 23, 145 at 1024. Both endpoints are "correct" on their own
 *      terms and the seam is still there, which is why this is measured in pixels.
 *   2. The value's rule is painted outside the lane it belongs to. A three-line value plus its
 *      9px gap and 1px rule is taller than the lane's 50px content box, and the rule is the
 *      part that ends up over the edge: it sits at y=373 in a lane whose border box ends at
 *      371.44 at 1440, reading as an orphan stroke under the lane rather than an underline.
 *   3. The rule is a flat 52px whatever it underlines, so it is wider than PASS and narrower
 *      than the recorded project name — attached to nothing in particular.
 * ------------------------------------------------------------------------------------------ */

/** Luminance sampled along each connector, across its lane's tip and then along plain curve.
 *
 *  Along the curve rather than along a scanline: a 1px stroke at a shallow angle is antialiased
 *  across two rows, so its brightness swings by 70 levels over its own length, and a horizontal
 *  scan of a steeply descending connector spends half its samples on the background between
 *  curve segments. Following the path keeps the line centred in every sample, which is what
 *  makes the control run a usable unit of comparison.
 */
async function junctionProfiles(page: Page) {
  const geometry = await page.evaluate(() => {
    const svg = document.querySelector('.decision-convergence') as SVGSVGElement;
    const ctm = svg.getScreenCTM()!;
    return [...document.querySelectorAll('.signal-lane')].map((lane, index) => {
      const box = lane.getBoundingClientRect();
      const path = svg.querySelectorAll('path')[index];
      const total = path.getTotalLength();
      const points: { x: number; y: number }[] = [];
      for (let at = 0; at <= total; at += 0.5) {
        const point = path.getPointAtLength(at).matrixTransform(ctm);
        points.push({ x: point.x, y: point.y });
      }
      return {
        label: lane.querySelector('dt')?.textContent ?? '',
        // The handoff is at the lane's tip, wherever the connector's path begins: the path now
        // starts inside the lane and is painted over it, so its start is not a visible event.
        tipX: box.left + (339 / 340) * box.width,
        points,
      };
    });
  });
  const frame = (await page.screenshot()).toString('base64');
  return page.evaluate(async ({ frame, geometry }) => {
    const image = new Image();
    image.src = `data:image/png;base64,${frame}`;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext('2d')!;
    context.drawImage(image, 0, 0);
    const brightest = (x: number, y: number) => {
      const { data } = context.getImageData(Math.round(x), Math.round(y) - 2, 1, 5);
      let best = 0;
      for (let i = 0; i < data.length; i += 4) {
        const luminance = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
        if (luminance > best) best = luminance;
      }
      return Math.round(best);
    };
    const along = (points: { x: number; y: number }[], from: number, to: number) => {
      const values: number[] = [];
      let previous = Number.NaN;
      for (const point of points) {
        if (point.x < from || point.x > to || Math.round(point.x) === previous) continue;
        previous = Math.round(point.x);
        values.push(brightest(point.x, point.y));
      }
      let step = 0;
      for (let i = 1; i < values.length; i++) step = Math.max(step, Math.abs(values[i] - values[i - 1]));
      return { darkest: Math.min(...values), step };
    };
    return geometry.map(lane => ({
      label: lane.label,
      junction: along(lane.points, lane.tipX - 6, lane.tipX + 6),
      control: along(lane.points, lane.tipX + 8, lane.tipX + 34),
    }));
  }, { frame, geometry });
}

test('every signal meets its connector as one continuous painted line', async ({ page }) => {
  // Reduced motion so the frame is the settled one: the canvas has a 420ms entrance, and a
  // frame caught inside it moves these numbers by enough to make the comparison meaningless.
  await page.emulateMedia({ reducedMotion: 'reduce' });
  // 768 is excluded deliberately: below 901 base.css paints the mobile bracket instead and the
  // lane's tip is the end of the drawing, so there is no handoff to measure.
  for (const width of [1440, 1280, 1024]) {
    await selectW01(page, width);
    await page.waitForTimeout(400);
    const junctions = await junctionProfiles(page);
    expect(junctions, `junction count at ${width}`).toHaveLength(4);
    for (const { label, junction, control } of junctions) {
      // Nothing across the handoff is darker than the connector's own darkest pixel: a
      // background-coloured column between two painted ends fails here.
      expect(junction.darkest, `${label} junction is unbroken at ${width}`)
        .toBeGreaterThanOrEqual(0.8 * control.darkest);
      // And nothing across it changes faster than the line changes anyway. A flat cap or a
      // merged bar ending in one is a step the line never takes on its own: measured against
      // the HEAD this replaced, the ratio asserted below reached 1.87 on six of the twelve
      // lane/width pairs and reaches 0.81 at worst now.
      expect(junction.step, `${label} junction has no painted endpoint at ${width}`)
        .toBeLessThanOrEqual(control.step);
    }
  }
});

test('the compact lane shows a readable label and still tells the truth about the project',
  async ({ page }) => {
    for (const width of [1440, 1280, 1024, 768]) {
      await selectW01(page, width);
      const value = page.locator('.signal-lane').first().locator('dd strong');
      // The lane carries a label sized for the lane.
      await expect(value, `lane label at ${width}`).toHaveText('Synthetic demo');
      // And the full recorded project name is never lost: it is on the value itself, and the
      // queue card beside it still shows it in full.
      await expect(value, `full project name on the value at ${width}`)
        .toHaveAttribute('title', 'Synthetic Eligibility Demonstrator');
      await expect(page.locator('.workspace-queue').getByText('Synthetic Eligibility Demonstrator'),
        `full project name in the queue at ${width}`).toBeVisible();
    }
  });

test('a value rule underlines its own value, inside the lane', async ({ page }) => {
  for (const width of [1440, 1280, 1024, 901, 768]) {
    await selectW01(page, width);
    for (const lane of await taperIntegrity(page)) {
      // Inside the lane it belongs to, rather than an orphan stroke painted under it: a
      // three-line value used to push the rule to y=373 in a lane ending at 371.44 at 1440.
      expect(lane.ruleEscapesTop, `${lane.label} rule escapes lane top at ${width}`).toBeLessThanOrEqual(0);
      expect(lane.ruleEscapesBottom, `${lane.label} rule escapes lane bottom at ${width}`).toBeLessThanOrEqual(0);
      // Clear of the shape's edge at the rule's own height, the same way the text is.
      expect(lane.ruleClearance, `${lane.label} rule clears the taper at ${width}`)
        .toBeGreaterThanOrEqual(TAPER_SAFE_GAP);
      // It underlines the value rather than running past it. A wrapped value is the exception
      // the rule cannot follow: its box is the track, not the widest line it happens to paint.
      if (lane.lineCount === 1) {
        expect(lane.ruleWiderThanValue, `${lane.label} rule is wider than its value at ${width}`)
          .toBeLessThanOrEqual(0.5);
      }
    }
  }
});

/** Every lane holds what it is given, and holds it centred.
 *
 *  The lane's height is fixed at 62px and its grid row is what the connector overlay's rhythm
 *  is derived from, so a label taller than the row does not enlarge the lane — it overflows it
 *  and drags the row's other items off their own centres on the way out. Measured at the point
 *  this was written, a 96px floor on the value slot left the label 72.8px at 1280, which wrapped
 *  a four-word eyebrow onto two lines: the label block became 64.78px inside a 50px content box,
 *  escaped the lane by 8.78px, and pushed the icon 7.39px below where it sits in every other
 *  lane. Both are visible and neither is a text-geometry assertion, which is why they are here.
 */
test('a lane holds its own label, and holds it centred', async ({ page }) => {
  for (const width of [1440, 1280, 1024, 901, 768]) {
    await selectW01(page, width);
    const lanes = await page.evaluate(() => {
      const r2 = (n: number) => Math.round(n * 100) / 100;
      return [...document.querySelectorAll('.signal-lane')].map(lane => {
        const box = lane.getBoundingClientRect();
        const meaning = lane.querySelector('.signal-meaning')!.getBoundingClientRect();
        const icon = lane.querySelector('.signal-icon')!.getBoundingClientRect();
        const term = lane.querySelector('dt')!;
        const range = document.createRange();
        range.selectNodeContents(term);
        return {
          label: term.textContent ?? '',
          escapesTop: r2(box.top - meaning.top),
          escapesBottom: r2(meaning.bottom - box.bottom),
          // How far the icon sits from the lane's own centre. Every lane should agree.
          iconOffCentre: r2((icon.top + icon.bottom) / 2 - (box.top + box.bottom) / 2),
          termLines: new Set([...range.getClientRects()].filter(r => r.width > 0).map(r => Math.round(r.top))).size,
        };
      });
    });
    expect(lanes, `lane count at ${width}`).toHaveLength(4);
    for (const lane of lanes) {
      expect(lane.escapesTop, `${lane.label} label escapes lane top at ${width}`).toBeLessThanOrEqual(0);
      expect(lane.escapesBottom, `${lane.label} label escapes lane bottom at ${width}`).toBeLessThanOrEqual(0);
      expect(Math.abs(lane.iconOffCentre), `${lane.label} icon off centre at ${width}`).toBeLessThanOrEqual(1);
      // The eyebrow names the signal; it is fixed copy and there is no width at which wrapping
      // it is the right answer, because the lane cannot afford the line.
      expect(lane.termLines, `${lane.label} eyebrow lines at ${width}`).toBe(1);
    }
  }
});

/* --------------------------------------------------------------------------------------------
 * The prepared pack is the subject of its own view.
 *
 * The pack route renders inside the same four-zone body as the decision workspace, so the
 * finished document arrived with the workspace's other three zones still around it — including
 * a Why & proof panel reading "No decision selected. Evidence context is unavailable.", which
 * is true of the workspace and says nothing about the pack. A payoff document framed by two
 * dead panels reads as another screen rather than as the thing the approval produced.
 * ------------------------------------------------------------------------------------------ */

test('the prepared pack is the subject of its own view, not a panel inside the workspace',
  async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 810 });
    await page.goto('/inbox');
    await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
    await page.getByRole('button', { name: 'Approve application' }).click();
    const checkpoint = page.getByRole('region', { name: 'Human approval' });
    await checkpoint.getByRole('button', { name: /confirm approval/i }).click();
    await checkpoint.getByRole('link', { name: /open draft pack/i }).click();

    const pack = page.getByRole('article', { name: 'Application pack' });
    await expect(pack).toBeVisible();

    // Nothing beside the document claims a decision context the pack route does not have.
    await expect(page.getByText('No decision selected.')).toBeHidden();
    await expect(page.getByText('Evidence context is unavailable.')).toBeHidden();

    // And the document has the view to itself. Not measured as a share of the body — the pack
    // keeps a deliberate page measure and does not want the whole width — but structurally:
    // the body is one column on this route, where the decision workspace is four.
    const body = await page.evaluate(() => {
      const canvas = document.querySelector('.workspace-canvas')!.getBoundingClientRect();
      const grid = document.querySelector('.workspace-grid')!;
      const gridBox = grid.getBoundingClientRect();
      const gridStyle = getComputedStyle(grid);
      // Against the grid's content box, not its border box: the route pads the body to hold
      // the document's dark stage, and that padding is the composition rather than a shortfall.
      const track = gridBox.width - parseFloat(gridStyle.paddingLeft) - parseFloat(gridStyle.paddingRight);
      const visible = (selector: string) => {
        const element = document.querySelector(selector);
        return !!element && getComputedStyle(element).display !== 'none';
      };
      return {
        canvasShortfall: Math.round((track - canvas.width) * 100) / 100,
        queue: visible('.workspace-queue'),
        proof: visible('.proof-context'),
        rail: visible('.workspace-rail'),
      };
    });
    expect(body.canvasShortfall, 'canvas spans the body').toBeLessThanOrEqual(1);
    expect(body.queue, 'queue beside the pack').toBe(false);
    expect(body.proof, 'proof panel beside the pack').toBe(false);
    expect(body.rail, 'rail beside the pack').toBe(false);
  });

/* The payoff has to show the payoff. The finished document opened on a first viewport of pack,
 * approval and drafting-job UUIDs, bound versions and policy versions, with the first prepared
 * section below the fold — the trail before the thing it traces. */
test('the prepared document shows what was prepared in its first viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 810 });
  await page.goto('/inbox');
  await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
  await page.getByRole('button', { name: 'Approve application' }).click();
  const checkpoint = page.getByRole('region', { name: 'Human approval' });
  await checkpoint.getByRole('button', { name: /confirm approval/i }).click();
  await checkpoint.getByRole('link', { name: /open draft pack/i }).click();
  const pack = page.getByRole('article', { name: 'Application pack' });
  await expect(pack).toBeVisible();
  await page.evaluate(() => document.fonts.ready);

  // The first prepared section, and some of its recorded content, without scrolling.
  const heading = pack.getByRole('heading', { name: /01 Submission summary/i });
  const box = await heading.boundingBox();
  expect(box, 'submission summary heading is rendered').not.toBeNull();
  expect(box!.y + box!.height, 'submission summary heading inside the first viewport')
    .toBeLessThanOrEqual(810);
  await expect(pack.getByText(/Local draft for human review/i)).toBeInViewport();
});

/* ------------------------------------------------------------------------------------------
 * QUALOR-04B Task 5 — the judge experience as one continuous session.
 *
 * Every moment above is proved in isolation: the decision hierarchy, the reader and its exact
 * citation, the recorded trail, the approval boundary, the prepared pack. A judge never meets
 * them that way. They meet them in one unbroken run, and four individually correct moments can
 * still fail each other — the reader takes the canvas away and has to give it back unchanged,
 * and the rail has to still be showing the run it was showing before the detour.
 *
 * So this test asserts continuity rather than features: what the decision and the recorded
 * activity read as before the proof detour is captured from the page, and the same reads are
 * required to match afterwards. Nothing here is compared against a value the test supplied.
 * ------------------------------------------------------------------------------------------ */

test('the judge sequence survives itself: decision, proof, activity, approval, pack',
  async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 810 });
    await page.goto('/inbox');

    // --- Decision ---------------------------------------------------------------------
    await page.getByRole('link', { name: /AWS Agents for Humans/ }).click();
    await expect(page).toHaveURL(/\/inbox\/opp_/);
    const opportunityUrl = page.url();

    const hero = page.getByRole('heading', { level: 1, name: 'APPLY' });
    const signals = page.getByRole('group', { name: 'Decision signals' });
    const primaryAction = page.getByRole('button', { name: 'Approve application' });
    await expect(hero).toBeVisible();
    await expect(primaryAction).toBeEnabled();

    // The reads that have to survive the detour, taken from the rendered page. Captured as
    // `textContent` because that is what `toHaveText` normalises and compares against.
    const decisionBefore = await signals.textContent() ?? '';
    const activity = page.getByRole('list', { name: /recorded activity/i });
    const counters = page.getByRole('group', { name: /recorded in this run/i });
    const activityBefore = await activity.getByRole('listitem').locator('.event-title').allInnerTexts();
    const countersBefore = await counters.locator('dd').allInnerTexts();
    expect(activityBefore.length, 'the run recorded observations to survive').toBeGreaterThan(0);

    // --- open Proof, and the exact citation it exists to carry ------------------------
    const trigger = page.getByRole('button', { name: /why this decision/i });
    await trigger.click();
    const plane = page.getByRole('region', { name: 'Decision proof' });
    await expect(plane).toBeVisible();
    await expect(plane.locator('blockquote').first()).not.toBeEmpty();
    const citation = plane.getByRole('link', { name: /view original/i }).first();
    await expect(citation).toBeVisible();
    await expect(citation).toHaveAttribute('href', /^https:\/\/rules\.aws-agents-for-humans\.example\//);

    // --- close Proof ------------------------------------------------------------------
    await page.keyboard.press('Escape');
    await expect(plane).toHaveCount(0);
    await expect(trigger).toBeFocused();

    // --- the Decision is still the decision it was ------------------------------------
    await expect(hero).toBeVisible();
    await expect(signals).toHaveText(decisionBefore);
    await expect(primaryAction).toBeEnabled();

    // --- and the recorded trail is still the same recorded trail ----------------------
    // The reader is a presentation layer over persisted state; a detour through it must not
    // reorder, drop or inflate a single recorded observation or counter.
    await expect(activity.getByRole('listitem').locator('.event-title')).toHaveText(activityBefore);
    await expect(counters.locator('dd')).toHaveText(countersBefore);

    // --- Approval ---------------------------------------------------------------------
    await primaryAction.click();
    const checkpoint = page.getByRole('region', { name: 'Human approval' });
    await expect(checkpoint).toContainText('PENDING_APPROVAL');
    // The boundary is stated while the person can still decline, not after.
    await expect(checkpoint).toContainText(/nothing is submitted externally/i);

    // --- Confirm, and the state the server moves to -----------------------------------
    await checkpoint.getByRole('button', { name: /confirm approval/i }).click();
    await expect(checkpoint).toContainText('DRAFT_READY');

    // --- Application Pack -------------------------------------------------------------
    await checkpoint.getByRole('link', { name: /open draft pack/i }).click();
    const pack = page.getByRole('article', { name: 'Application pack' });
    await expect(pack).toBeVisible();
    await expect(page).toHaveURL(/\/draft-packs\/.+/);
    const packUrl = page.url();

    // Section 01 is the payoff, and it is on the first screen of it.
    const sections = pack.getByRole('region');
    await expect(sections.first()).toHaveAttribute('data-section-key', 'SUBMISSION_SUMMARY');
    await expect(pack.getByRole('heading', { name: /01 Submission summary/i })).toBeInViewport();

    // Seven canonical sections, in the order the server prepared them.
    await expect(sections).toHaveCount(7);
    const sectionOrder = await sections.evaluateAll(
      nodes => nodes.map(node => node.getAttribute('data-section-key')));

    // --- direct pack reload, with no prior app state ----------------------------------
    await page.goto(packUrl);
    const reloaded = page.getByRole('article', { name: 'Application pack' });
    await expect(reloaded).toBeVisible();
    await expect(reloaded.getByRole('region')).toHaveCount(7);
    // The same document, in the same order, rebuilt from persistence rather than from the
    // approval that was still in memory a moment ago.
    expect(await reloaded.getByRole('region')
      .evaluateAll(nodes => nodes.map(node => node.getAttribute('data-section-key'))))
      .toEqual(sectionOrder);
    await expect(reloaded).toContainText('DRAFT_FOR_HUMAN_REVIEW');

    // The session began at an opportunity and ended at a prepared local document; nothing it
    // passed through offered to send that document anywhere.
    for (const control of await reloaded.getByRole('link').all()) {
      expect(await control.textContent() ?? '').not.toMatch(SUBMISSION_WORDS);
    }
    expect(opportunityUrl).toMatch(/\/inbox\/opp_/);
  });
