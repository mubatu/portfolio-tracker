/**
 * Market configurations
 * Add new markets here as your app expands
 */

export type Market = 'BIST';

export interface MarketConfig {
  value: Market;
  label: string;
  currency: string;    // ISO 4217 currency code
  country: string;     // For future use (flags, etc.)
}

export const MARKETS: MarketConfig[] = [
  { 
    value: 'BIST', 
    label: 'BIST (Borsa İstanbul)', 
    currency: 'TRY',
    country: 'TR',
  },
  // Future markets:
  // { value: 'NYSE', label: 'NYSE (New York Stock Exchange)', currency: 'USD', country: 'US' },
  // { value: 'NASDAQ', label: 'NASDAQ', currency: 'USD', country: 'US' },
  // { value: 'LSE', label: 'LSE (London Stock Exchange)', currency: 'GBP', country: 'GB' },
];

/**
 * Get currency code for a market
 */
export const getMarketCurrency = (marketCode: string): string => {
  const market = MARKETS.find((m) => m.value === marketCode);
  return market?.currency || 'TRY';
};

/**
 * Get market config by value
 */
export const getMarketConfig = (marketCode: string): MarketConfig | undefined => {
  return MARKETS.find((m) => m.value === marketCode);
};
