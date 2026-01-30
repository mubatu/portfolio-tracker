import axios from 'axios';

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
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
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ============================================
// API Functions
// ============================================

// Auth
export const login = async (email: string, password: string) => {
  const response = await apiClient.post('/auth/login', { email, password });
  return response.data;
};

export const register = async (email: string, password: string, name: string) => {
  const response = await apiClient.post('/auth/register', { email, password, name });
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
