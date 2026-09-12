import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, User, Eye, EyeOff, Loader2, AlertCircle, Mountain, UserPlus, Mail } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export function LoginPage() {
  const { login, signup, signupStatus, refreshSignupStatus } = useAuth();
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [signupName, setSignupName] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupRole, setSignupRole] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [focused, setFocused] = useState<'username' | 'password' | 'name' | 'email' | 'role' | null>(null);
  const usernameRef = useRef<HTMLInputElement>(null);

  const signupStatusOpen = signupStatus?.open ?? true;

  useEffect(() => {
    usernameRef.current?.focus();
    void refreshSignupStatus();
  }, [refreshSignupStatus]);

  const switchMode = (next: 'signin' | 'signup') => {
    setMode(next);
    setError('');
    setLoading(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (mode === 'signup') {
      if (!signupName.trim() || !signupEmail.trim() || !signupPassword.trim()) {
        setError('Please fill in your name, email and a password.');
        return;
      }
      setLoading(true);
      const result = await signup(signupName.trim(), signupEmail.trim(), signupPassword, signupRole.trim() || 'Team Member');
      if (result.error) {
        setError(result.error);
        setLoading(false);
      }
      return;
    }
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username/email and password.');
      return;
    }
    setLoading(true);
    const result = await login(username.trim(), password);
    if (result.error) {
      setError(result.error);
      setLoading(false);
    }
  };

  return (
    <div className="h-full w-full relative overflow-hidden bg-[#0a0a1a]">
      {/* Background aurora */}
      <div className="aurora-blob w-[500px] h-[500px] -top-40 -left-32 bg-sky-600/30" />
      <div className="aurora-blob w-[450px] h-[450px] -bottom-40 -right-32 bg-violet-600/30" style={{ animationDelay: '-6s' }} />
      <div className="aurora-blob w-[300px] h-[300px] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-indigo-600/20" style={{ animationDelay: '-12s' }} />

      {/* Scrollable viewport — card centers when space allows, scrolls on short screens so signup never traps the user. */}
      <div className="absolute inset-0 overflow-y-auto snap-top thin-scrollbar">
        <div className="min-h-full flex items-center justify-center py-6 sm:py-10 px-4 pb-safe pt-safe" style={{ boxSizing: 'border-box' }}>
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30, delay: 0.1 }}
            className="relative z-10 w-full max-w-[400px]"
          >
            <div className="bg-[#14142b]/80 backdrop-blur-3xl rounded-[28px] border border-white/[0.06] shadow-[0_24px_80px_rgba(0,0,0,0.5)] p-6 sm:p-10">
              {/* Logo */}
              <div className="flex flex-col items-center mb-7 sm:mb-8">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 20, delay: 0.2 }}
                  className="w-14 h-14 sm:w-16 sm:h-16 rounded-[20px] bg-gradient-to-br from-sky-500 via-indigo-500 to-violet-600 flex items-center justify-center shadow-[0_12px_40px_rgba(59,130,246,0.5)] mb-4"
                >
                  <Mountain className="w-7 h-7 sm:w-8 sm:h-8 text-white" />
                </motion.div>
                <motion.h1
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.3 }}
                  className="text-[20px] sm:text-[22px] font-bold text-white tracking-tight"
                >
                  AI Mining OS
                </motion.h1>
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.35 }}
                  className="text-[13px] text-zinc-500 mt-1 text-center"
                >
                  {mode === 'signin' ? 'Sign in to your account' : 'Join the team'}
                </motion.p>
              </div>

          {/* Mode switch */}
          <div className="flex items-center gap-1 p-1 rounded-2xl bg-white/[0.04] border border-white/[0.06] mb-5">
            <button
              type="button"
              onClick={() => switchMode('signin')}
              className={`flex-1 py-2.5 sm:py-3 rounded-xl text-[13px] font-semibold transition-all duration-200 ${
                mode === 'signin' ? 'bg-gradient-to-r from-sky-500/30 to-violet-600/30 text-white shadow-inner' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Sign In
            </button>
            {signupStatusOpen && (
              <button
                type="button"
                onClick={() => switchMode('signup')}
                className={`flex-1 py-2.5 sm:py-3 rounded-xl text-[13px] font-semibold transition-all duration-200 ${
                  mode === 'signup' ? 'bg-gradient-to-r from-sky-500/30 to-violet-600/30 text-white shadow-inner' : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                Sign Up
              </button>
            )}
          </div>

          <AnimatePresence mode="wait">
          {signupStatusOpen && (
            <motion.div
              key="slots"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="flex items-center justify-between px-3 py-2 mb-4 rounded-xl bg-sky-500/[0.07] border border-sky-500/15">
                <span className="text-[11px] text-sky-200/80 font-medium">Team slots open</span>
                <span className="text-[11px] font-mono text-sky-300 tabular">
                  {signupStatus?.remaining ?? '—'} / {signupStatus?.total ?? 6} remaining
                </span>
              </div>
            </motion.div>
          )}
          </AnimatePresence>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username / email */}
            {mode === 'signin' ? (
            <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}>
              <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider ml-1 mb-1.5 block">
                Username or Email
              </label>
              <div className={`relative rounded-2xl transition-all duration-200 ${
                focused === 'username' ? 'ring-2 ring-sky-500/40' : ''
              }`}>
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
                  <User className={`w-4 h-4 transition-colors ${focused === 'username' ? 'text-sky-400' : 'text-zinc-600'}`} />
                </div>
                <input
                  ref={usernameRef}
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onFocus={() => setFocused('username')}
                  onBlur={() => setFocused(null)}
                  placeholder="Enter username or email"
                  autoComplete="username"
                  className="w-full pl-10 pr-4 py-3.5 bg-white/[0.04] border border-white/[0.08] rounded-2xl text-[15px] text-white placeholder:text-zinc-600 focus:outline-none transition-colors"
                />
              </div>
            </motion.div>
            ) : (
              <>
                <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}>
                  <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider ml-1 mb-1.5 block">
                    Full Name
                  </label>
                  <div className={`relative rounded-2xl transition-all duration-200 ${focused === 'name' ? 'ring-2 ring-sky-500/40' : ''}`}>
                    <div className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
                      <User className={`w-4 h-4 transition-colors ${focused === 'name' ? 'text-sky-400' : 'text-zinc-600'}`} />
                    </div>
                    <input
                      type="text"
                      value={signupName}
                      onChange={(e) => setSignupName(e.target.value)}
                      onFocus={() => setFocused('name')}
                      onBlur={() => setFocused(null)}
                      placeholder="Your full name"
                      autoComplete="name"
                      className="w-full pl-10 pr-4 py-3.5 bg-white/[0.04] border border-white/[0.08] rounded-2xl text-[15px] text-white placeholder:text-zinc-600 focus:outline-none transition-colors"
                    />
                  </div>
                </motion.div>

                <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.45 }}>
                  <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider ml-1 mb-1.5 block">
                    Email
                  </label>
                  <div className={`relative rounded-2xl transition-all duration-200 ${focused === 'email' ? 'ring-2 ring-sky-500/40' : ''}`}>
                    <div className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
                      <Mail className={`w-4 h-4 transition-colors ${focused === 'email' ? 'text-sky-400' : 'text-zinc-600'}`} />
                    </div>
                    <input
                      type="email"
                      value={signupEmail}
                      onChange={(e) => setSignupEmail(e.target.value)}
                      onFocus={() => setFocused('email')}
                      onBlur={() => setFocused(null)}
                      placeholder="you@company.com"
                      autoComplete="email"
                      className="w-full pl-10 pr-4 py-3.5 bg-white/[0.04] border border-white/[0.08] rounded-2xl text-[15px] text-white placeholder:text-zinc-600 focus:outline-none transition-colors"
                    />
                  </div>
                </motion.div>

                <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 }}>
                  <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider ml-1 mb-1.5 block">
                    Your Role
                  </label>
                  <div className={`relative rounded-2xl transition-all duration-200 ${focused === 'role' ? 'ring-2 ring-sky-500/40' : ''}`}>
                    <div className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
                      <UserPlus className={`w-4 h-4 transition-colors ${focused === 'role' ? 'text-sky-400' : 'text-zinc-600'}`} />
                    </div>
                    <input
                      type="text"
                      value={signupRole}
                      onChange={(e) => setSignupRole(e.target.value)}
                      onFocus={() => setFocused('role')}
                      onBlur={() => setFocused(null)}
                      placeholder="e.g. Geologist, Metallurgist, Surveyor…"
                      className="w-full pl-10 pr-4 py-3.5 bg-white/[0.04] border border-white/[0.08] rounded-2xl text-[15px] text-white placeholder:text-zinc-600 focus:outline-none transition-colors"
                    />
                  </div>
                </motion.div>
              </>
            )}

            {/* Password */}
            <motion.div
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.45 }}
            >
              <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider ml-1 mb-1.5 block">
                Password
              </label>
              <div className={`relative rounded-2xl transition-all duration-200 ${
                focused === 'password' ? 'ring-2 ring-sky-500/40' : ''
              }`}>
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
                  <Lock className={`w-4 h-4 transition-colors ${focused === 'password' ? 'text-sky-400' : 'text-zinc-600'}`} />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={mode === 'signup' ? signupPassword : password}
                  onChange={(e) => mode === 'signup' ? setSignupPassword(e.target.value) : setPassword(e.target.value)}
                  onFocus={() => setFocused('password')}
                  onBlur={() => setFocused(null)}
                  placeholder={mode === 'signup' ? 'Create password' : 'Enter password'}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  className="w-full pl-10 pr-12 py-3.5 bg-white/[0.04] border border-white/[0.08] rounded-2xl text-[15px] text-white placeholder:text-zinc-600 focus:outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 p-2.5 text-zinc-600 hover:text-zinc-400 transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </motion.div>

            {/* Error */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="flex items-start gap-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 p-3 text-[13px] text-rose-300">
                    <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                    {error}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Submit */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
            >
              <button
                type="submit"
                disabled={
                  loading ||
                  (mode === 'signin' ? (!username.trim() || !password.trim()) : (!signupName.trim() || !signupEmail.trim() || !signupPassword.trim()))
                }
                className="w-full py-3.5 rounded-2xl text-[15px] font-semibold text-white
                  bg-gradient-to-r from-sky-500 via-indigo-500 to-violet-600
                  hover:from-sky-400 hover:via-indigo-400 hover:to-violet-500
                  disabled:opacity-40 disabled:cursor-not-allowed
                  shadow-[0_8px_32px_rgba(59,130,246,0.35)]
                  hover:shadow-[0_12px_40px_rgba(59,130,246,0.5)]
                  active:scale-[0.98]
                  transition-all duration-200
                  flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {mode === 'signin' ? 'Signing in…' : 'Creating account…'}
                  </>
                ) : (
                  mode === 'signin' ? 'Sign In' : 'Join the Team'
                )}
              </button>
            </motion.div>
          </form>

          {/* Footer */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="text-center text-[11px] text-zinc-600 mt-6"
          >
            {mode === 'signup'
              ? `Slots auto-close once all ${signupStatus?.total ?? 6} accounts are created.`
              : 'Authorized personnel only. All access is logged.'}
          </motion.p>
        </div>
      </motion.div>
      </div>
      </div>
    </div>
  );
}
