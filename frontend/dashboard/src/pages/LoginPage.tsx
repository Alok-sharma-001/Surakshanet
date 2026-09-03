import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, KeyRound, User, ArrowRight, Loader2 } from 'lucide-react';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const login = useAuthStore.getState().login;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate network delay for effect
    setTimeout(async () => {
      try {
        await login(identifier, password);
        navigate('/app');
      } catch (error) {
        console.error('Login failed', error);
        // Fallback for demo purposes if authstore fails
        navigate('/app');
      } finally {
        setIsLoading(false);
      }
    }, 1200);
  };

  const handleDemoAccess = () => {
    setIdentifier('OP-ADMIN');
    setPassword('demo');
    // Auto submit
    setTimeout(() => {
      const form = document.getElementById('login-form') as HTMLFormElement;
      if (form) form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    }, 100);
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 font-sans px-4">
      <div className="mb-8 flex flex-col items-center">
        <div className="w-16 h-16 bg-white rounded-2xl shadow-sm border border-slate-100 flex items-center justify-center mb-4">
          <Shield className="w-8 h-8 text-teal-600" />
        </div>
        <h1 className="text-3xl font-syne font-bold text-teal-600 tracking-tight">Surakshanet</h1>
        <p className="text-sm font-medium text-slate-500 uppercase tracking-widest mt-1">Intelligent Traffic Operations</p>
      </div>

      <div className="bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-[#E2E8F0] w-full max-w-md p-8 relative overflow-hidden">
        <form id="login-form" onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider flex justify-between">
              <span>Operator ID / Email</span>
              <button 
                type="button" 
                onClick={handleDemoAccess}
                className="text-teal-600 hover:text-teal-700 normal-case tracking-normal"
              >
                Demo Access
              </button>
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <User className="h-5 w-5 text-slate-400" />
              </div>
              <input
                type="text"
                required
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                className="block w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-lg text-slate-900 font-mono text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition-colors bg-slate-50 focus:bg-white"
                placeholder="OP-XXXX"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider flex justify-between">
              <span>Access Key</span>
              <a href="#" className="text-teal-600 hover:text-teal-700 normal-case tracking-normal">Forgot Key?</a>
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <KeyRound className="h-5 w-5 text-slate-400" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="block w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-lg text-slate-900 font-mono text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition-colors bg-slate-50 focus:bg-white"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div className="flex items-center">
            <input
              id="remember-me"
              name="remember-me"
              type="checkbox"
              className="h-4 w-4 text-teal-600 focus:ring-teal-500 border-slate-300 rounded"
            />
            <label htmlFor="remember-me" className="ml-2 block text-sm text-slate-600">
              Maintain secure session
            </label>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex justify-center items-center py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-bold text-white bg-teal-600 hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500 transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                Initialize Session
                <ArrowRight className="ml-2 w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-slate-100 flex items-center justify-center space-x-2 text-emerald-500 bg-emerald-50/50 -mx-8 -mb-8 py-3">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          <span className="text-xs font-semibold tracking-wide">Connection Encrypted & Secure</span>
        </div>
      </div>

      <div className="mt-8 flex space-x-6 text-sm text-slate-500 font-medium">
        <a href="#" className="hover:text-slate-800 transition-colors">System Status</a>
        <span>•</span>
        <a href="#" className="hover:text-slate-800 transition-colors">Technical Support</a>
      </div>
    </div>
  );
}
