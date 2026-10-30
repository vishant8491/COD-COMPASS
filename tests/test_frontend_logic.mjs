import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// Direct imports from production frontend TypeScript utilities
import {
  maskPhone,
  formatRupees,
  formatPercent,
  formatDateIST,
} from '../frontend/src/utils/formatters.ts';

import {
  validatePolicyThresholds,
} from '../frontend/src/utils/policyValidator.ts';

import {
  resolveTheme,
} from '../frontend/src/utils/themeResolver.ts';

import {
  parseUrlQuery,
  VALID_TABS,
} from '../frontend/src/utils/urlParams.ts';

import {
  DATE_PRESETS,
  getDateScopeParams,
} from '../frontend/src/utils/dateScope.ts';

describe('COD Compass Production Frontend Utilities Unit Tests', () => {
  describe('PII Masking (formatters.ts)', () => {
    it('masks 10-digit Indian mobile numbers to first 5 digits followed by 5 asterisks', () => {
      assert.strictEqual(maskPhone('9876543210'), '98765*****');
      assert.strictEqual(maskPhone('+919876543210'), '91987*****');
      assert.strictEqual(maskPhone('98765 43210'), '98765*****');
    });

    it('handles short or missing numbers gracefully', () => {
      assert.strictEqual(maskPhone('123'), '*****');
      assert.strictEqual(maskPhone(''), '—');
      assert.strictEqual(maskPhone(null), '—');
      assert.strictEqual(maskPhone(undefined), '—');
    });
  });

  describe('Currency & Percentage Formatting (formatters.ts)', () => {
    it('formats Indian rupee values with comma separation', () => {
      const formatted = formatRupees(1234567.89, { decimals: 2 });
      assert.strictEqual(formatted, '₹12,34,567.89');
    });

    it('formats negative numbers cleanly with minus sign', () => {
      const formattedNegative = formatRupees(-91.61, { decimals: 2, showSign: true });
      assert.strictEqual(formattedNegative, '-₹91.61');
    });

    it('formats positive delta with plus sign when requested', () => {
      const formattedPositive = formatRupees(1500, { showSign: true });
      assert.strictEqual(formattedPositive, '+₹1,500');
    });

    it('formats percentages accurately', () => {
      assert.strictEqual(formatPercent(0.284, 1), '28.4%');
      assert.strictEqual(formatPercent(0, 1), '0.0%');
      assert.strictEqual(formatPercent(1.0, 0), '100%');
    });

    it('formats IST timestamps', () => {
      const formatted = formatDateIST('2026-09-15T10:30:00Z');
      assert.ok(formatted.includes('2026'));
      assert.strictEqual(formatDateIST(null), '—');
    });
  });

  describe('Policy Threshold Ordering Validation (policyValidator.ts)', () => {
    it('validates strictly ascending default policy thresholds', () => {
      const res = validatePolicyThresholds(0.18, 0.40, 0.70, 0.90);
      assert.strictEqual(res.isValid, true);
      assert.strictEqual(res.errors.length, 0);
    });

    it('rejects inverted thresholds (low >= confirm)', () => {
      const res = validatePolicyThresholds(0.45, 0.40, 0.70, 0.90);
      assert.strictEqual(res.isValid, false);
      assert.ok(res.errors.some(e => e.includes('Low-risk threshold must be strictly less than Confirm')));
    });

    it('rejects out of bounds thresholds (< 0 or > 1)', () => {
      const res = validatePolicyThresholds(-0.1, 0.4, 0.7, 1.2);
      assert.strictEqual(res.isValid, false);
      assert.strictEqual(res.errors.length, 2);
    });
  });

  describe('Theme Resolution Logic (themeResolver.ts)', () => {
    it('resolves explicit light theme preference regardless of system setting', () => {
      assert.strictEqual(resolveTheme('light', true), 'light');
      assert.strictEqual(resolveTheme('light', false), 'light');
    });

    it('resolves explicit dark theme preference regardless of system setting', () => {
      assert.strictEqual(resolveTheme('dark', false), 'dark');
      assert.strictEqual(resolveTheme('dark', true), 'dark');
    });

    it('follows system dark mode when preference is system', () => {
      assert.strictEqual(resolveTheme('system', true), 'dark');
      assert.strictEqual(resolveTheme('system', false), 'light');
    });
  });

  describe('URL Navigation Parameter Synchronization (urlParams.ts)', () => {
    it('parses valid tab, action, date_preset, and order_id from search query', () => {
      const parsed = parseUrlQuery('?tab=orders&action=HOLD&order_id=ORD-2026-09-0001&date_preset=september_2026');
      assert.strictEqual(parsed.tab, 'orders');
      assert.strictEqual(parsed.action, 'HOLD');
      assert.strictEqual(parsed.orderId, 'ORD-2026-09-0001');
      assert.strictEqual(parsed.datePreset, 'september_2026');
    });

    it('falls back to overview if invalid tab name is provided', () => {
      const parsed = parseUrlQuery('?tab=unknown_tab_name');
      assert.strictEqual(parsed.tab, 'overview');
    });

    it('includes all primary tabs in VALID_TABS', () => {
      assert.deepStrictEqual(VALID_TABS, ['overview', 'orders', 'simulator', 'policy', 'analysis']);
    });
  });

  describe('Date Scope Presets (dateScope.ts)', () => {
    it('defaults to yesterday as the initial preset', () => {
      assert.strictEqual(DATE_PRESETS[0].key, 'yesterday');
      assert.strictEqual(DATE_PRESETS[0].label, 'Yesterday');
    });

    it('includes September 2026 benchmark cohort', () => {
      const sepPreset = DATE_PRESETS.find(p => p.key === 'september_2026');
      assert.ok(sepPreset);
      assert.ok(sepPreset.label.includes('September 2026'));
    });

    it('generates correct API query parameters', () => {
      const params = getDateScopeParams('yesterday');
      assert.deepStrictEqual(params, { date_preset: 'yesterday' });
    });
  });
});
