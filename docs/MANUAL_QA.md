# Manual QA Test Scripts & Verification Guide — COD Compass

**Target Version:** 1.0.0  
**Tested Viewports:** 360x800 (Mobile), 768x1024 (Tablet), 1440x900 (Desktop)  
**Theme Coverage:** Light, Dark, System Modes  

---

### Prerequisites & Starting the Application

1. **Single-Command Full-Stack Run:**
   ```powershell
   python backend/main.py
   ```
   *The production React frontend is pre-built in `frontend/dist`. Visiting `http://localhost:8000` serves the complete full-stack application instantly!*

2. **Frontend Development Server with Hot-Reloading (Optional):**
   - Terminal 1: `python backend/main.py`
   - Terminal 2: `npm --prefix frontend run dev` (opens `http://localhost:5173`)

---

### Test Script 1: Theme System Verification (Light / Dark / System)

- **Objective:** Verify theme switching, color contrast, FOUC prevention, and system preference tracking.
- **Steps:**
  1. Open `http://localhost:8000` in your browser.
  2. Locate the **Theme Control** in the top navigation header (segmented 3-way radio: Sun, Moon, Laptop).
  3. Click **Dark Mode (Moon icon)**:
     - Verify background transitions to dark slate (`#020617`).
     - Verify surfaces elevate to deep slate (`#0F172A`) with high-contrast off-white text (`#F8FAFC`).
     - Verify financial badges, charts, and table rows remain high-contrast and legible.
  4. Reload the page (`Ctrl+R` / `F5`):
     - Verify there is **no flash of unstyled content (FOUC)**; the dark theme renders before the first paint.
  5. Click **Light Mode (Sun icon)**:
     - Verify background transitions to soft neutral slate (`#F8FAFC`) with crisp white card surfaces.
  6. Click **System Mode (Laptop icon)**:
     - Change your OS color scheme between Light and Dark in Windows Settings.
     - Verify COD Compass synchronizes dynamically with your OS setting.

---

### Test Script 2: Executive Cockpit, Date Scopes & Financial Reconciliation Bridge

- **Objective:** Verify date scope presets, honest empty state handling, financial transparency, UTC+5:30 time context, and the audited reconciliation bridge.
- **Steps:**
  1. Navigate to **Executive Cockpit** (`?tab=overview`).
  2. Inspect the **Evaluation Scope** selector in the top-right header:
     - Notice that the default selection is **Yesterday** (in `Asia/Kolkata`, UTC+05:30).
     - Because the operational historical database contains orders through September 30, 2026, observe the **Honest Empty State**:
       - Clear icon and message: *"No Orders Recorded for Yesterday"*.
       - Explanatory copy explaining the current historical bounds.
       - Quick action buttons: **View September 2026 Demo Cohort (329 orders)** and **View All Time (1,988 orders)**.
  3. Click **View September 2026 Demo Cohort (329 orders)**:
     - Verify the scope dropdown switches to `September 2026 (Demo Cohort)`.
     - Observe the cockpit metrics populate with the 329 holdout orders.
     - Inspect the 4 KPI cards:
       - **Net Financial Improvement:** Formatted in bold font with sign (`-₹92` or `-₹91.61`). When negative, observe the card styling applies **red font and light red highlight** to clearly alert the operator rather than masquerading as a positive gain.
       - **Direct Freight Saved:** `+₹8,933`.
       - **Delivered Margin Forfeited:** `-₹8,863`.
       - **Acquisition Capital at Risk:** Monitored separately from pre-shipment cash deductions.
  4. Inspect the **4 Pre-Shipment Decision Buckets**:
     - Ship As-Is (111 orders, 33.7%).
     - Confirm WhatsApp (180 orders, 54.7%).
     - Hold for Review (36 orders, 10.9%).
     - Nudge to Prepaid (2 orders, 0.6%).
  5. Click the **Confirm WhatsApp** card:
     - Verify navigation immediately switches to the **Pre-Shipment Queue** with `action=CONFIRM` pre-filtered.
     - Check browser address bar: verify `?tab=orders&action=CONFIRM`.
  6. Click browser **Back Button**:
     - Verify you return cleanly to the **Executive Cockpit** without page reload.
  7. Inspect the **Audited Reconciliation Bridge**:
     - Baseline Delivered Contribution: `₹93,658.68`.
     - Avoided RTO Freight & Damage: `+₹8,932.69`.
     - Change in Delivered Margin: `-₹8,862.99`.
     - Prepaid Incentive Discounts: `-₹11.00`.
     - WhatsApp Messaging Sessions: `-₹145.92`.
     - Payment Gateway Fees: `-₹4.39`.
     - **Net Reconciled Improvement:** `-₹91.61` (**Discrepancy: ₹0.00**).
     - Simulated Policy Net Contribution: `₹93,567.07`.
     - Founder Takeaway Callout: Explains why sunk CAC (₹300) is NOT subtracted again.

---

### Test Script 3: Pre-Shipment Queue, PII Masking & Cancellation Safeguards

- **Objective:** Test orders filtering, PII masking, slide-over detail drawer, and destructive action modal.
- **Steps:**
  1. Navigate to **Pre-Shipment Queue** (`?tab=orders`).
  2. Verify customer phone numbers in the table are masked (`98765*****`) for privacy.
  3. In the search box, type `Pooja` or `KT100001`:
     - Confirm the table filters instantly.
     - Notice the "Clear search" (`×`) button in the input field.
  4. Select **Action: HOLD** and **Risk: High Risk**:
     - Verify active filter chips appear below the search bar.
     - Click the individual dismiss button (`×`) on the Risk chip; confirm the filter is cleared.
     - Click **Clear all filters**; confirm all dropdowns reset to default.
  5. Click any order row to open the **Slide-Over Detail Drawer**:
     - Verify full unmasked phone number is visible in the drawer for warehouse dispatch staff.
     - Review the **Expected Economics by Action (vs Baseline)** table: confirm the 4 action scenarios are calculated with the recommended action highlighted in teal.
  6. Test the **Destructive Action Safeguard (Cancel Order)**:
     - In the drawer footer, click **Cancel Order (Hold Dispatch)**.
     - Observe the accessible **Confirmation Modal** appear with title *"Cancel Order & Hold Dispatch"*.
     - Verify the **Confirm Cancellation** button is disabled until a mandatory audit reason is entered.
     - Type: *"Customer requested cancellation via call"*.
     - Click **Confirm Cancellation**:
       - Verify modal closes, toast notification confirms cancellation, and order state updates to `CANCELLED`.

---

### Test Script 4: WhatsApp & Payment Simulator

- **Objective:** Verify conversational state machine, intent classification with negation, clock timeouts, terminal state safety, and payment idempotency.
- **Steps:**
  1. Navigate to **WhatsApp Simulator** (`?tab=simulator`).
  2. In the left panel, select an order with `CONFIRM` or `NUDGE_PREPAID` action.
  3. Observe the WhatsApp phone canvas:
     - For `CONFIRM`: Automated store message asks customer to confirm dispatch.
     - For `NUDGE_PREPAID`: Store message offers the dynamically active policy discount (e.g. ₹25 instant discount) via order-specific mock payment link.
  4. **Customer Quick Replies & Negation Classification:**
     - Click `"Haan bhej do, confirm hai!" (YES)`:
       - Observe customer message in green, followed by store bot confirmation acknowledgement.
       - Check right State Inspector panel: verify lifecycle status updates to `CONFIRMED`.
     - Test **Intent Negation**: Type custom reply `"Please don't cancel my order, I will receive it"`:
       - Verify the bot classifies intent as confirmation/keep order rather than mistakenly cancelling on the word `"cancel"`.
     - Test **Negated Confirmation**: Type custom reply `"do not confirm"`:
       - Verify the bot classifies intent as cancellation rather than confirmation.
     - Test **Cancellation Precedence over Payment**: Type custom reply `"no payment link, cancel it"`:
       - Verify the bot recognizes cancellation priority over payment inquiries and processes cancellation.
     - Test **Conflicting Request / Address Correction**: Type custom reply `"Yes, but please update address to Flat 204, Green Heights"`:
       - Verify the bot prioritizes address correction over confirmation, updates the address, and routes order to review/confirmation.
  5. **Payment Gateway Webhook & Idempotency:**
     - Click **Simulate Payment SUCCESS (Convert to Prepaid)**.
     - Observe payment confirmation bubble appear in chat with transaction ID.
     - Check State Inspector: payment method updates to `PREPAID`, and status updates to `PREPAID_CONVERTED`.
     - Click the payment button a second time: verify the system returns an idempotent response (`ALREADY_PROCESSED`) without duplicating messages or state transitions.
     - Verify cross-order payment safety: attempting to replay the same transaction ID on a different order is rejected by the backend `payment_transactions` table.
  6. **Terminal Order State Safety & Post-Cancellation Payment:**
     - If an order is in terminal state `CANCELLED`, send an ordinary chat message: verify terminal order cannot be silently reopened back to active queues.
     - Simulate a payment received on an already `CANCELLED` order: verify the order transitions to `HELD_FOR_REVIEW` with an operational note requiring supervisor review for refund or manual reactivation.
  7. **Simulated Clock 24h Timeout:**
     - Select an order in `AWAITING_CONFIRMATION` status.
     - Under **Simulated Order Clock**, click **+25 Hours (Timeout)**.
     - Observe system notice appear in chat:
       `⚠️ [SYSTEM NOTICE]: 24 hours elapsed without customer response. Order automatically held for manual operations review.`
     - Verify order state transitions to `HELD_FOR_REVIEW`.

---

### Test Script 5: Policy Rules Editor & Pre-Deployment Simulation

- **Objective:** Adjust risk thresholds safely with ordering validation, and preview simulated financial impact before saving.
- **Steps:**
  1. Navigate to **Policy Rules & Preview** (`?tab=policy`).
  2. Inspect the 4 non-technical rule groups:
     - Decision Thresholds.
     - Confirmation & Basket Rules.
     - Prepaid Offer Incentives.
     - Operational Safeguards.
  3. Test **Synchronized Inputs**:
     - Move the **Low Risk Maximum** slider from 20% to 15%.
     - Observe the numeric input box updates in tandem.
  4. Test **Validation Rules**:
     - Attempt to set Low Risk to 50% (exceeding Confirm threshold of 40%).
     - Observe real-time validation error: *"Low-risk threshold must be strictly less than Confirm threshold"*.
     - Verify the **Preview Impact** and **Save Policy** buttons are disabled until valid.
  5. Click **Reset to Active Policy**:
     - Confirm all sliders restore to the currently active policy settings.
  6. Test **Pre-Application Simulation Preview**:
     - Set valid threshold adjustments and click **Preview Impact**:
       - Observe pre-deployment financial projection showing projected avoided RTO savings, foregone margin, and net monthly impact.
  7. Click **Deploy New Policy Version**:
     - Confirm the confirmation dialog appears with summary of changes.
     - Confirm deployment; verify green toast confirms new policy version.

---

### Test Script 6: Empirical Discoveries & Accessible Tables

- **Objective:** Verify empirical data visualizations, accessible table alternatives, and Founder Memo modal.
- **Steps:**
  1. Navigate to **Empirical Analysis** (`?tab=analysis`).
  2. Inspect the **Chronic Prior RTO Escalation** chart:
     - Verify 2+ Prior RTOs is highlighted with a catastrophic **76.5% RTO rate**.
  3. Inspect the **The "Pincode Trap"** histogram:
     - Verify that out of 1,066 resolved pincodes (1,067 unique orders), **554 have only 1 order**, proving why naive pincode blacklisting destroys marketing spend.
  4. Test **Accessible Tables View**:
     - In the top right header, click **Accessible Tables**.
     - Observe all SVG charts transform into accessible, high-contrast HTML data tables with complete numeric details.
     - Verify screen readers can read table headers (`scope="col"`) and rows cleanly.
     - Click **Charts** to switch back to vector graphics.
  5. Test **Founder Memo Summary**:
     - Click the **Founder Memo** button in the header.
     - Verify the accessible modal opens displaying the Executive Summary, the ₹169.40 formula, the 64.8% break-even rule, and the sunk CAC principle.
