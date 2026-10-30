/**
 * Formatting and PII-masking utilities for COD Compass frontend.
 */

/**
 * Masks phone numbers to first 5 digits followed by 5 asterisks for PII safety.
 * Returns '—' for missing or empty phone numbers.
 */
export function maskPhone(phone: string | null | undefined): string {
  if (!phone) return '—';
  const clean = phone.replace(/\D/g, '');
  if (clean.length < 5) return '*****';
  return clean.slice(0, 5) + '*****';
}

/**
 * Formats a rupee amount in Indian numbering system (e.g., ₹1,23,456).
 * Supports explicit sign prefix (+₹... or -₹...) for incremental financial deltas.
 */
export function formatRupees(
  amount: number,
  options?: { showSign?: boolean; decimals?: number }
): string {
  if (typeof amount !== 'number' || isNaN(amount)) {
    return '₹0';
  }
  const decimals = options?.decimals ?? 0;
  const isNegative = amount < 0;
  const absVal = Math.abs(amount);
  const formattedAbs = absVal.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  if (isNegative) {
    return `-₹${formattedAbs}`;
  }
  if (options?.showSign && amount > 0) {
    return `+₹${formattedAbs}`;
  }
  return `₹${formattedAbs}`;
}

/**
 * Formats a decimal fraction (0.0 to 1.0) into a percentage string (e.g. 28.4%).
 */
export function formatPercent(rate: number, decimals: number = 1): string {
  if (typeof rate !== 'number' || isNaN(rate)) {
    return '0.0%';
  }
  const pct = rate * 100;
  return `${pct.toFixed(decimals)}%`;
}

/**
 * Formats ISO datetime string to IST human-readable format.
 */
export function formatDateIST(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return dateStr;
  }
}

