# Public School Website Module (`website`)

**Document 3 of 3.** This file specifies the public school website that each school can run, and edit from inside its ERP. It is built **last, as Phase 16**, after the core platform's release checkpoint (Phase 15) is complete. References to **ARCH** point to `01_PROJECT_ARCHITECTURE.md` and **GUIDE** to `02_BUILD_GUIDE.md`. All rules in GUIDE section 0 (including autonomous operation and the UI quality gate) apply to this module.

> **Rule for the builder AI:** do not start any work from this file until the Phase 15 RELEASE CHECKPOINT is complete. Verify current library documentation before using any library. Never use copyrighted images or fonts you are not licensed to bundle.

---

## 1. Goal

Give every school a **beautiful, modern, fast public website** (home, about, programs, admissions, news, events, gallery, staff, contact and more) that the school's own staff edit **inside the ERP**, with no technical skill and no way to break the design. It is a licensable, switchable module that you can sell as an add-on, and it fits Ethiopian conditions: bilingual (English/Amharic), light on slow networks, easy to share through Telegram and phone buttons.

## 2. Scope

**In scope:** server-rendered public pages, ready-made templates with editable blocks, the editor and media library inside the ERP, news and events, forms, SEO, domains, privacy controls, and an optional AI helper.
**Out of scope (for now):** free-form drag-anywhere page building, online shop, forums, member areas other than the existing portals, analytics beyond simple privacy-friendly counters, and a mobile-app version of the editor.

## 3. Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Rendering | **Server-side rendered HTML from the school's API** (Jinja2 templates), with minimal JavaScript | Fast on weak networks, good for search engines, no extra server or build system per school |
| Editing model | **Templates made of blocks**, not a free-form builder | Every school's site stays beautiful and consistent |
| Preview | The editor's preview is the **same server renderer** used in production | What you see is exactly what is published |
| Module boundary | The module owns its own content tables (pages, news, events, media). Other modules feed it only through **actions and events** | Keeps the module system rules (ARCH §4.5) |
| ERP location | The ERP web app moves under **`/app`** (configurable). The domain root shows the public site | One domain per school, clean URLs |
| Privacy | **Nothing about students or staff is public unless deliberately published**, with consent records | Children's safety and legal exposure |
| Announcements | Announcements are **not** given a public flag. A "Publish to website" action creates a draft news post from an announcement | Avoids coupling to the communication module's tables |

## 4. Architecture

### 4.1 Request flow
```
Visitor ─► Caddy (TLS, school domain) ─┬─ /                 → public site (website module, SSR, cached)
                                       ├─ /{locale}/…       → public site pages (am, en, later om, ti)
                                       ├─ /verify/{code}    → certificate verification (Document Studio)
                                       ├─ /app/…            → ERP web app (static SPA)
                                       └─ /api/v1/…         → API
```
- If the website module is off or unpublished, `/` redirects to `/app`.
- `APP_BASE_PATH` is configurable: `/app` in production, `/` in local development (the dev web app keeps its port and the public site is served by the API at its own port, so development is unaffected).
- Reserved slugs that pages can never use: `app, api, verify, static, media, admin, login, sitemap.xml, robots.txt`.

### 4.2 Rendering and caching
- Pages render from **published versions only**. Draft content renders only through the authenticated preview endpoint.
- Rendered HTML is cached per `(page, locale, version)` and invalidated on publish. Responses carry `ETag` and sensible `Cache-Control`. Static assets (CSS, fonts, images) are fingerprinted and cached long-term.
- CSS is generated from the school's **design tokens** (ARCH §5.11) plus the chosen template's layer, so the school's brand colors apply automatically in light and dark.
- JavaScript is progressive enhancement only (mobile menu, gallery lightbox, language switch, form submit, scroll reveal), small and dependency-free, delivered with CSP nonces. The site works with JavaScript disabled.

### 4.3 Media
- Public images live in a **public media area** separate from private student files. Uploads are validated (type, size, dimensions), re-encoded to **WebP/AVIF** in several widths (`srcset`), with a tiny blurred placeholder. SVG uploads are rejected unless sanitized. Alt text is stored **per language** and is required before publishing.
- Each image has flags: `contains_people`, `contains_minors`, and a **consent record** (who gave it, when, scope). Images flagged `contains_minors` cannot be published without a consent record.

### 4.4 Domains
- Every site gets a default address (a subdomain of the owner's domain, e.g. `{slug}.<owner-domain>`). A school can attach its own domain: the ERP shows DNS instructions and verifies ownership, and the instance's Caddy configuration is generated for TLS. In development this is a stub. Real DNS and domains are listed in `docs/OWNER_ACTIONS.md`.

## 5. Design standards for the public site

Follow ARCH §11.5 (clean, restrained, tokens only) **adapted for a marketing-style site**: still clean and professional, but more spacious and expressive.

- **Feel:** modern, warm, trustworthy, clearly "a school", never futuristic, never cluttered. Strong typographic hierarchy, generous whitespace, one brand accent, subtle depth only.
- **Grid and spacing:** 12-column grid, max content width about 1200, section padding 64 to 96 (desktop) and 40 to 56 (phone), 8-point spacing scale from tokens, corner radius 12 to 16, consistent card style.
- **Type:** the ERP's Latin sans plus a Ethiopic font, fluid sizes (`clamp`): H1 about 40 to 56, H2 about 28 to 36, body 16 to 18, comfortable line height (1.6, a bit more for Ethiopic). Fonts are self-hosted, subset with `unicode-range`, `font-display: swap`.
- **Imagery:** large, well-cropped photos where the school has them. **The site must look excellent with zero photos**: typographic heroes, brand-color shapes, subtle patterns, and generated placeholders (SVG/CSS) so a new school's draft is never empty or ugly.
- **Motion:** gentle fade/slide on scroll, 150 to 300 ms, fully disabled for "reduce motion."
- **Navigation:** sticky header with logo, menu, language switch, a clear **Apply** button and a **Login** button. Mobile gets a clean slide-in menu. Rich footer with contact, links, social and language.
- **CTAs:** one primary call to action per section. Phone, Telegram and WhatsApp buttons use `tel:` and `https://t.me/...` style links.
- **Both color schemes:** light by default, dark via `prefers-color-scheme`, both from tokens.
- **Quality bar:** a visitor should believe a professional agency built it.

## 6. Templates

A template = block renderers (layout variants) + a CSS layer + default page set + default block order. Ship at least **three** at launch (a fourth if time allows):

| Template key | Character | Good for |
|---|---|---|
| `modern-clean` | Light, airy, large type, soft shapes | Most schools |
| `warm-primary` | Friendly, rounded, playful accents | KG and primary schools |
| `academic-classic` | Structured, serif accents, formal tone | Secondary and preparatory schools |
| `bold-contemporary` (optional) | High contrast, large imagery | Private and international schools |

Rules: all templates support every block in §7 (with graceful fallbacks), both locales, light and dark, and the school's accent color. **Switching templates preserves all content.** A block unsupported by a template falls back to the default layout, never disappears.

## 7. Block catalog

Each block has a typed schema (Pydantic → JSON Schema) with field hints. The editor forms are **generated from the schema**, so adding a block needs no new editor code. Minimum launch set:

| Block | Purpose |
|---|---|
| `hero` | Headline, subheading, primary/secondary CTA, image or typographic variant |
| `about` | Text + image, mission/vision/values |
| `stats` | Key numbers (students, teachers, years, results). Manual or opted-in sync |
| `programs` | Programs by level/stage, generated from the school's scope with editable descriptions |
| `admissions_steps` | How to apply, steps, dates, CTA to the application page |
| `features` | Icon + title + text grid (facilities, approach) |
| `news_list` | Latest news |
| `events_list` | Upcoming events with Ethiopian and Gregorian dates |
| `gallery` | Image grid with lightbox, captions |
| `staff_leadership` | Opt-in staff/leadership cards (consent required) |
| `testimonials` | Quotes (consent required) |
| `faq` | Accordion |
| `downloads` | Forms, policies, calendars, with file size |
| `contact` | Address, phone, email, hours, map link, inquiry form |
| `map` | Click-to-load map (no heavy third-party script until the visitor asks) |
| `cta_banner` | Strong call to action |
| `rich_text` | Free text with constrained formatting |
| `video` | Click-to-load embed or hosted file (no autoplay) |
| `app_download` | The single mobile app: school code, QR code, store links (links supplied by the owner) |
| `login_portals` | Login entry points for parents, students and staff |

---
## 8. Content model

All tables follow ARCH §10 conventions (soft delete, audit, `row_version`).

| Table | Purpose |
|---|---|
| `site_settings` | Identity (name, tagline, logo), default and enabled locales, template key, contact details, social links, SEO defaults, map link, domain status |
| `site_pages` | `slug`, type (home, about, programs, admissions, news, events, gallery, staff, contact, custom, legal), status, in-nav flag, order, SEO fields |
| `site_page_versions` | Block list as JSON, version number, state (`draft`, `published`, `scheduled`, `archived`), author, publish time |
| `site_menus` | Header and footer menu structure |
| `site_media` | File reference, derivatives, alt text per locale, `contains_people`, `contains_minors`, consent record id, usage count |
| `media_consents` | Who consented, for whom/what, date, scope, expiry, evidence file (private) |
| `site_posts` | News: slug, cover, body (sanitized rich text), status, publish time, category |
| `site_events` | Title, start/end (Gregorian stored, Ethiopian displayed), location, description, public flag |
| `site_public_staff` | Opt-in public profile per staff member: display name, role title, bio, photo, consent id, visible flag |
| `site_downloads` | File, title, category, language |
| `site_faq`, `site_testimonials` | Entries with locale variants and consent where needed |
| `site_form_submissions` | Inquiry/contact submissions, spam score, status, handled-by |

Text fields use `content_translations` (ARCH §5.6) with **fallback to the default locale**. AI translations are saved only after the human clicks Save and are marked `needs_review`.

## 9. Editor experience (inside the ERP)

**Website Manager** (menu item, only visible with permission and when the module is on):

1. **Dashboard:** site status (draft/published), last published, unpublished changes, inquiries waiting, simple privacy-friendly visit counts (server-side, no cookies, no third parties), a checklist ("Add logo", "Add alt text to 3 images").
2. **Pages:** list with status. Create from page types. Reorder, hide, delete (soft).
3. **Page editor:** the core screen.
   - Left: ordered list of blocks (drag to reorder, duplicate, hide, delete) and an **"Add block" gallery with thumbnails**.
   - Center: **live preview** rendered by the real server renderer, with a desktop/tablet/phone switcher, refreshed as you edit (debounced).
   - Right: the selected block's form, generated from its schema, with image pickers, link pickers (internal pages, files, phone, Telegram), and field-level help.
   - Language switch with an optional side-by-side view (English | Amharic), with "missing translation" markers.
   - Undo/redo, auto-save to draft, and an unsaved-changes guard.
4. **Media library:** upload (drag and drop, multiple), crop and focal point, alt text per language, consent and minor flags with clear warnings, usage tracking, bulk actions.
5. **News and Events:** lists and editors with a constrained rich-text editor (headings, bold, italic, lists, links, quotes only; no raw HTML; sanitized on the server).
6. **Navigation and footer:** menu editor.
7. **Site settings:** identity, contact, map, social links, languages, SEO defaults, domain and DNS instructions.
8. **Template and style:** pick a template with previews, pick accent and (within limits) font pairing from the theme tokens. Switching is non-destructive.
9. **Inbox:** inquiries from the website, with status and reply-by-email or phone shortcuts.
10. **Publish:** draft → preview → **Publish** (or schedule). Version history with diff summary and one-click **rollback**. "Unpublished changes" indicator. All of it audited.

The editor follows the ERP's UI standards (ARCH §11.5): shared components, tokens, loading/empty/error states. It is a desktop-first screen that must remain usable on a tablet.

## 10. "Create my site" wizard

Goal: a good draft in a few minutes, with nothing published automatically.
- Inputs pulled from the ERP (read through whitelisted service functions): school name, logo, contact details, levels offered (academic scope), curriculum and term system, selected leadership (opt-in), recent announcements (offered as news drafts, never auto-published).
- Steps: choose template → confirm identity and contact → choose pages to create → generate draft → review each page.
- **Optional AI help** (only when the AI module is on and permitted): draft the about text, program descriptions and a welcome message in English and Amharic, using the school's own key. Output is marked `needs_review`, and a human must confirm every text.
- Without AI, the wizard fills sensible placeholder copy in both languages (clearly marked "edit me").

## 11. Public site features

- **Pages and sections:** all blocks in §7, with admissions and contact flows built in.
- **Languages:** English and Amharic switch on every page, `hreflang` links, locale in the URL (`/am/...`), fallback to the default locale for missing text. Afan Oromo and Tigrinya later by adding locales.
- **Admissions:** an "Apply" button to the public application page (if the admissions module is on and its public page is enabled). Otherwise, the contact/inquiry form.
- **Inquiry/contact form:** honeypot field, rate limiting, optional CAPTCHA through an adapter (provider chosen later, stub now), notification to the school through the notification service, and a visible confirmation.
- **Events:** list and detail pages, Ethiopian and Gregorian dates side by side, "add to calendar" file.
- **News:** list, detail, categories, share links (copy link, Telegram, WhatsApp, Facebook).
- **Verify a certificate:** a link to the existing `/verify` page.
- **Mobile app section:** school code, QR code and store buttons (store URLs come from the owner).
- **Legal pages:** privacy policy, terms and accessibility statement templates, editable, with a reminder to have them reviewed locally.
- **Error pages:** friendly 404 and 500 pages in both languages.
- **No cookie banner needed** as long as there are no tracking cookies or third-party trackers. The site must not add any.

## 12. SEO, performance and accessibility

**SEO:** unique title and description per page and locale, Open Graph and Twitter cards with generated share images, `JSON-LD` (`School`/`EducationalOrganization`, `Event`, `NewsArticle`), `sitemap.xml` (with `hreflang` alternates), `robots.txt`, canonical URLs, clean slugs, and unpublished or draft content never indexed.

**Performance budgets (targets, to be measured and tuned in P16-26):**
- Home page transfer size under about 500 KB excluding the hero image, and a hero image under about 150 KB (optimized).
- JavaScript under about 30 KB. No render-blocking third-party code. No layout shift from images (fixed aspect ratios).
- Lighthouse (mobile, throttled) goals: Performance 90+, Accessibility 95+, SEO 95+, Best Practices 95+. Run in CI against the seeded demo site.
- Rendered pages served from cache in the tens of milliseconds, even for a large school.

**Accessibility:** WCAG 2.2 AA targets: semantic HTML landmarks, skip link, visible focus, keyboard operable menu/accordion/lightbox, alt text enforced, sufficient contrast in every template and theme, reduced-motion respected, language attributes per page and per inline segment.

## 13. Privacy, safety and security

- **Opt-in publishing.** Public pages never query private ERP tables. Any ERP data that appears (levels offered, optional counts, selected staff) comes through **whitelisted service functions that return only minimal public fields**, or from the module's own tables.
- **Consent:** photos of identifiable people, and especially minors, require a consent record. The publish step **blocks** media flagged `contains_minors` without consent, and lists exactly what is blocking. Student names are never shown publicly by default, and the module has no block that lists students.
- **Staff** appear only through opt-in public profiles with consent.
- **Security:** strict CSP with nonces, security headers, HTML sanitization allowlist for rich text, upload validation and re-encoding, no user-supplied scripts or raw HTML, rate limits on forms and search, safe redirects, escaped output everywhere. Preview endpoints require authentication and a short-lived token.
- **Draft protection:** unpublished content, previews and media in drafts are never publicly retrievable.
- **Abuse:** spam protection on forms, size limits on submissions, and moderation status in the inbox.
- **Legal:** a local lawyer should review the privacy and consent wording (listed in `docs/OWNER_ACTIONS.md`).

## 14. Permissions, audit, AI, controller

**Permissions** (Super Admin holds all by default; add a "Communications Officer" default role):
`website.site.view`, `website.page.edit`, `website.page.publish`, `website.media.manage`, `website.news.manage`, `website.events.manage`, `website.staff_profiles.manage`, `website.forms.view`, `website.settings.manage`, `website.template.change`, `website.domain.manage`. Publishing is separate from editing, with an optional approval step.

**Audit:** every edit, publish, rollback, consent change and settings change is audited. Page versions are `Revertible` (ARCH §5.4). Events emitted: `website.published`, `website.unpublished`, `website.inquiry_received`.

**Actions (shared registry, ARCH §6):** `website.draft_text`, `website.translate_page` (preview, then Save), `website.suggest_alt_text`, `website.generate_site_draft`, `website.publish_news_from_announcement`, `website.publish` (risk `write`, always needs confirmation). AI can never override a consent block.

**Controller:** the module is a licensable key (`website`) in plans. The heartbeat reports whether a site is published. The controller can pre-set a school's default domain and, later, push template packs.

**Mobile app:** unchanged. The single app is not extended for the website. The site simply advertises it (the `app_download` block).

## 15. Testing and acceptance

- **Renderer:** golden HTML snapshots per block × template × locale × color scheme. A fixture site renders identically across runs.
- **Safety:** an XSS payload corpus against every text field and the rich-text sanitizer. A **privacy leak scan**: seed private data (a student name, a phone number) and assert it appears nowhere in any rendered public page or sitemap. Consent gate tests: media flagged `contains_minors` cannot publish without consent. Draft and preview isolation tests.
- **Routing:** `/app` base-path tests, reserved-slug tests, locale fallback and `hreflang` tests, redirect behavior when the module is off.
- **Forms:** honeypot, rate limit and spam tests, inbox flow.
- **Quality gates:** axe accessibility scan on every rendered page of every template, Lighthouse CI against budgets, screenshot review at 1440, 768 and 390 widths, light and dark, English and Amharic (including very long Amharic strings), and **zero-photo** and **full-photo** variants.
- **E2E (Playwright):** wizard → edit a block → live preview → publish → public page shows the change → switch language → submit contact form → see it in the inbox → rollback → public page reverts.
- **Acceptance (all must be true):**
  1. A new school can go from nothing to a published, good-looking bilingual site in under 15 minutes using the wizard.
  2. The seeded demo site scores within budget on Lighthouse and passes axe with no serious violations.
  3. No private data appears on any public page (leak scan passes).
  4. Switching templates never loses content.
  5. The full existing test suite and smoke e2e still pass after the `/app` base-path move.
  6. The owner-review checklist (`docs/website/WEBSITE_CHECKLIST.md`) is complete.

---

## 16. Tasks (Phase 16)

Mirror these into `docs/PROGRESS.md` as unchecked. Follow the same working rules, Definition of Done and UI quality gate as every other phase.

### Foundation
- [ ] **P16-01** Scaffold module `website` (manifest, permissions, i18n namespace, settings schema, licensable, default off). **Verify:** module conformance test passes (GUIDE Appendix A).
- [ ] **P16-02** **Move the ERP web app under `/app`** (`APP_BASE_PATH`, default `/app` in production and `/` in dev): Vite base, router basename, links, Caddy routes, compose, dev scripts, e2e tests. Legacy `/login` redirects to `/app/login`. When the website is off or unpublished, `/` redirects to `/app`. **Verify:** the full test suite and the smoke e2e pass, deep links work, mobile app login unaffected.
- [ ] **P16-03** Models and migrations for all §8 tables.
- [ ] **P16-04** Public media pipeline: public area, validation, WebP/AVIF derivatives with `srcset`, placeholders, alt text per locale, consent flags, SVG policy. **Verify:** upload tests including malicious files.
- [ ] **P16-05** Block system: Pydantic schemas → JSON Schema, registry, schema versioning, validation, and the minimum block set from §7. **Verify:** each block validates good and bad input.
- [ ] **P16-06** SSR renderer: Jinja2, token-to-CSS build, critical CSS, small progressive-enhancement JS with CSP nonces, cache and invalidation, `ETag`. **Verify:** golden snapshot tests; page works with JavaScript disabled.
- [ ] **P16-07** Templates: `modern-clean`, `warm-primary`, `academic-classic` (and optionally `bold-contemporary`), each complete for every block, locale and color scheme, with graceful fallbacks. **Verify:** snapshot and axe tests per template.
- [ ] **P16-08** Public routing and i18n: `/`, `/{locale}/…`, language switch, `hreflang`, fallbacks, reserved slugs, 404 and 500 pages.
- [ ] **P16-09** SEO: meta, Open Graph, JSON-LD, `sitemap.xml`, `robots.txt`, canonical URLs, noindex for drafts.
- [ ] **P16-10** Rich-text sanitizer and the constrained editor component. **Verify:** XSS corpus.
- [ ] **P16-11** Pages and versions: draft, preview (short-lived token), publish, schedule, rollback, audit, events, `Revertible`.
- [ ] **P16-12** News and events (EC/GC display, add-to-calendar) and the `publish_news_from_announcement` action.
- [ ] **P16-13** Public staff profiles, gallery, downloads, FAQ, testimonials, all with consent handling and the minors' publish block. **Verify:** consent gate tests.
- [ ] **P16-14** Forms: inquiry/contact, honeypot, rate limit, CAPTCHA adapter stub, notification, inbox; admissions CTA integration with the public application page.
- [ ] **P16-15** Public data bridge: whitelisted functions with minimal fields (levels offered, optional counts). **Verify:** the privacy leak scan.

### Editor in the ERP
- [ ] **P16-16** Website Manager shell and dashboard, permissions, empty/loading/error states.
- [ ] **P16-17** Page editor: block list with drag and drop, add-block gallery with thumbnails, schema-generated forms, live server-rendered preview with device switcher, language switch with side-by-side view, undo/redo, auto-save, unsaved guard.
- [ ] **P16-18** Media library UI: upload, crop/focal point, alt text per locale, consent and minor flags, usage tracking.
- [ ] **P16-19** Menus and footer, site settings (identity, contact, click-to-load map, social, languages, SEO).
- [ ] **P16-20** Template and style picker with previews; non-destructive switching. **Verify:** content identical before and after switching.
- [ ] **P16-21** Publish workflow UI: preview, publish, schedule, version history with diff summary, rollback, "unpublished changes" indicator.
- [ ] **P16-22** "Create my site" wizard (ERP data pre-fill, placeholder copy in both languages, optional AI drafts marked `needs_review`).
- [ ] **P16-23** Domains: default subdomain, custom-domain instructions and verification, generated Caddy configuration (stubbed in dev). Real DNS and TLS steps go in `docs/OWNER_ACTIONS.md`.

### AI and controller
- [ ] **P16-24** Register the website actions with risk levels and previews (§14). **Verify:** AI cannot publish without confirmation and cannot bypass consent blocks.
- [ ] **P16-25** Controller: license key, plan inclusion, heartbeat field `site_published`, CP UI toggle.

### Quality
- [ ] **P16-26** Performance: measure against §12 budgets, add Lighthouse CI, tune images, fonts and caching until within budget.
- [ ] **P16-27** Accessibility and i18n pass: axe on all rendered pages, keyboard walkthrough, reduced-motion, long-Amharic text, language attributes.
- [ ] **P16-28** Security tests: XSS corpus, CSP checks, upload abuse, rate limits, privacy leak scan, consent gate, draft isolation.
- [ ] **P16-29** Visual review: screenshots of every template × page type × width × locale × color scheme × zero-photo/full-photo; self-review against `docs/website/WEBSITE_CHECKLIST.md` (create it from §5); save under `docs/review/p16/` and add an `OWNER_REVIEW.md` entry.
- [ ] **P16-30** Documentation: website editor guide (English and an Amharic draft marked for review), domain setup runbook in `docs/runbooks/`.
- [ ] **P16-31** E2E (Playwright): the full journey listed in §15.
- [ ] **P16-32** Update `README.md`, `docs/OWNER_TEST_GUIDE.md` and the dev launcher; re-run the full regression (`./scripts/dev.sh reset && ./scripts/dev.sh test && ./scripts/dev.sh smoke`).
- [ ] **P16-SEED** Seed: a published demo site for Demo Academy in English and Amharic, all three templates selectable, generated placeholder imagery only (no copyrighted images, no real photos of minors), sample news and events, a handful of inquiries.

### ✅ PHASE 16 CHECKPOINT
- [ ] All §15 acceptance criteria are true and recorded.
- [ ] The full suite, smoke e2e and Lighthouse CI are green.
- [ ] Tag `v1.1.0`, then write `docs/FINAL_REPORT.md` (GUIDE §0.7).
