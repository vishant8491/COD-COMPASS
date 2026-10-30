import React, { useState } from 'react';
import {
  Compass,
  ShieldCheck,
  AlertTriangle,
  Layers,
  MessageSquare,
  Sliders,
  BarChart3,
  RefreshCw,
  Menu,
  X,
} from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isFallback: boolean;
  activePolicyVersion: string;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  isFallback,
  activePolicyVersion,
  onRefresh,
  isRefreshing = false,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const tabs = [
    { id: 'overview', label: 'Founder Overview', icon: Layers },
    { id: 'orders', label: 'Orders Queue', icon: Compass },
    { id: 'simulator', label: 'Conversations & Payments', icon: MessageSquare },
    { id: 'policy', label: 'Policy Rules', icon: Sliders },
    { id: 'analysis', label: 'Dataset & Replay', icon: BarChart3 },
  ];

  const handleTabClick = (tabId: string) => {
    setActiveTab(tabId);
    setMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-30 bg-white/95 dark:bg-[#0F172A]/95 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 shadow-2xs transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3">
            <button
              onClick={() => handleTabClick('overview')}
              className="flex items-center space-x-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 rounded-lg p-1"
            >
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-teal-700 via-teal-600 to-teal-500 flex items-center justify-center shadow-md shadow-teal-700/20 text-white">
                <Compass className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-extrabold text-slate-900 dark:text-slate-50 tracking-tight text-lg">
                    COD Compass
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-950/80 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                    D2C Haircare
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:block">
                  Pre-shipment decision intelligence & unit-economic optimizer
                </p>
              </div>
            </button>
          </div>

          {/* Right Header Controls (Theme, Badges, Refresh, Mobile Hamburger) */}
          <div className="flex items-center space-x-2.5">
            {/* Engine Status / Fallback badge */}
            {isFallback ? (
              <span
                title="Running with server-side heuristics; no external LLM API key required."
                className="hidden md:inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800/80"
              >
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                <span>Offline Engine</span>
              </span>
            ) : (
              <span className="hidden md:inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/80">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                <span>Live LLM</span>
              </span>
            )}

            {/* Active Policy Pill */}
            <span className="hidden lg:inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-mono font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              Policy: {activePolicyVersion}
            </span>

            {/* Light / Dark / System Theme Switcher */}
            <ThemeToggle />

            {/* Manual Sync / Refresh */}
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              title="Refresh Dashboard and Orders"
              aria-label="Refresh Dashboard Data"
              className="p-2 text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-teal-600' : ''}`} />
            </button>

            {/* Mobile Hamburger Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle navigation menu"
              aria-expanded={mobileMenuOpen}
              className="md:hidden p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Desktop Navigation Tabs */}
        <nav
          role="tablist"
          aria-label="Main Navigation"
          className="hidden md:flex space-x-1 overflow-x-auto pb-0 scrollbar-none border-t border-slate-100 dark:border-slate-800 pt-1"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                role="tab"
                id={`tab-${tab.id}`}
                aria-selected={isActive}
                aria-controls={`panel-${tab.id}`}
                onClick={() => handleTabClick(tab.id)}
                className={`flex items-center space-x-2 px-3.5 py-2.5 text-xs font-semibold rounded-lg transition-all whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 ${
                  isActive
                    ? 'bg-teal-50 dark:bg-teal-950/70 text-teal-800 dark:text-teal-200 shadow-2xs border-b-2 border-teal-600 dark:border-teal-400'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800/60'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-teal-600 dark:text-teal-400' : 'text-slate-400 dark:text-slate-500'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0F172A] px-4 pt-2 pb-4 space-y-1 shadow-lg animate-in slide-in-from-top-2 duration-150">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab.id)}
                className={`w-full flex items-center space-x-3 px-3.5 py-3 text-sm font-semibold rounded-xl text-left transition-colors ${
                  isActive
                    ? 'bg-teal-50 dark:bg-teal-950/70 text-teal-800 dark:text-teal-200'
                    : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-teal-600 dark:text-teal-400' : 'text-slate-400 dark:text-slate-500'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 text-xs text-slate-500 dark:text-slate-400 flex items-center justify-between px-2">
            <span>Policy: {activePolicyVersion}</span>
            <span>{isFallback ? 'Offline Mode' : 'Live LLM'}</span>
          </div>
        </div>
      )}
    </header>
  );
};
