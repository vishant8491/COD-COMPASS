# AI Usage & Correction Log — COD Compass

**Target System:** COD Compass Pre-Shipment Optimization Engine  
**Version:** 1.0.0 (Production Candidate)  
**Date:** October 30, 2026  
**Audience:** Founders, Engineering Reviewers, Evaluators  

This document provides full transparency into the AI tools used during the development of COD Compass, the specific engineering tasks assisted, and—crucially—**genuine weak, flawed, or incorrect AI outputs encountered during development, along with how they were caught and corrected using concrete codebase evidence**.

---

## 1. AI Tools & Development Environment

- **Primary AI Assistant:** Antigravity (Google DeepMind advanced agentic coding assistant).
- **Underlying Models:** Gemini 2.5 Pro and Gemini 2.5 Flash.
- **Execution Shell:** Windows PowerShell in a secure sandboxed environment.
- **Assisted Areas:**
  - Scaffolding typed Pydantic V2 request/response schemas (`backend/app/models/schemas.py`) and TypeScript interfaces (`frontend/src/types.ts`).
  - ReportLab flowable coordinate geometry, table styling, and two-page constraint budgeting for [`docs/FOUNDER_MEMO.pdf`](docs/FOUNDER_MEMO.pdf).
  - Accessible React Tailwind CSS UI components (`Modal.tsx`, `Skeleton.tsx`, `EmptyState.tsx`, `ThemeToggle.tsx`).
  - Stage 1 exploratory data analysis scripts and Wilson score confidence interval calculations.

---

## 2. Genuine Flawed AI Outputs Identified & Corrected

### Case 1: Double-Counting Sunk Customer Acquisition Cost (CAC)
- **Flawed AI Output:**  
  When writing the pre-shipment action contribution formulas in `backend/app/services/financial_model.py`, the AI initially subtracted the ₹300 customer acquisition cost (CAC) from each pre-shipment action's delivered contribution:
  $$\text{Incremental Contribution} = \text{Order Value} \times 0.62 - \text{Shipping} - \text{Packaging} - \text{CAC}$$
- **Evidence & How Caught:**  
  Reviewing the financial bridge output for a baseline ₹649 order revealed that delivered contribution collapsed from **₹312.38 down to ₹12.38**. This caused the decision engine to recommend cancelling or holding almost all orders with even slight risk (10%–15% RTO), as any non-zero risk appeared to turn the order cash-negative.
- **Correction Applied:**  
  The AI's managerial accounting was rejected. The ₹300 acquisition cost was spent at ad click time on Meta/Google Ads and is completely sunk prior to warehouse dispatch. Cancelling an order cannot recover the ₹300; it merely destroys the ₹312.38 in delivered gross profit. The code was updated to treat CAC as sunk, established the mathematical **value-dependent break-even hurdle** ($P_{\text{break-even}} = \text{Delivered Margin} / (\text{Delivered Margin} + ₹169.40)$), and created a separate metric named *"Acquisition Spend at Risk"* $((1 - P_{\text{RTO}}) \times \text{CAC})$ to protect marketing spend.

---

### Case 2: Starlette `TestClient` / ASGI Thread Pool Deadlock in Sandbox
- **Flawed AI Output:**  
  In `tests/test_api.py`, the AI generated automated API test suites using Starlette's standard `TestClient(app)` to issue HTTP GET and POST requests against the FastAPI backend.
- **Evidence & How Caught:**  
  Running `pytest -v` caused the test suite to hang indefinitely on Windows sandbox threads inside `anyio.to_thread.run_sync` due to an event loop deadlock between Starlette's synchronous test harness worker threads and the asyncio loop under sandbox process constraints.
- **Correction Applied:**  
  Identified that FastAPI route handlers are pure Python functions that can be tested deterministically as handler unit tests (`list_orders(...)`, `get_dashboard_overview(...)`, `preview_policy_impact(...)`). Documented honestly in the QA report that direct handler calls verify schema and business logic, while full ASGI HTTP tests using httpx / TestClient require unsandboxed socket/thread networking.

---

### Case 3: Policy Threshold Boundary Gap (55%–65% Unhandled Region)
- **Flawed AI Output:**  
  In `backend/app/services/decision_engine.py`, the AI configured threshold checks using disjoint cutoffs:
  ```python
  elif risk_score <= policy.nudge_threshold:  # 0.55
      recommended_action = ActionType.NUDGE_PREPAID
  else:
      # Extreme risk (> hold_threshold)
      recommended_action = ActionType.HOLD
  ```
  While in documentation and policy settings, `hold_threshold` was set to 0.65 or 0.70.
- **Evidence & How Caught:**  
  Auditing orders with risk scores between 0.55 and 0.65 (e.g., 0.58 or 0.60) revealed that they fell into the `else:` branch, setting the action to `HOLD` while generating a contradictory explanation claiming:
  `High RTO risk (58.0% >= 65.0%)` (which is mathematically false: 58% is not $\ge$ 65%).
- **Correction Applied:**  
  Refactored the decision engine to use contiguous, gap-free boundaries:
  - Low Risk: $P \le 0.20 \implies$ `SHIP_AS_IS`
  - Moderate Risk: $0.20 < P \le 0.35 \implies$ `CONFIRM`
  - High Risk: $0.35 < P \le 0.65 \implies$ `NUDGE_PREPAID`
  - Critical Risk: $P > 0.65 \implies$ `HOLD`
  Aligned database and schema defaults so every continuous risk score maps deterministically to exactly one bucket.

---

### Case 4: Cross-Row Address Matching Bug & Wald Normal Approximation
- **Flawed AI Output:**  
  In `analysis/exploratory_analysis.py`, the AI's address quality detection line compared address text to city using:
  ```python
  a.lower() == str(df.loc[df["address_clean"] == a, "city"].values[0]).lower()
  ```
  And calculated confidence intervals using the Wald normal approximation ($\hat{p} \pm 1.96 \sqrt{\hat{p}(1-\hat{p})/n}$) while labeling them as "Wilson score intervals".
- **Evidence & How Caught:**  
  1. If two rows in different cities had generic addresses (e.g., "Main Road"), `df.loc[...]["city"].values[0]` compared the row's address against another order's city.
  2. For small segments (such as 2+ prior RTOs, $n=34, k=26$), the Wald normal approximation produced intervals exceeding the sample bounds and failed to adjust for skewness.
- **Correction Applied:**  
  1. Rewrote address quality to compare each row strictly against its own city: `row['address'].strip().lower() == row['city'].strip().lower()`.
  2. Implemented the exact Wilson score interval formula ($z=1.95996$), correctly adjusting center and margin for binomial proportions.

---

### Case 5: ReportLab Indian Rupee Symbol Encoding Artifact
- **Flawed AI Output:**  
  When generating `docs/FOUNDER_MEMO.pdf`, the AI initially configured ReportLab with standard Type 1 `Helvetica` and `Helvetica-Bold` fonts, writing `"₹169.40"`.
- **Evidence & How Caught:**  
  Text inspection using `pypdf` revealed that the Indian Rupee symbol `₹` (Unicode U+20B9) was rendered as black squares (`■`) (e.g. `■169.40 in unrecoverable cash`). Standard Type 1 PDF fonts only support Latin-1 / WinAnsiEncoding and lack glyph U+20B9.
- **Correction Applied:**  
  Registered native Windows TrueType font `Arial` (`C:/Windows/Fonts/arial.ttf`) and `Arial-Bold` (`C:/Windows/Fonts/arialbd.ttf`) with ReportLab's `pdfmetrics`. This enabled native vector rendering of the `₹` glyph without encoding squares, backed by an automated fallback to `"Rs."` on non-Windows environments.

---

### Case 6: Overly Broad Address Regex (`^near`) & Accounting Identity Discrepancies
- **Flawed AI Output:**  
  1. In `extract_address_features`, the AI included `r"^near"` in suspicious patterns, flagging complete landmark-first addresses like `"Near City Mall, House 42, MG Road, Sector 10"` as suspicious.
  2. In `evaluate_order_actions`, the prepaid action charged unconditional ₹25 packaging even for unconfirmed/unshipped orders, and subtracted messaging twice for fallback nonconverters.
- **Evidence & How Caught:**  
  1. Regression testing complete Indian landmark-first addresses flagged false positives.
  2. Line-item summation check `revenue - cogs - forward - return - packaging - damage - messaging - discount - fees` did not match `expected_net_contribution`.
- **Correction Applied:**  
  1. Replaced `r"^near"` with `is_vague_landmark_only` that strictly checks if the entire address is a short landmark phrase lacking digits and under 25 characters.
  2. Weight packaging by orders actually shipped, account for PG fees and discounts as explicit lines, charge messaging once, and guarantee the accounting identity holds within 0.01 tolerance for every pre-shipment action.

---

### Case 7: Intent Classification Negation & Conflicting Requests
- **Flawed AI Output:**  
  In `backend/app/services/llm_adapter.py`, the AI generated intent classification using raw substring searches:
  ```python
  if any(w in text for w in ["cancel", "no", "nahi"]):
      return "CANCEL"
  ```
- **Evidence & How Caught:**  
  A customer message saying *"please don't cancel my order, I will receive it tomorrow"* matched the substring `"cancel"`, triggering an unintended cancellation recommendation on a genuine confirmed order. Similarly, *"yes, but please change my address to House 5"* matched `"yes"` and ignored the critical address correction.
- **Correction Applied:**  
  Replaced substring matches with token-boundary regex patterns (`\b(?:cancel|cancellation|radd)\b`), added explicit negation detection (`don't cancel`, `do not cancel`, `mat karna`), and gave priority to address correction intents over generic confirmation phrases.

---

### Case 8: Frontend Test Duplication vs. Production Import
- **Flawed AI Output:**  
  In `tests/test_frontend_logic.mjs`, the AI redefined copies of utility functions (`maskPhone`, `validatePolicyThresholds`, etc.) directly inside the test script instead of importing them from frontend source code.
- **Evidence & How Caught:**  
  Auditing the test suite revealed that `tests/test_frontend_logic.mjs` was testing duplicate code; changes to production UI logic would not be caught by the test runner.
- **Correction Applied:**  
  Modularized shared utilities into production TypeScript files under `frontend/src/utils/` (`formatters.ts`, `policyValidator.ts`, `themeResolver.ts`, `urlParams.ts`, `dateScope.ts`). Configured Node 22 native type-stripping (`node --experimental-strip-types --test`) to import directly from the real production files in `npm test`.

---

### Case 9: Production WhatsApp NLP Regressions on Negated Confirmations & Cancellation Intent Boundaries
- **Flawed AI Output:**  
  In `backend/app/services/llm_adapter.py`, the AI's heuristic NLP parser initially lacked negation handling for confirmation words (mapping `"do not confirm"` to `CONFIRM_ORDER`), and then over-corrected by treating `"do not confirm"` as `CANCEL_ORDER`. Concurrently, `"no payment link, cancel it"` was misclassified as a payment inquiry due to the substring `payment link`.
- **Evidence & How Caught:**  
  Auditing customer interaction flows revealed that a customer replying `"do not confirm"` may simply be hesitating or waiting to verify details rather than cancelling. Automatically cancelling their order destroyed delivered gross profit on viable orders. Furthermore, `"no payment link, cancel it"` contains an explicit cancellation command that was previously swallowed by the payment link regex.
- **Correction Applied:**  
  Distinguished negated confirmation from explicit cancellation:
  1. *Negated confirmation alone* (`"do not confirm"`, `"don't confirm"`) returns `AMBIGUOUS_OR_UNRESOLVED` with action `HOLD`, asking the customer to clarify whether they wish to update details, switch payment methods, or cancel.
  2. *Only explicit cancellation requests* (`"cancel"`, `"cancel it"`, `"cancel kardo"`, `"no payment link, cancel it"`) cancel the order (`CANCEL_ORDER`).
  3. Preserved priority for address modifications (`ADDRESS_UPDATE`), payment inquiries (`ASK_DISCOUNT_OR_PAYMENT`), and terminal state protections against reopening cancelled orders.
  Verified with automated regression tests in `tests/test_defects_regression.py` and simulator lifecycle tests in `tests/test_simulator.py`.

---

### Case 10: Sticky Fallback State Leak & Unvalidated LLM Response Schema
- **Flawed AI Output:**  
  In `LLMAdapterService`, after any successful live provider call, the service mutated an instance attribute `self.is_fallback = False`. In subsequent fallback scenarios (e.g. timeout or malformed JSON), the code returned `"is_fallback": self.is_fallback`, which retained `False` from the prior call, falsely claiming that a fallback response came from the live LLM. Additionally, non-numeric LLM output (e.g. `completeness_score="invalid"`) crashed route handlers with unhandled `ValueError`.
- **Evidence & How Caught:**  
  Executing `test_17_llm_strict_validation_and_fallback_safety` revealed that fallback responses had `is_fallback=False` after a live call, and malformed provider responses caused 500 errors.
- **Correction Applied:**  
  Strictly validated LLM outputs (requiring `0.0 <= completeness_score <= 1.0` and valid actions/intents), wrapped parsing in defensive `try/except` blocks, and guaranteed that all fallback return dictionaries explicitly set `"is_fallback": True`.

---

### Case 11: Nested Analysis Replay Schema Mismatch & Unconditional Positive Formatting
- **Flawed AI Output:**  
  In `backend/app/api/endpoints.py`, `get_analysis_report` retrieved scenario data via `data.get("scenarios", {})`, but `analysis/replay_results.json` placed scenario objects inside `september_2026_holdout_replay["scenarios"]`. Concurrently, `AnalysisView.tsx` unconditionally rendered net monthly gains with `+₹{s.net_monthly_gain_rupees.toLocaleString()}`, displaying negative scenarios as `+₹-69,537.93`.
- **Evidence & How Caught:**  
  The frontend Analysis tab rendered an empty backtest table with 0 rows because the API returned an empty object. When manually populating mock data, negative monetary projections displayed contradictory `+₹-` formatting.
- **Correction Applied:**  
  Traversed the nested dictionary `data.get("september_2026_holdout_replay", {}).get("scenarios", {})` with comprehensive fallback defaults, updated `AnalysisView.tsx` to conditionally format negative numbers with `-₹...` in red styling, and added automated test `test_analysis_report_frontend_contract`.

---

## 3. Missing Evidence Disclosures

To adhere strictly to transparent disclosure standards, the following data is flagged as not present in workspace files:
- **Token Usage / Prompt Latency Logs:** Antigravity does not persist raw token usage or API prompt cost metrics to the local disk repository.
- **External Paid LLM Logs:** No third-party LLM APIs (OpenAI GPT-4, Anthropic Claude) were called in production; all address sanitization, risk evaluation, and conversational replies run via local deterministic Python implementations.
