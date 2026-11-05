# Design System & Page Plan

> Status: **Implemented in Milestone 1.** Tokens live in `frontend/src/app/globals.css`; shadcn/ui primitives in `frontend/src/components/ui/` were adjusted for touch-friendly sizes (buttons and inputs 40px, `lg` buttons 44px) and bordered cards with a subtle shadow.

## 1. Personality

Trustworthy · modern · clean · intelligent · accessible. A professional SaaS product, not a government form. Restraint over decoration: no heavy gradients, subtle motion only.

## 2. Color tokens

| Token | Hex | Use |
|---|---|---|
| `--color-navy` (primary) | `#12324A` | primary buttons, sidebar, headings |
| `--color-teal` (accent) | `#0F8B8D` | icons, focus rings, highlights, active nav indicator, large text |
| `--color-teal-strong` | `#0B6F71` | teal **text/links** at body size (contrast 5.9:1 on white) |
| `--color-background` | `#F7F9FC` | app background |
| `--color-card` | `#FFFFFF` | cards, inputs, popovers |
| `--color-muted-foreground` | `#64748B` | secondary text (4.5:1 on white, the minimum) |
| `--color-foreground` | `#0F172A` | body text |
| `--color-border` | `#E2E8F0` | borders, dividers |
| `--color-success` | `#157A56` | success text/icons (5.3:1 on white, 4.7:1 on `success-soft`; darkened in M6 after an axe audit) |
| `--color-warning` | `#D99620` | warning **fills and icons only** |
| `--color-warning-strong` | `#8A5A0B` | warning text |
| `--color-error` | `#D94F4F` | error borders, icons, fills |
| `--color-error-strong` | `#B83A3A` | error text |

**Accessibility notes (checked against WCAG AA 4.5:1 for normal text):**
- White text on teal `#0F8B8D` is only ≈4.1:1, so **primary buttons use navy**. Teal works for icons, borders, and large text (≥ 24px, or 18.7px bold).
- Warning `#D99620` and error `#D94F4F` fail as small text on white. Use them for tinted badge backgrounds (10–15% opacity) with the `-strong` text variant.

### Status badges
| Status | Style |
|---|---|
| DRAFT, PENDING_REVIEW | slate tint |
| SUBMITTED, ACKNOWLEDGED | teal tint |
| IN_PROGRESS | navy tint |
| RESOLVED_PENDING_VERIFICATION | warning tint |
| VERIFIED_RESOLVED, CLOSED | success tint |
| REOPENED | error tint |
| CANCELLED | slate outline |
| `Simulated` / `Demo AI` / `Demo directory entry` | dashed outline badge, always visible |

Each badge pairs **color with an icon and a text label**. Color is never the only signal.

## 3. Typography

Font: **Inter** via `next/font/google` (self-hosted at build, no layout shift).

| Role | Size / line height | Weight |
|---|---|---|
| Display (hero) | 48 / 56 (mobile 36 / 44) | 700 |
| H1 page title | 30 / 38 | 700 |
| H2 section | 22 / 30 | 600 |
| H3 card title | 18 / 26 | 600 |
| Body | 16 / 26 | 400 |
| Small / meta | 14 / 20 | 400–500 |
| Caption | 12 / 16 | 500 |

## 4. Shape, spacing, elevation, motion

- **Radius:** cards `12px` (`rounded-xl`), inputs/buttons `8px`, badges full-pill.
- **Spacing:** 4px grid. Card padding 24px (mobile 16px), section gaps 32–64px, page gutter 16px mobile / 32px desktop.
- **Shadows:** `0 1px 2px rgb(15 23 42 / 0.06)` resting; `0 4px 12px rgb(15 23 42 / 0.08)` on hover/raised. A border is always present too.
- **Motion:** 150–200ms ease-out for hover/press, fade/slide ≤ 8px for entering content. All of it respects `prefers-reduced-motion`.
- **Touch targets:** ≥ 44×44px. Focus ring is a visible 2px teal ring with offset.

## 5. Components (shadcn/ui based)

Primitives: Button (primary navy / secondary outline / ghost / destructive), Card, Input, Textarea, Select, Checkbox, Label, Form (React Hook Form + Zod), Dialog, Sheet (mobile nav), DropdownMenu, Tabs, Badge, Skeleton, Toast (Sonner), Tooltip, Progress, Separator, Avatar.

Product components: `StatCard`, `StatusBadge`, `CategoryIcon`, `ComplaintCard`, `Timeline`, `ImageDropzone`, `StepIndicator`, `AuthorityCard` (with verification line + source link, or `DemoDirectoryBadge` for fictional entries), `DeliveryBadge` (delivery status; a simulated send always reads "Simulated: not delivered to a real department"), *Messages* (every message both ways) and *Response tracking* (`features/complaints/components/response-tracking.tsx`: reminder card, reply-meaning card, escalation card) on the details page, the dashed *Demo tools* card (simulation only), the dashboard's *Needs your attention* list, *Check the repair* (`repair-check.tsx`: after-photo drop zone, before/after pair, "The AI thinks…" box with warnings, decision form, *Earlier checks*), `AIInsightPanel` (shows observations, uncertainties, and the "AI-generated, please review" note), `EmptyState`, `ErrorState`, `PageHeader`.

## 6. Layouts

- **Public layout** (`/`, `/login`, `/register`): sticky top nav (logo, Home, How It Works, Features, Login, **Get Started**), with a hamburger → Sheet on mobile; footer.
- **App layout** (authenticated): left **sidebar** on ≥ `lg` (Dashboard, Report Issue, My Complaints, Settings, user menu). Below `lg`: top bar (logo + avatar menu, which holds Settings and Log out) + **bottom tab bar** with three tabs (Dashboard · **Report** · Complaints). The centre Report button is raised, so reporting is always one tap away.

## 7. Page plan

| Route | Milestone | Key sections | Data |
|---|---|---|---|
| `/` | M1 | Hero ("Your City. Your Voice. Smarter Civic Action."), CTA buttons, product mock-up made from real UI components (not a stock image), How It Works (4 steps), Features (6 cards), footer with privacy note + contact placeholders. **No invented partners or statistics.** | static |
| `/login`, `/register` | M1 | Centered card, RHF + Zod, inline errors, password visibility toggle, redirect back to the requested page | `/auth/*` |
| `/dashboard` | M1 shell, M2 data | Welcome + name, Report button, 4 stat cards, recent complaints, recent activity, empty state | `/dashboard/summary` |
| `/report` | M2 (manual), M3 (AI), M4 (department + submit) | 6-step wizard with `StepIndicator`; server-saved draft | complaints, evidence, analysis, authorities, communications |
| `/complaints` | M2 | Search, category + status filters, sort, cards, pagination, empty/no-results states. Filters live in URL query params. | `/complaints` |
| `/complaints/[id]` | M2 → M6 | Header (ref, title, category, status, date) · Issue (photo, description, location map) · AI analysis · Department · Communications · Timeline · Resolution panel. **Actions depend on status.** | many |
| `/settings` | M1 basic, M7 full | Profile, account, notification preferences, privacy settings | `/users/me` |

## 8. Empty, loading, and error states

Every data view has three designed states: **skeleton** loading (no spinners for whole pages), **empty** (icon + one-line explanation + primary action), and **error** (plain-language message + retry). AI steps show progress text ("Looking at the photo…") and always offer a manual path.
