# UI checklist

Distilled from ARCH §11.5. Every screen is reviewed against this list before it
is called done; the automated parts run in the UI quality gate (P1-27).

Use it for self-review (author) and for the owner review. Mark a screen done
only when every applicable box is ticked. "N/A" is allowed, but write why.

## 1. Foundation (screen-level, not per component)

- [ ] Uses the shared kit (`@erp/ui-web` on web, `owner/mobile/src/ui` on
      mobile) and tokens only — no ad-hoc components, colours, radii, shadows
      or spacing.
- [ ] No hard-coded user-facing text: every label, hint, title, empty state and
      error message comes from `t()` and exists in `en` and `am`.
- [ ] Dates go through the calendar layer (EC/GC), money through the money
      layer (ETB, santim, tabular numerals).
- [ ] The page fits the standard shell: page header (title, one-line
      description, one primary action), content max width (1280 lists/dashboards,
      720 forms), consistent page padding (24 desktop / 16 phone).

## 2. Layout and responsiveness

- [ ] Renders cleanly at **1440** (desktop), **768** (tablet) and **390**
      (phone) CSS pixels with no horizontal page scroll.
- [ ] Tables become stacked cards below 640; wide tables scroll inside their
      wrapper (never the page).
- [ ] Sidebar collapses to the icon rail / drawer on tablet and phone; the
      primary action stays reachable.
- [ ] Content does not overlap the top bar, banners, toasts or the floating
      assistant panel.
- [ ] Long Amharic text (30–40 % expansion) wraps without clipping, ellipsis or
      fixed-width labels; names are never truncated without a tooltip.
- [ ] Nothing is positioned with magic numbers; spacing comes from the
      4/8/12/16/24/32/48/64 scale.

## 3. States

- [ ] **Loading:** skeletons that match the final layout (no full-page spinner,
      no layout jump).
- [ ] **Empty:** explains what is missing and offers the next action.
- [ ] **Error:** plain message, retry action and the request id; no stack
      traces or technical detail.
- [ ] **403 / 404 / offline** screens exist where the route can hit them.
- [ ] Disabled / read-only controls are visibly disabled and explained
      (tooltip or inline help), never silently inert.
- [ ] Controller-session banner visible on every screen while a controller
      actor is signed in (read-only variant when writes are blocked).

## 4. Forms

- [ ] Labels above inputs, first field focused where useful, single column by
      default (two columns only for short paired fields).
- [ ] Required fields marked, helper text under the field, inline validation
      with plain sentences and no colour-only error signal.
- [ ] Inputs use the correct control: select for short fixed lists, combobox
      with search for long ones, date picker for dates, money input for ETB.
- [ ] Long forms have a sticky save bar; leaving with unsaved changes warns.
- [ ] Destructive actions ask for confirmation and name what is affected.

## 5. Colour, contrast and theme

- [ ] Light and dark are both first-class and both reviewed.
- [ ] Semantic colours only (primary, muted, destructive, success, warning,
      info); colour is never the only signal (icon or label alongside).
- [ ] Contrast meets WCAG AA: 4.5:1 body text, 3:1 large text and UI parts.
- [ ] A school theme changes accent and brand only; layout, spacing, type scale
      and component shape stay identical. A community theme cannot break the
      screen.
- [ ] Focus ring is visible in both modes and on every interactive element.

## 6. Typography

- [ ] Bundled Latin sans + Noto Sans Ethiopic; Ethiopic and Latin sit well
      together at the same size.
- [ ] Type scale 12/14/16/18/20/24/30, weights 400/500/600, line height
      1.4–1.6 (a little more generous for Ethiopic).
- [ ] Numbers in tables, marks and money use tabular figures and align.
- [ ] Sentence case, short plain sentences, one term per concept.

## 7. Interaction and accessibility

- [ ] Full keyboard path: every action reachable by Tab, dialogs trap focus,
      Escape closes, focus returns to the trigger.
- [ ] Every input has a label; icons that carry meaning have an accessible
      name; decorative icons are hidden from assistive tech.
- [ ] Touch targets at least 44 pt (iOS) / 48 dp (Android) on mobile, 38–44 px
      on web; targets are not crowded.
- [ ] Motion is 150–200 ms, feedback only, and respects
      `prefers-reduced-motion`.
- [ ] Automated axe scan: no serious or critical violations.

## 8. Data display

- [ ] Tables: sticky header, sortable where useful, filters bar, pagination,
      row actions, comfortable (44) and compact (36) density.
- [ ] Figures and totals are right-aligned with tabular numerals; units (ETB,
      marks, %) are labelled once, not repeated in every cell.
- [ ] Status badges use one consistent style and pair colour with a label.
- [ ] Charts stay simple: few series, labelled axes, accessible summary text.

## 9. Mobile-specific

- [ ] Native feel: platform navigation, bottom tabs (five at most), safe-area
      insets respected on every screen and on the tab bar.
- [ ] Touch targets ≥ 44 pt / 48 dp; swipe and pull-to-refresh gestures do not
      conflict with scrolling.
- [ ] Dark mode and both languages reviewed on a small and a large phone.
- [ ] Offline/unreachable states are explicit and recoverable.

## 10. Sign-off

| Field | Value |
| --- | --- |
| Screen | |
| Reviewer / date | |
| Widths reviewed | 1440 / 768 / 390 |
| Themes reviewed | light / dark |
| Languages reviewed | en / am |
| Screenshots | `docs/review/p0/…` |
| Open issues | |
