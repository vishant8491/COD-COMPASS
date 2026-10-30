import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { OverviewView } from './views/OverviewView';
import { OrdersView } from './views/OrdersView';
import { SimulatorView } from './views/SimulatorView';
import { PolicyView } from './views/PolicyView';
import { AnalysisView } from './views/AnalysisView';
import { DashboardOverview, ActionType } from './types';
import { fetchHealth, fetchOverview } from './api';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider, useToast } from './context/ToastContext';

const AppContent: React.FC = () => {
  const { showToast } = useToast();

  // Parse initial state from URL query parameters
  const parseUrlParams = () => {
    if (typeof window === 'undefined') {
      return { tab: 'overview', action: undefined, search: '', orderId: undefined };
    }
    const params = new URLSearchParams(window.location.search);
    const tabParam = params.get('tab') || 'overview';
    const actionParam = params.get('action') as ActionType | null;
    const searchParam = params.get('search') || '';
    const orderIdParam = params.get('order_id') || undefined;

    const validTabs = ['overview', 'orders', 'simulator', 'policy', 'analysis'];
    const activeTab = validTabs.includes(tabParam) ? tabParam : 'overview';

    return {
      tab: activeTab,
      action: actionParam || undefined,
      search: searchParam,
      orderId: orderIdParam,
    };
  };

  const initialParams = parseUrlParams();

  const [activeTab, setActiveTabState] = useState<string>(initialParams.tab);
  const [initialOrderFilter, setInitialOrderFilter] = useState<ActionType | undefined>(initialParams.action);
  const [initialOrderSearch, setInitialOrderSearch] = useState<string>(initialParams.search);
  const [simulatorOrderId, setSimulatorOrderId] = useState<string | undefined>(initialParams.orderId);
  const [datePreset, setDatePreset] = useState<string>('yesterday');

  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [isFallback, setIsFallback] = useState<boolean>(true);
  const [activePolicyVersion, setActivePolicyVersion] = useState<string>('default_v1');
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date());

  // Synchronize state with URL history
  const updateUrl = useCallback((tab: string, extraParams: Record<string, string | undefined> = {}) => {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);

    // Clean up or set params
    ['action', 'search', 'order_id'].forEach((key) => {
      url.searchParams.delete(key);
    });

    Object.entries(extraParams).forEach(([k, v]) => {
      if (v) url.searchParams.set(k, v);
    });

    window.history.pushState(null, '', url.toString());
  }, []);

  // Listen to browser Back/Forward (popstate)
  useEffect(() => {
    const handlePopState = () => {
      const parsed = parseUrlParams();
      setActiveTabState(parsed.tab);
      setInitialOrderFilter(parsed.action);
      setInitialOrderSearch(parsed.search);
      setSimulatorOrderId(parsed.orderId);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const loadData = async (isManual = false, preset: string = datePreset) => {
    try {
      const [h, o] = await Promise.all([fetchHealth(), fetchOverview(preset)]);
      setIsFallback(h.is_fallback);
      setActivePolicyVersion(h.active_policy || 'default_v1');
      setOverview(o);
      setLastRefreshedAt(new Date());
      if (isManual) {
        showToast('Dashboard data refreshed successfully', 'success');
      }
    } catch (err) {
      console.error('Failed to load initial COD Compass data', err);
      showToast('Failed to refresh data from server', 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData(false, datePreset);
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData(true, datePreset);
  };

  const handlePeriodChange = (newPreset: string) => {
    setDatePreset(newPreset);
    setLoading(true);
    loadData(false, newPreset);
  };

  const handleTabChange = (newTab: string) => {
    setActiveTabState(newTab);
    if (newTab !== 'orders') {
      setInitialOrderFilter(undefined);
      setInitialOrderSearch('');
    }
    updateUrl(newTab);
  };

  const handleNavigateToOrders = (actionFilter?: ActionType) => {
    setInitialOrderFilter(actionFilter);
    setActiveTabState('orders');
    updateUrl('orders', { action: actionFilter });
  };

  const handleNavigateToSimulator = (orderId?: string) => {
    setSimulatorOrderId(orderId);
    setActiveTabState('simulator');
    updateUrl('simulator', { order_id: orderId });
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 font-sans text-slate-900 dark:text-slate-100 selection:bg-teal-100 dark:selection:bg-teal-900/60 selection:text-teal-900 dark:selection:text-teal-100 transition-colors duration-150">
      <Header
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        isFallback={isFallback}
        activePolicyVersion={activePolicyVersion}
        onRefresh={handleRefresh}
        isRefreshing={refreshing}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        {activeTab === 'overview' && (
          <OverviewView
            data={overview}
            loading={loading}
            onNavigateToOrders={handleNavigateToOrders}
            onNavigateToSimulator={() => handleNavigateToSimulator()}
            lastRefreshedAt={lastRefreshedAt}
            selectedPeriod={datePreset}
            onPeriodChange={handlePeriodChange}
          />
        )}
        {activeTab === 'orders' && (
          <OrdersView
            initialActionFilter={initialOrderFilter}
            initialSearch={initialOrderSearch}
            onNavigateToSimulatorWithOrder={handleNavigateToSimulator}
          />
        )}
        {activeTab === 'simulator' && (
          <SimulatorView initialOrderId={simulatorOrderId} />
        )}
        {activeTab === 'policy' && <PolicyView />}
        {activeTab === 'analysis' && <AnalysisView />}
      </main>

      <footer className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-6 mt-12 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 dark:text-slate-400 gap-2">
          <div>
            <span className="font-bold text-slate-800 dark:text-slate-200">COD Compass</span> — Pre-shipment RTO intelligence for D2C brands.
          </div>
          <div className="flex items-center space-x-4">
            <span>Period: September 2026 Holdout</span>
            <span aria-hidden="true">•</span>
            <span>Baseline RTO: 28.4%</span>
            <span aria-hidden="true">•</span>
            <span className="font-mono">Direct RTO Loss: ₹169.40</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </ThemeProvider>
  );
};

export default App;
