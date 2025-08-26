import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { loginUser } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import ErrorModal from './ErrorModal';

const Login = () => {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const navigate = useNavigate();
  const { login } = useAuth();

  // Credenziali admin hardcoded per il controllo iniziale
  const adminCredentials = {
    email: 'marktrapella06@gmail.com',
    password: 'admin123',
    role: 'admin'
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      // Prima controlla se è l'utente admin
      if (formData.email.toLowerCase() === adminCredentials.email.toLowerCase() && 
          formData.password === adminCredentials.password) {
        // Login admin riuscito
        navigate('/admin/dashboard');
        return;
      }

      // Altrimenti prova il login tramite API
      const response = await loginUser({
        email: formData.email,
        password: formData.password
      });

      // Login riuscito - salva il token nel contesto
      login(response.access_token);
      
      // Reindirizza alla dashboard utente
      navigate('/user/dashboard');
      
    } catch (error) {
      console.error('Errore durante il login:', error);
      
      // Messaggio generico per tutti gli errori di login
      setErrorMessage('Email o password non corretti.');
      setShowErrorModal(true);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-cream-50 via-white to-primary-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-100 rounded-full opacity-20 blur-3xl"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-green-200 rounded-full opacity-20 blur-3xl"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-to-r from-primary-200 to-green-300 rounded-full opacity-10 blur-3xl"></div>
      </div>

      <div className="max-w-md w-full relative z-10">
        {/* Logo and Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <img 
              src="/logo-cip-academy.png" 
              alt="CIP Academy Logo" 
              className="h-20 w-auto object-contain"
            />
          </div>
          <h2 className="text-3xl font-bold text-gray-900 mb-2">Benvenuto in C.I.P Academy</h2>
          <p className="text-gray-600 text-lg">
            Accedi alla tua area personale
          </p>
        </div>

        {/* Login Form Card */}
        <div className="card p-8 shadow-2xl border-0 bg-white/80 backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="space-y-6">

            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-semibold text-gray-700">
                Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m6.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                  </svg>
                </div>
                <input
                  type="text"
                  name="email"
                  id="email"
                  className="input-field pl-10 bg-gray-50 focus:bg-white transition-colors duration-200"
                  placeholder="Inserisci la tua email"
                  value={formData.email}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-semibold text-gray-700">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  id="password"
                  required
                  autoComplete="new-password"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck="false"
                  className="input-field pl-10 pr-12 bg-gray-50 focus:bg-white transition-colors duration-200"
                  placeholder="Inserisci la tua password"
                  value={formData.password}
                  onChange={handleChange}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="w-full bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-700 hover:to-primary-800 text-white font-semibold py-3 px-4 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-lg hover:shadow-xl"
            >
              Accedi
            </button>
          </form>

          {/* Footer Links */}
          <div className="mt-8 pt-6 border-t border-gray-200">
            <div className="text-center space-y-3">
              <p className="text-gray-600">
                Non hai un account?{' '}
                <Link to="/register" className="text-primary-600 hover:text-primary-700 font-semibold transition-colors duration-200">
                  Registrati qui
                </Link>
              </p>
              <Link 
                to="/" 
                className="inline-flex items-center text-gray-500 hover:text-gray-700 text-sm transition-colors duration-200"
              >
                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Torna alla homepage
              </Link>
            </div>
          </div>
        </div>

        {/* Additional Info */}
        <div className="mt-6 text-center">
          <p className="text-xs text-gray-500">
            Accedi con le credenziali fornite dalla tua organizzazione
          </p>
        </div>
      </div>

      {/* Error Modal */}
      <ErrorModal
        isOpen={showErrorModal}
        onClose={() => setShowErrorModal(false)}
        title="Errore di Login"
        message={errorMessage}
      />
    </div>
  );
};

export default Login;
