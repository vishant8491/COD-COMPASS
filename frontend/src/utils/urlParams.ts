/**
 * URL search params parser for tab navigation and filters.
 */

export interface ParsedUrlQuery {
  tab: string;
  action?: string;
  search: string;
  orderId?: string;
  datePreset?: string;
}

export const VALID_TABS = ['overview', 'orders', 'simulator', 'policy', 'analysis'];

/**
 * Parses URL search string into validated application navigation parameters.
 */
export function parseUrlQuery(searchString: string): ParsedUrlQuery {
  const params = new URLSearchParams(searchString);
  const tab = params.get('tab') || 'overview';
  const action = params.get('action') || undefined;
  const search = params.get('search') || '';
  const orderId = params.get('order_id') || undefined;
  const datePreset = params.get('date_preset') || undefined;

  return {
    tab: VALID_TABS.includes(tab) ? tab : 'overview',
    action,
    search,
    orderId,
    datePreset,
  };
}

