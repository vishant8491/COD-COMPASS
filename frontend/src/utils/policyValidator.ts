/**
 * Policy ordering validation utilities for COD Compass.
 */

export interface PolicyValidationResult {
  isValid: boolean;
  errors: string[];
}

/**
 * Validates contiguous policy thresholds:
 * 0.0 <= low < confirm <= nudge <= 1.0 and hold >= nudge.
 */
export function validatePolicyThresholds(
  low: number,
  confirm: number,
  nudge: number,
  hold: number
): PolicyValidationResult {
  const errors: string[] = [];

  if (typeof low !== 'number' || isNaN(low) || low < 0 || low > 1) {
    errors.push('Low-risk threshold must be between 0.0 and 1.0');
  }
  if (typeof confirm !== 'number' || isNaN(confirm) || confirm < 0 || confirm > 1) {
    errors.push('Confirm threshold must be between 0.0 and 1.0');
  }
  if (typeof nudge !== 'number' || isNaN(nudge) || nudge < 0 || nudge > 1) {
    errors.push('Nudge threshold must be between 0.0 and 1.0');
  }
  if (typeof hold !== 'number' || isNaN(hold) || hold < 0 || hold > 1) {
    errors.push('Hold threshold must be between 0.0 and 1.0');
  }

  if (errors.length === 0) {
    if (low >= confirm) {
      errors.push('Low-risk threshold must be strictly less than Confirm threshold');
    }
    if (confirm > nudge) {
      errors.push('Confirm threshold must be less than or equal to Nudge threshold');
    }
    if (nudge > hold) {
      errors.push('Nudge threshold must be less than or equal to Hold threshold');
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

