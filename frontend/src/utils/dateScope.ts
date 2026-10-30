/**
 * Date preset and filtering utilities for COD Compass dashboard.
 */

export type DatePresetKey = 'yesterday' | 'september_2026' | 'last_7_days' | 'all_time' | 'custom';

export interface DatePresetOption {
  key: DatePresetKey;
  label: string;
  description: string;
}

export const DATE_PRESETS: DatePresetOption[] = [
  {
    key: 'yesterday',
    label: 'Yesterday',
    description: 'Current real-time operations (Asia/Kolkata)',
  },
  {
    key: 'september_2026',
    label: 'September 2026 (Demo Cohort)',
    description: 'Frozen holdout replay benchmark (329 orders)',
  },
  {
    key: 'last_7_days',
    label: 'Last 7 Days',
    description: 'Trailing 7-day rolling performance',
  },
  {
    key: 'all_time',
    label: 'All Time',
    description: 'Full historical dataset (1,988 orders)',
  },
];

/**
 * Returns API query parameters for a given date preset.
 */
export function getDateScopeParams(preset: DatePresetKey): Record<string, string> {
  return { date_preset: preset };
}

