import axios from 'axios';
import { supabase } from './supabase';

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth token from Supabase
apiClient.interceptors.request.use(
  async (config) => {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for handling errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await supabase.auth.signOut();
      window.location.href = '/auth';
    }
    return Promise.reject(error);
  }
);

// ============================================
// API Functions
// ============================================

// Auth (email check only - actual auth handled by Supabase client)
export const checkEmailExists = async (email: string): Promise<{ exists: boolean }> => {
  const response = await apiClient.post('/auth/check-email', { email });
  return response.data;
};

export const getMe = async () => {
  const response = await apiClient.get('/auth/me');
  return response.data;
};

// Portfolio
export const getPortfolios = async () => {
  const response = await apiClient.get('/portfolios');
  return response.data;
};

export const getPortfolioById = async (id: string) => {
  const response = await apiClient.get(`/portfolios/${id}`);
  return response.data;
};

export const getPortfolioSummary = async (id: string) => {
  const response = await apiClient.get(`/portfolios/${id}/summary`);
  return response.data;
};

export const createPortfolio = async (name: string, description?: string) => {
  const response = await apiClient.post('/portfolios', { name, description });
  return response.data;
};

// Transactions
export const getTransactions = async (portfolioId: string) => {
  const response = await apiClient.get(`/portfolios/${portfolioId}/transactions`);
  return response.data;
};

export const createTransaction = async (
  portfolioId: string,
  data: {
    symbol: string;
    type: 'buy' | 'sell';
    quantity: number;
    price: number;
    date: string;
  }
) => {
  const response = await apiClient.post(`/portfolios/${portfolioId}/transactions`, data);
  return response.data;
};

// Stocks
export const searchStocks = async (query: string) => {
  const response = await apiClient.get(`/stocks/search?q=${query}`);
  return response.data;
};

export const getStockPrice = async (symbol: string) => {
  const response = await apiClient.get(`/stocks/${symbol}/price`);
  return response.data;
};
