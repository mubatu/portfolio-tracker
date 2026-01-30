import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, ProtectedLayout, ThemeProvider } from '@/hooks';
import { LandingPage, LoginPage, RegisterPage } from '@/pages/public';
import { Dashboard, PortfolioDetail, Profile } from '@/pages/private';
import '@/i18n';
import './index.css';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              {/* Public Routes */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              {/* Private Routes */}
              <Route
                path="/dashboard"
                element={
                  <ProtectedLayout>
                    <Dashboard />
                  </ProtectedLayout>
                }
              />
              <Route
                path="/portfolio/:id"
                element={
                  <ProtectedLayout>
                    <PortfolioDetail />
                  </ProtectedLayout>
                }
              />
              <Route
                path="/profile"
                element={
                  <ProtectedLayout>
                    <Profile />
                  </ProtectedLayout>
                }
              />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
