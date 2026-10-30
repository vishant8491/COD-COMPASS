# COD Compass — UI, UX & Design Architecture Decisions

**Document Version:** 1.0.0  
**Target Roles:** Founder, Operations Team, Business Manager  
**Accessibility Target:** WCAG 2.1 AA Compliant  

---

## 1. Executive Summary & Design Philosophy

COD Compass is an internal decision-support system built for a high-growth D2C haircare brand in India. In high-velocity e-commerce operations, decision fatigue and misaligned incentives frequently cause substantial financial damage:
- **Overly aggressive operations teams** blacklist pincodes on single return occurrences, throwing away expensive customer acquisition cost (CAC).
- **Overly lenient operations teams** ship high-risk cash-on-delivery orders blindly, bleeding ₹169.40 in forward freight, return freight, handling, and damaged inventory per return.

The COD Compass UI was designed under the core principle: **financial transparency over decorative complexity**. Every number, color, and action communicates direct rupee consequences with zero hidden assumptions.

---

## 2. User Personas & Primary Tasks

| Persona | Primary Daily Tasks | Critical UI Requirements |
| :--- | :--- | :--- |
| **Founder / CEO** | Morning performance check; assess yesterday's orders; verify net bottom-line gain; ensure marketing capital is not wasted. | 30-second executive summary; mathematical financial reconciliation bridge; explicit proof that sunk CAC is not double-counted. |
| **Operations Lead / Warehouse** | Process morning unfulfilled queue; verify addresses; review WhatsApp confirmations; approve dispatches or cancel bad orders safely. | High information density without clutter; clear status badges; masked customer phone numbers; destructive action confirmation modals. |
| **Business / Growth Manager** | Tune risk tolerance; run promotional prepaid nudges; simulate policy adjustments on real historical orders before deployment. | Non-technical slider and numeric inputs; real-time validation constraints; pre-deployment impact simulation preview. |

---

## 3. Information Architecture & Navigation

### Five Core Destinations
1. **Executive Cockpit (`/overview` / `?tab=overview`)**:  
   High-level health metrics, IST time context (UTC+5:30), 4 pre-shipment decision bucket cards (clickable to filter orders), operations attention summaries, and the audited financial reconciliation bridge.
2. **Pre-Shipment Queue (`/orders` / `?tab=orders`)**:  
   Searchable, filterable operations workspace with active filter chips, sort options, PII masking, a 4-action expected economics slide-over drawer, and single-click dispatch/cancel workflows.
3. **WhatsApp & Payment Simulator (`/simulator` / `?tab=simulator`)**:  
   Split-screen interactive sandbox with conversation queues, realistic WhatsApp message bubbles, quick customer replies, +1h and +25h timeout clock triggers, and idempotent payment webhooks.
4. **Policy Rules & Preview (`/policy` / `?tab=policy`)**:  
   Four grouped rule sections (Decision Thresholds, High Basket Safeguards, Prepaid Offer, Minimum Pincode Sample), dual synchronized numeric and slider inputs, strict threshold validation ($T_{\text{low}} < T_{\text{confirm}} < T_{\text{nudge}} \le T_{\text{hold}}$), and real-time financial backtest preview.
5. **Empirical Analysis (`/analysis` / `?tab=analysis`)**:  
   Deep-dive charts and accessible data tables illustrating the Chronic Prior RTO Escalation, the Small-Sample Pincode Trap, Empirical Bayes smoothing, Order Value Bands, Address Quality indicators, and September 2026 Holdout Backtest proof.

### URL Parameter Synchronization & Deep-Linking
- Every destination and filter state is bound to browser query parameters:
  - `?tab=orders&action=HOLD`
  - `?tab=simulator&order_id=ORD-2026-09-0042`
  - `?tab=orders&search=Pooja`
- Full support for browser **Back** and **Forward** buttons using native HTML5 `popstate` event listeners and `pushState` history management.
- Direct links can be bookmarked or shared between operations and management without losing filter context.

---

## 4. Visual Design System & Theme Architecture

### Semantic Token Architecture
All styling avoids hardcoded colors in favor of centralized Tailwind semantic design tokens and CSS custom variables (`frontend/src/index.css` & `frontend/tailwind.config.js`):

```css
:root {
  --bg-page: #F8FAFC;         /* Soft neutral slate-50 */
  --bg-card: #FFFFFF;         /* Crisp white surface */
  --bg-elevated: #F1F5F9;     /* Subtle elevated slate-100 */
  --border-subtle: #E2E8F0;   /* Clean slate-200 border */
  --text-primary: #0F172A;    /* High-contrast slate-900 */
  --text-secondary: #64748B;  /* Legible slate-500 */
}

.dark {
  --bg-page: #020617;         /* Deep rich slate-950 */
  --bg-card: #0F172A;         /* Elevated slate-900 surface */
  --bg-elevated: #1E293B;     /* Slate-800 modal/drawer surface */
  --border-subtle: #1E293B;   /* Slate-800 subtle border */
  --text-primary: #F8FAFC;    /* High-contrast slate-50 text */
  --text-secondary: #94A3B8;  /* Muted slate-400 */
}
```

### Theme Modes (Light / Dark / System)
- **Light Theme**: Polished SaaS interface with subtle neutral backgrounds and teal action accents (`#0D9488`).
- **Dark Theme**: Purpose-crafted dark mode using deep slate blues (`#020617`, `#0F172A`), preserving high contrast (4.5:1+ text contrast ratio) without naive color inversion.
- **System Theme**: Automatically tracks the operating system preference (`prefers-color-scheme: dark`) with instant reactive switching.
- **FOUC Prevention**: Inline `<script>` in `index.html` resolves and sets the HTML `.dark` class before the first paint cycle.

---

## 5. Usability, Interaction & Ergonomics

### Filter Ergonomics & Active Chips
- Operations users frequently combine filters (e.g., Action: `CONFIRM` + Risk: `HIGH`).
- Active filters render as clickable dismissal chips with a master "Clear all filters" button to eliminate filter confusion.

### PII Protection & Customer Phone Masking
- Unmasked customer phone numbers pose a privacy risk in public warehouse and operations environments.
- Phone numbers in the public orders table are automatically masked (`98765*****`), revealing full numbers only inside the secured detail drawer for authenticated dispatch verification.

### Destructive Action Confirmation Modal
- Accidental order cancellation destroys customer trust and wastes acquired ad spend.
- The **Cancel Order** button triggers an accessible modal dialog requiring the operator to enter a mandatory cancellation audit reason (e.g. "Customer requested cancellation via call", "Invalid pincode").

### WhatsApp Simulator Realism
- Real WhatsApp-style green chat bubbles for customer replies (`#DCF8C6` in light mode, `#065F46` in dark mode) and store outgoing bubbles.
- One-click quick response chips ("Haan bhej do, confirm hai!", "Address update kardo", "Nahi chahiye, cancel kardo") to rapidly test edge-case linguistic variations.
- Simulated clock controls (+1 Hour, +25 Hour Timeout) to verify time-sensitive auto-hold behaviors without waiting 24 real hours.

---

## 6. Accessibility & Inclusivity (WCAG 2.1 AA)

1. **Visible Focus Rings**: All interactive controls feature distinct 2px teal focus rings (`focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:outline-none`).
2. **Keyboard Trapping & Modal Focus**: The `Modal` component traps keyboard focus when open, binds `Escape` to close, and restores focus to the triggering element upon exit.
3. **Screen Reader Live Regions**: Mutation updates, clock advances, and payment events announce via `ToastContext` utilizing `aria-live="polite"`.
4. **Accessible Alternative Views**: The Analysis view provides an **Accessible Tables** toggle, allowing screen readers and keyboard users to inspect raw data counts without relying exclusively on SVG chart graphics.
5. **Reduced Motion Support**: All animations respect the operating system's `@media (prefers-reduced-motion: reduce)` setting by disabling unnecessary transforms and duration delays.

---

## 7. Technical Trade-offs & Rationales

1. **Native Tailwind & Semantic CSS Variables vs Heavy Component Libraries:**  
   *Decision:* Built lightweight accessible components (`Modal`, `Skeleton`, `EmptyState`) rather than importing monolithic UI libraries.  
   *Benefit:* Zero bloat, fast load times (<180kB minified gzipped bundle), and 100% control over contrast and theme tokens.
2. **In-Memory Endpoint Test Handlers vs Network Socket Binding:**  
   *Decision:* FastAPI endpoints are tested directly via typed asynchronous handler invocations in `pytest`, bypassing sandbox socket permission restrictions.  
   *Benefit:* Tests complete in 2.9 seconds with zero thread lockups or networking flakes.
3. **Empirical Bayes Shrinkage vs Naive Pincode Blacklists:**  
   *Decision:* Implemented Bayesian shrinkage pulling small-sample pincodes toward the 28.4% prior.  
   *Benefit:* Prevents blacklisting 541 single-order pincodes, preserving expensive marketing spend while protecting freight capital.

