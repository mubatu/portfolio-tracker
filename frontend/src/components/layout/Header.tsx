import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TrendingUp, Moon, Sun, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/hooks/useTheme';
import { useAuth } from '@/hooks/useAuth';

export function Header() {
  const { t } = useTranslation();
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated, signOut, user } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate('/');
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-primary" style={{ color: 'hsl(var(--primary))' }} />
          <span className="text-xl font-bold">{t('common.appName')}</span>
        </Link>
        
        <nav className="flex items-center gap-2">
          {isAuthenticated ? (
            <>
              <Link to="/dashboard">
                <Button variant="ghost">{t('common.dashboard')}</Button>
              </Link>
              <span className="text-sm text-muted-foreground hidden sm:inline">
                {user?.email}
              </span>
              <Button 
                variant="ghost" 
                size="icon"
                onClick={handleSignOut}
                aria-label="Sign out"
              >
                <LogOut className="h-5 w-5" />
              </Button>
            </>
          ) : (
            <Link to="/auth">
              <Button variant="default">{t('common.signIn')}</Button>
            </Link>
          )}
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <Sun className="h-5 w-5" />
            ) : (
              <Moon className="h-5 w-5" />
            )}
          </Button>
        </nav>
      </div>
    </header>
  );
}
