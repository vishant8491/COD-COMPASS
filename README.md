# COD Compass — Pre-Shipment RTO Intelligence & Unit-Economics Optimizer

[![Python Tests](https://img.shields.io/badge/pytest-52%20passed-emerald.svg)](tests/)
[![Frontend Tests](https://img.shields.io/badge/node%3Atest-19%20passed-emerald.svg)](tests/test_frontend_logic.mjs)
[![TypeScript](https://img.shields.io/badge/TypeScript-clean%20build-teal.svg)](frontend/)
[![Theme Support](https://img.shields.io/badge/Themes-Light%20%7C%20Dark%20%7C%20System-teal.svg)](#theme-support--ui-design)
[![Accessibility](https://img.shields.io/badge/Accessibility-Accessible%20Design%20Patterns-blue.svg)](docs/UI_DECISIONS.md)
[![Architecture](https://img.shields.io/badge/Architecture-FastAPI%20%2B%20React%20%2B%20SQLite-navy.svg)](#architecture)
[![License](https://img.shields.io/badge/License-MIT-slate.svg)](LICENSE)

**COD Compass** is a pre-shipment decision engine and financial optimizer designed for a direct-to-consumer (D2C) haircare brand selling via Shopify with high Cash on Delivery (COD) volume (55% share, 28% baseline RTO rate).

Instead of treating RTO solely as a logistics failure or relying on crude pincode blacklists that incinerate customer acquisition capital, COD Compass reconciles the structural tension between the **Head of Operations** (cutting return freight invoices) and the **Head of Marketing** (protecting customer acquisition investments) through deterministic, rupee-denominated unit economics.

Every incoming COD order is evaluated before shipment across 4 contiguous, gap-free action tiers:
1. **Ship As-Is ($P \le 20\%$):** Low calibrated risk; fast-tracked for immediate warehouse dispatch.
2. **Ship After Confirmation ($20\% < P \le 35\%$ or Basket $\ge ₹1,500$):** Moderate risk; verified via automated WhatsApp messaging (₹0.80/session).
3. **Nudge to Prepaid ($35\% < P \le 65\%$ or Prior RTOs $\ge 2$):** Elevated risk; incentivized with an instant ₹25 discount via WhatsApp payment link.
4. **Hold for Operations Review ($P > 65\%$ or Incomplete Address):** High risk; held for address landmark enrichment and phone follow-up. Automatic order cancellation is **strictly disabled**.

---

## ⚡ Quickstart & Reviewer Verification Guide

### 1. Prerequisites
- Python 3.10+ (verified on Python 3.12.3)
- Node.js 18+ (verified on Node v22.14.0)
- **Zero Paid API Keys Required:** All NLP intent matching, risk scoring, prompt injection defense, and WhatsApp simulation run 100% offline via local deterministic Python implementations. An optional LLM adapter is provided via `.env` but is completely non-mandatory.

### 2. Environment Setup & Dependencies
```bash
# Clone the repository and navigate into the project root
git clone <repo-url> cod-compass
cd cod-compass

# Create and activate virtual environment
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install backend Python dependencies
pip install -r requirements.txt

# Install frontend dependencies and verify production build
npm ci --prefix frontend
npm --prefix frontend run build
```

### 3. Dataset Placement & Seeding
COD Compass supports two dataset modes:
- **Synthetic Public Demo Dataset (`data/demo_orders.csv`):** Pre-packaged in the repository with 500 realistic, leak-free, 0% PII synthetic orders for instant standalone verification.
- **Private Research Dataset (`data/orders_sample.csv`):** If provided, place the CSV directly at `data/orders_sample.csv` (automatically Git-ignored).

**To seed into the default local database (`backend/cod_compass.db`):**
```bash
# Auto-detects orders_sample.csv if present; otherwise uses demo_orders.csv
python scripts/seed_database.py --force

# Or explicitly force seeding with the synthetic demo dataset:
python scripts/seed_database.py --demo --force
```

**To verify in a clean disposable environment without touching the existing database:**
```powershell
$env:DATABASE_PATH = "$PWD\temp_eval.db"
python scripts/seed_database.py --demo --force
python backend/main.py
# Cleanup when finished:
Remove-Item temp_eval.db -Force; Remove-Item env:DATABASE_PATH
```

### 4. Run the Full-Stack Application
Because the React frontend is pre-built into production assets at `frontend/dist/`, running the backend immediately serves **both the REST API and the React Single Page Application** on a single local port:
```bash
python backend/main.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser!

*For frontend hot-reloading development mode (optional):*
- Terminal 1: `python backend/main.py`
- Terminal 2: `npm --prefix frontend run dev` (opens `http://localhost:5173`)

### 5. Run the Automated Test Suites
```bash
# Run all 52 Python backend, decision engine & defect regression tests
pytest -v

# Run all 19 frontend unit & logic tests importing directly from production TypeScript
node --experimental-strip-types --test tests/test_frontend_logic.mjs
# or via npm script:
npm --prefix frontend test

# Verify production frontend compilation
npm --prefix frontend run build

# Regenerate independent analysis and September replay results
python analysis/exploratory_analysis.py
```
*Executes all 71 automated unit and regression tests across financial math, leakage prevention, decision rules, chat simulation, theme resolution, PII privacy, and API endpoints.*

---

## 📊 Core Financial Model & Accounting Formulas

All figures are deterministic, test-verified down to the exact paisa, and centralized in `backend/app/services/financial_model.py`.

### 1. Baseline Parameters (Assignment Specifications)
- **Direct Expected RTO Loss per Return:**
  $$\text{Forward Shipping (₹65)} + \text{Return Shipping (₹65)} + \text{Packaging (₹25)} + 8\% \times \text{Damaged Inventory Cost (₹180)} = \mathbf{₹169.40}$$
- **Monthly COD Orders:** $3,000 \times 55\% = \mathbf{1,650 \text{ orders}}$
- **Expected Monthly COD Returns:** $1,650 \times 28\% = \mathbf{462 \text{ returns}}$
- **Expected Monthly Direct COD RTO Loss:** $462 \times ₹169.40 = \mathbf{₹78,262.80}$

### 2. Delivered Contribution Accounting
At ₹649 Average Order Value (AOV) with 62% gross margin:
- Gross Profit $= ₹649 \times 0.62 = ₹402.38$
- Delivered Net Contribution $= ₹402.38 - \text{Forward Shipping (₹65)} - \text{Packaging (₹25)} = \mathbf{₹312.38}$

### 3. Dynamic Break-Even Rule for Order Cancellation
When does canceling an order save more cash than shipping it?
$$\text{Expected Value if Shipped} = (1 - P) \times \text{Delivered Contribution} - P \times ₹169.40$$
$$\text{Expected Value if Cancelled} = ₹0$$
$$P_{\text{break-even}} = \frac{\text{Delivered Contribution}}{\text{Delivered Contribution} + ₹169.40}$$

Because delivered contribution depends directly on order basket size, **break-even varies by order value**:
- **₹400 basket:** Delivered contribution $= ₹158.00 \implies P_{\text{break-even}} = \mathbf{48.3\%}$.
- **₹649 AOV basket:** Delivered contribution $= ₹312.38 \implies P_{\text{break-even}} = \mathbf{64.8\%}$.
- **₹1,500 basket:** Delivered contribution $= ₹840.00 \implies P_{\text{break-even}} = \mathbf{83.2\%}$.

**Policy Takeaway:** Canceling an order below its break-even risk destroys more delivered gross margin than it saves in return shipping. Default automatic cancellation is disabled (OFF). Holding an order is not cancellation; it provides an operational pause for address enrichment.

### 4. Sunk CAC Protection
The ₹300+ customer acquisition cost was already spent at ad click time and is sunk capital. Subtracting ₹300 again from pre-shipment action comparisons double-counts marketing expense. COD Compass reports **Acquisition Spend at Risk** $( (1 - P) \times \text{CAC} )$ separately to protect customer acquisition investments.

---

## 🔍 Four Core Empirical Dataset Findings

Audited across 1,988 unique orders from `data/orders_sample.csv` (1,987 resolved: 1,422 delivered, 565 returned; 1 unresolved `IN_TRANSIT` order cleanly quarantined):

1. **Severe Chronic RTO Escalation (2+ Prior Returns Break Unit Economics):**  
   Customers with 0 prior returns return at 27.15% (501/1,845; 95% Wilson CI: [25.2%, 29.2%]); 1 prior return at 35.19% (38/108; 95% Wilson CI: [26.8%, 44.6%]). Customers with **2+ prior returns return at 76.47% (26 returns on 34 orders; 95% Wilson CI: [60.0%, 87.6%])**. Because 76.5% observed RTO exceeds the ₹649 break-even threshold (64.8%), shipping COD yields an expected negative contribution (-₹56.18/order on average). Routing them to an automated ₹25 prepaid nudge converts margin while avoiding return freight loss.
2. **Incomplete Delivery Addresses Correlate with Final-Mile Failure:**  
   Incomplete addresses (missing building numbers, floor, or landmarks) exhibit an observed **64.05% RTO rate (98/153; 95% Wilson CI: [56.2%, 71.2%])** vs. 25.46% for deliverable addresses (467/1,834; 95% Wilson CI: [23.5%, 27.5%]). Placing these on temporary hold for WhatsApp landmark collection recovers genuine orders without premature cancellation.
3. **Order Value Dynamics (Sweet Spot vs. High-Basket Remorse):**  
   Orders between ₹1,000–₹1,499 have the lowest return rate (**20.30% RTO**, 82/404; 95% Wilson CI: [16.7%, 24.5%]). Baskets ≥₹1,500 jump to **39.15% RTO (110/281; 95% Wilson CI: [33.6%, 45.0%])** due to doorstep cash remorse. WhatsApp confirmation above ₹1,500 verifies buyer commitment before fulfillment.
4. **The Pincode Trap (12 Missing Pincodes & High Sparsity):**  
   In deduplicated resolved orders (1,987 orders), there are **1,066 unique known 6-digit pincodes**. **554 pincodes have exactly 1 order ($n=1$)** (52.0%), and **1,036 have fewer than 5 orders** (97.2%). Zero pincodes have 10 or more orders (maximum in any pincode is 8). Exactly **12 orders lack pincodes**. (Note: the 1 unresolved `IN_TRANSIT` order, `KT100021`, has pincode `600030`, which is unique to that order, bringing total unique orders pincodes to 1,067). A blanket blacklist on high-RTO pincodes bans future customers on pure statistical noise. COD Compass uses **Empirical Bayes prior shrinkage** ($K=10$), regressing sparse pincodes toward the 28.4% national baseline.

---

## 💻 September 2026 Holdout Policy Replay Results

Evaluating the risk model (trained strictly on April–August 2026 data and frozen at August 31, 2026) over the complete September 2026 holdout cohort (329 unique resolved orders: 243 delivered, 86 returns):

### 1. Action Bucket Distribution & Observed Outcomes (329 Orders)
| Recommended Action Bucket | September Orders | Observed Delivered | Observed Returns | Observed RTO Rate (95% Wilson CI) |
| :--- | :---: | :---: | :---: | :---: |
| **CONFIRM (WhatsApp)** | 180 (54.71%) | 136 | 44 | 24.44% [18.7%, 31.2%] |
| **SHIP_AS_IS (Fast-track)** | 111 (33.74%) | 93 | 18 | 16.22% [10.5%, 24.2%] |
| **HOLD (Address Review)** | 36 (10.94%) | 13 | 23 | 63.89% [47.6%, 77.5%] |
| **NUDGE_PREPAID (Incentive)** | 2 (0.61%) | 1 | 1 | 50.00% [9.4%, 90.5%] |
| **Total Cohort** | **329** | **243** | **86** | **26.14%** |

### 2. Complete Reconciled Financial Bridge (September Cohort & Monthly Scaling)
*Derived programmatically via `analysis/exploratory_analysis.py` and exported to `analysis/replay_results.json`.*

| Financial Bridge Component | Observed Baseline (Sep 329) | Counterfactual Policy (Sep 329) | Monthly Scaled (1,650 Benchmark, Scale: 5.0152x) | Accounting Basis & Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| **Baseline Net Contribution** | **₹93,658.68** | — | **₹469,716.78** | Actual delivered gross margin minus actual 86 RTO losses (₹14,568.40) |
| **1. Avoided RTO Freight & Damage** | — | **+₹8,932.69** | **+₹44,800.70** | 52.731 avoided returns saved at ₹169.40 direct logistics cost each |
| **2. Change in Delivered Margin** | — | **-₹8,862.99** | **-₹44,451.65** | Margin forfeited on unconfirmed/unrecovered orders (62% gross margin - ₹90 fulfillment) |
| **3. Prepaid Incentive Discounts** | — | **-₹11.00** | **-₹55.17** | ₹25 instant discount on converted prepaid orders |
| **4. WhatsApp Messaging Sessions** | — | **-₹145.92** | **-₹731.82** | 180 confirmation sessions (₹0.80) + 2 prepaid nudges (₹0.96) |
| **5. Payment Gateway Fees (2%)** | — | **-₹4.39** | **-₹22.02** | 2% processing fee on net collected prepaid order value |
| **Sum of Financial Bridge Lines** | — | **-₹91.61** | **-₹459.43** | **Exact Reconciled Net Improvement (Discrepancy: ₹0.0000; Zero Balancing Adjustments)** |
| **Simulated Policy Net Contribution** | — | **₹93,567.07** | **₹469,257.35** | Baseline Contribution + Reconciled Net Improvement |
| **Passive Auto-Cancel Net Impact** | — | **-₹1,847.60** | **-₹9,266.07** | **Severe Loss:** Blind cancellation forfeits genuine margin on viable orders |

*Scaling Methodology Note:* The operating baseline is 1,650 monthly COD orders (from 3,000 monthly orders at 55% COD share). The scaling multiplier is $1,650 / 329 = 5.015197568389058$. All scaled projections are computed directly from unrounded source values.

### 3. Scenario Sensitivity Comparison (Monthly Scaled to 1,650 COD Orders)
- **Conservative Scenario (60% confirm, 15% prepaid conv, 50% hold recovery, 10% hold leakage):**
  Projected Net Gain: **-₹69,537.93/mo** (Avoids 231.0 RTOs).
- **Base Scenario (70% confirm, 22% prepaid conv, 70% hold recovery, 0% hold leakage):**
  Projected Net Gain: **-₹459.43/mo** (Avoids 264.5 RTOs).
- **Optimistic Scenario (80% confirm, 30% prepaid conv, 85% hold recovery, 0% hold leakage):**
  Projected Net Gain: **+₹53,762.11/mo** (Avoids 282.7 RTOs).

### 4. Economic Justification for the ₹25 Prepaid Discount
Targeted customer cohort: Repeat returners (≥2 prior returns, empirical RTO = 76.47%, AOV = ₹649.00).

- **Shipped COD Expected Value:** $0.2353 \times [₹649 \times 0.62 - ₹90] - 0.7647 \times ₹169.40 = \mathbf{-₹56.18}$ per order.
- **Discount Comparison:**
  | Discount | Est. Conversion | PG Fee (2%) | Net Prepaid Margin | Exp. Incremental Pool Value | Break-even vs ₹0 Discount |
  | :---: | :---: | :---: | :---: | :---: | :--- |
  | **₹0** | 10.0% | ₹12.98 | ₹280.13 | +₹32.83 | Baseline |
  | **₹15** | 19.0% | ₹12.68 | ₹265.43 | +₹60.31 | +10.46% conversion break-even |
  | **₹25** | **25.0% (Assumed)** | **₹12.48** | **₹255.63** | **+₹77.15** | **10.79% conversion break-even** |
  | **₹35** | 31.0% | ₹12.28 | ₹245.83 | +₹92.82 | +11.14% conversion break-even |
  | **₹50** | 40.0% | ₹11.98 | ₹231.13 | +₹114.12 | +11.71% conversion break-even |

- **Break-Even Derivation:** Net prepaid contribution at ₹25 discount (retaining 4% residual RTO) is ₹257.12. For ₹25 to outperform ₹0:
  $$c_{25} \times 257.12 + (1 - c_{25}) \times (-56.18) > -22.50 \implies c_{25} > \frac{33.68}{313.30} = \mathbf{10.75\%}$$
  Because 10.75% conversion is well below the expected 22% conversion, offering ₹25 (3.8% of basket) delivers **+₹12.75 expected value per targeted customer** compared to -₹56.18 for COD.

---

## 🏗️ Architecture & Project Structure

```
cod-compass/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints.py         # REST API routes (orders, preview, simulator, etc.)
│   │   ├── db/
│   │   │   └── database.py          # SQLite schema, indices & parameterized queries
│   │   ├── models/
│   │   │   └── schemas.py           # Strictly typed Pydantic V2 models
│   │   └── services/
│   │       ├── decision_engine.py   # Contiguous policy thresholds & action selection
│   │       ├── financial_model.py   # Deterministic rupee calculations & breakeven rules
│   │       ├── risk_model.py        # Leak-free pipeline with Empirical Bayes smoothing
│   │       ├── chat_simulator.py    # WhatsApp state machine, clock advance & payment webhooks
│   │       └── llm_adapter.py       # Address completeness, Hinglish NLP & injection defense
│   └── main.py                      # FastAPI server & static SPA mount
├── frontend/                        # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/Header.tsx    # Sticky navigation, policy badges & offline status
│   │   ├── views/OverviewView.tsx   # Executive cockpit & financial reconciliation bridge
│   │   ├── views/OrdersView.tsx     # Filterable pre-shipment queue & slide-over drawer
│   │   ├── views/SimulatorView.tsx  # Interactive WhatsApp phone mockup & clock advance
│   │   ├── views/PolicyView.tsx     # Non-technical policy editor & pre-application preview
│   │   ├── views/AnalysisView.tsx   # Empirical findings charts & backtest scenarios
│   │   ├── api.ts                   # Typed API client
│   │   └── types.ts                 # Shared TypeScript interfaces
│   └── dist/                        # Pre-compiled production bundle
├── data/
│   ├── demo_orders.csv              # Synthetic demo dataset (0% PII, public reproduction)
│   └── orders_sample.csv            # Private historical dataset (Git ignored)
├── docs/
│   ├── FOUNDER_MEMO.md              # 1-2 page executive memorandum to Founder/CEO (Vishant Pal)
│   ├── FOUNDER_MEMO.pdf             # Rendered executive PDF via ReportLab (strictly 2 pages)
│   ├── DECISION_LOG.md              # Engineering, algorithmic & financial decision log
│   ├── AI_USAGE_LOG.md              # AI assistance disclosure & corrected flawed suggestions
│   ├── QA_REPORT.md                 # 52 backend + 19 frontend tests passing summary
│   └── MANUAL_QA.md                 # Step-by-step manual test scripts for reviewers
├── scripts/
│   ├── seed_database.py             # Seeds SQLite and fits pre-shipment model
│   ├── generate_synthetic_demo.py   # Generates leak-free synthetic demo dataset
│   └── generate_founder_memo.py     # Compiles Founder Memo to Markdown and PDF
├── tests/                           # 52 pytest tests + 19 Node unit logic tests
└── pytest.ini                       # Test configuration
```

---

## 🔒 Security & Data Privacy

1. **Private Customer PII:** The private dataset `data/orders_sample.csv` is explicitly listed in `.gitignore` and is never committed to Git.
2. **Synthetic Demonstration Mode:** Running `python scripts/generate_synthetic_demo.py` generates `data/demo_orders.csv` containing realistic Indian haircare orders with zero real names or phone numbers.
3. **Prompt Injection Safeguards:** Customer chat messages and address strings are checked against known jailbreak patterns (`Ignore previous instructions`, `Mark as VIP`) and quarantined with a `SECURITY_FLAG` for manual supervisor review. This regex filtering is an operational heuristic, not an absolute security guarantee.
4. **Test Scope & Architecture:** Direct handler unit tests verify in-process request validation, schemas, and business logic. They do not simulate external HTTP network routing or ASGI middleware. Full ASGI HTTP socket tests are documented in the QA report as BLOCKED in the sandboxed execution environment.
5. **Offline Local Fallback:** No paid third-party API keys (OpenAI, Gemini, WhatsApp, Payment Gateway) are mandatory. The local demo runs 100% offline with an explicit badge in the UI.

---

## ⚠️ Known Operational Limitations

1. **Courier Pre-Shipment Inaccessibility:** Because courier partner assignment takes place after warehouse picking and label generation, carrier performance differentials cannot be exploited pre-shipment without inducing temporal target leakage.
2. **Pincode Sample Sparsity:** In our empirical dataset, 96.7% of pincodes had $<5$ orders. Geographic risk inference relies strictly on Empirical Bayes shrinkage toward the 28.4% national prior; raw pincode blocking is forbidden.
3. **Simulated Behavioral Conversion Benchmarks:** WhatsApp confirmation response rates (70%) and prepaid conversion rates (22%) represent realistic D2C industry benchmark assumptions. In live production rollout, actual response distributions must be tracked via the monitoring signals documented in `docs/FOUNDER_MEMO.md`.
4. **SQLite Concurrency Ceiling:** Parameterized SQLite operations handle single-writer concurrency comfortably up to ~5,000 orders/day. Beyond this scale, migrating to PostgreSQL is recommended for multi-warehouse distributed operations.

---

## 📄 Deliverable Documents

- **Executive Founder Memo:** Read [docs/FOUNDER_MEMO.md](docs/FOUNDER_MEMO.md) or download [docs/FOUNDER_MEMO.pdf](docs/FOUNDER_MEMO.pdf).
- **UI, UX & Design Decisions:** Read [docs/UI_DECISIONS.md](docs/UI_DECISIONS.md).
- **Architecture & Engineering Decisions:** Read [docs/DECISION_LOG.md](docs/DECISION_LOG.md).
- **AI Usage & Corrections Log:** Read [docs/AI_USAGE_LOG.md](docs/AI_USAGE_LOG.md).
- **QA Report & Test Matrix:** Read [docs/QA_REPORT.md](docs/QA_REPORT.md).
- **Manual QA Test Scripts:** Read [docs/MANUAL_QA.md](docs/MANUAL_QA.md).
- **Machine-Readable Replay Results:** Inspect [analysis/replay_results.json](analysis/replay_results.json).
