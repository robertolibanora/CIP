import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { registerUser, checkEmailExists } from '../services/api';
import ErrorModal from './ErrorModal';

const Register = () => {
  const [formData, setFormData] = useState({
    nome: '',
    cognome: '',
    nomeTelegram: '',
    telefono: '',
    email: '',
    referralLink: '',
    password: '',
    confermaPassword: ''
  });
  const [errors, setErrors] = useState({});
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [showPhoneConfirmation, setShowPhoneConfirmation] = useState(false);
  const [pendingRegistration, setPendingRegistration] = useState(null);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const navigate = useNavigate();

  // Non serve più il controllo hardcoded, il backend gestisce tutto

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    // Rimuovi errore quando l'utente inizia a digitare
    if (errors[e.target.name]) {
      setErrors({
        ...errors,
        [e.target.name]: ''
      });
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.nome.trim()) newErrors.nome = 'Il nome è obbligatorio';
    if (!formData.cognome.trim()) newErrors.cognome = 'Il cognome è obbligatorio';
    if (!formData.nomeTelegram.trim()) newErrors.nomeTelegram = 'Il nome Telegram è obbligatorio';
    if (!formData.telefono.trim()) newErrors.telefono = 'Il numero di telefono è obbligatorio';
    if (!formData.email.trim()) newErrors.email = 'L\'email è obbligatoria';
    if (!formData.password) newErrors.password = 'La password è obbligatoria';
    if (formData.password !== formData.confermaPassword) {
      newErrors.confermaPassword = 'Le password non coincidono';
    }

    // Validazione formato email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (formData.email && !emailRegex.test(formData.email)) {
      newErrors.email = 'Mail errata';
    }

    // Validazione password lunghezza minima
    if (formData.password && formData.password.length < 6) {
      newErrors.password = 'La password deve essere di almeno 6 caratteri';
    }

    // Il controllo email già registrata viene fatto dal backend
    // Non serve più la validazione frontend

    return newErrors;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = validateForm();

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Mostra conferma numero di telefono
    setPendingRegistration(formData);
    setShowPhoneConfirmation(true);
  };

  const confirmPhoneNumber = async (isCorrect) => {
    if (isCorrect) {
      try {
        // Procedi con la registrazione
        const formDataToSubmit = pendingRegistration;
        
        // Registra l'utente tramite API
        const response = await registerUser({
          nome: formDataToSubmit.nome,
          cognome: formDataToSubmit.cognome,
          nome_telegram: formDataToSubmit.nomeTelegram,
          telefono: formDataToSubmit.telefono,
          email: formDataToSubmit.email,
          referral_link: formDataToSubmit.referralLink,
          password: formDataToSubmit.password
        });
        
        console.log('Utente registrato con successo:', response);
        
        // Reindirizza alla pagina di login
        navigate('/login');
      } catch (error) {
        console.error('Errore durante la registrazione:', error);
        
        // Se è un errore di email già registrata, mostra il messaggio elegante nel form
        if (error.message.includes('Email già registrata')) {
          setErrors({
            ...errors,
            email: 'Questa email è già registrata. Effettua l\'accesso.'
          });
          // Chiudi automaticamente il popup di conferma telefono
          setShowPhoneConfirmation(false);
          setPendingRegistration(null);
        } else {
          // Per altri errori, mostra il modal
          setErrorMessage(error.message);
          setShowErrorModal(true);
        }
      }
    } else {
      // Torna alla modifica del form
      setShowPhoneConfirmation(false);
      setPendingRegistration(null);
      // Il form rimane compilato per permettere la modifica
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-cream-50 via-white to-primary-50 py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-100 rounded-full opacity-20 blur-3xl"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-green-200 rounded-full opacity-20 blur-3xl"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-to-r from-primary-200 to-green-300 rounded-full opacity-10 blur-3xl"></div>
      </div>

      <div className="max-w-2xl mx-auto relative z-10">
        {/* Logo and Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <img 
              src="/logo-cip-academy.png" 
              alt="CIP Academy Logo" 
              className="h-20 w-auto object-contain drop-shadow-lg"
            />
          </div>
          <h2 className="text-3xl font-bold text-gray-900 mb-2">Registrazione C.I.P Academy</h2>
          <p className="text-gray-600 text-lg">
            Crea il tuo account per accedere alla piattaforma
          </p>
        </div>

        {/* Registration Form Card */}
        <div className="card p-8 shadow-2xl border-0 bg-white/80 backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Name Fields */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label htmlFor="nome" className="block text-sm font-semibold text-gray-700">
                  Nome *
                </label>
                <input
                  type="text"
                  name="nome"
                  id="nome"
                  required
                  className={`input-field ${errors.nome ? 'border-red-500 bg-red-50' : 'bg-gray-50 focus:bg-white'} transition-colors duration-200`}
                  placeholder="Inserisci il tuo nome"
                  value={formData.nome}
                  onChange={handleChange}
                />
                {errors.nome && <p className="text-red-500 text-xs mt-1">{errors.nome}</p>}
              </div>

              <div className="space-y-2">
                <label htmlFor="cognome" className="block text-sm font-semibold text-gray-700">
                  Cognome *
                </label>
                <input
                  type="text"
                  name="cognome"
                  id="cognome"
                  required
                  className={`input-field ${errors.cognome ? 'border-red-500 bg-red-50' : 'bg-gray-50 focus:bg-white'} transition-colors duration-200`}
                  placeholder="Inserisci il tuo cognome"
                  value={formData.cognome}
                  onChange={handleChange}
                />
                {errors.cognome && <p className="text-red-500 text-xs mt-1">{errors.cognome}</p>}
              </div>
            </div>

            {/* Telegram Username */}
            <div className="space-y-2">
              <label htmlFor="nomeTelegram" className="block text-sm font-semibold text-gray-700">
                Nome Telegram *
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                  </svg>
                </div>
                <input
                  type="text"
                  name="nomeTelegram"
                  id="nomeTelegram"
                  required
                  className={`input-field pl-10 ${errors.nomeTelegram ? 'border-red-500 bg-red-50' : 'bg-gray-50 focus:bg-white'} transition-colors duration-200`}
                  placeholder="Inserisci il tuo nome telegram"
                  value={formData.nomeTelegram}
                  onChange={handleChange}
                />
              </div>
              <p className="text-xs text-gray-500 mt-1 flex items-center">
                <svg className="w-4 h-4 mr-1 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Esempio: @mariorossi98
              </p>
              {errors.nomeTelegram && <p className="text-red-500 text-xs mt-1">{errors.nomeTelegram}</p>}
            </div>

            {/* Phone */}
            <div className="space-y-2">
              <label htmlFor="telefono" className="block text-sm font-semibold text-gray-700">
                Numero di telefono *
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                  </svg>
                </div>
                <input
                  type="tel"
                  name="telefono"
                  id="telefono"
                  required
                  className={`input-field pl-10 ${errors.telefono ? 'border-red-500 bg-red-50' : 'bg-gray-50 focus:bg-white'} transition-colors duration-200`}
                  placeholder="Es. +39 123 456 7890"
                  value={formData.telefono}
                  onChange={handleChange}
                />
              </div>
              {errors.telefono && <p className="text-red-500 text-xs mt-1">{errors.telefono}</p>}
            </div>

            {/* Email */}
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-semibold text-gray-700">
                Email *
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m6.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                  </svg>
                </div>
                <input
                  type="text"
                  name="email"
                  id="email"
                  required
                  className={`input-field pl-10 ${errors.email ? 'border-red-500 bg-red-50' : 'bg-gray-50 focus:bg-white'} transition-colors duration-200`}
                  placeholder="Inserisci la tua email"
                  value={formData.email}
                  onChange={handleChange}
                />
              </div>
              {errors.email && (
                <div className="flex items-center space-x-2">
                  <p className="text-red-500 text-xs">{errors.email}</p>
                  {errors.email.includes('già registrata') && (
                    <Link 
                      to="/login" 
                      className="text-primary-600 hover:text-primary-700 text-xs font-medium underline"
                    >
                      Vai al login
                    </Link>
                  )}
                </div>
              )}
            </div>

            {/* Referral Link */}
            <div className="space-y-2">
              <label htmlFor="referralLink" className="block text-sm font-semibold text-gray-700">
                Referral Link
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                </div>
                <input
                  type="text"
                  name="referralLink"
                  id="referralLink"
                  className="input-field pl-10 bg-gray-50 focus:bg-white transition-colors duration-200"
                  placeholder="Link di referimento (opzionale)"
                  value={formData.referralLink}
                  onChange={handleChange}
                />
              </div>
              <div className="bg-blue-50 border-l-4 border-blue-400 p-3 rounded-r-lg">
                <p className="text-xs text-blue-700">
                  <svg className="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Se non inserirai un referral link verrai inserito in automatico nel primo posto libero
                </p>
              </div>
            </div>

            {/* Password Fields */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label htmlFor="password" className="block text-sm font-semibold text-gray-700">
                  Password *
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
                    className={`input-field pl-10 pr-12 ${errors.password ? 'border-red-500 bg-red-50' : 'bg-gray-50 focus:bg-white'} transition-colors duration-200`}
                    placeholder="Inserisci la password"
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
                {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}
              </div>

              <div className="space-y-2">
                <label htmlFor="confermaPassword" className="block text-sm font-semibold text-gray-700">
                  Conferma Password *
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    name="confermaPassword"
                    id="confermaPassword"
                    required
                    autoComplete="new-password"
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck="false"
                    className={`input-field pl-10 pr-12 ${errors.confermaPassword ? 'border-red-500 bg-red-50' : 'bg-gray-50 focus:bg-white'} transition-colors duration-200`}
                    placeholder="Conferma la password"
                    value={formData.confermaPassword}
                    onChange={handleChange}
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? (
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
                {errors.confermaPassword && <p className="text-red-500 text-xs mt-1">{errors.confermaPassword}</p>}
              </div>
            </div>

            <button
              type="submit"
              className="w-full bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-700 hover:to-primary-800 text-white font-semibold py-3 px-4 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-lg hover:shadow-xl"
            >
              <svg className="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
              </svg>
              Registrati
            </button>
          </form>

          {/* Footer Links */}
          <div className="mt-8 pt-6 border-t border-gray-200">
            <div className="text-center space-y-3">
              <p className="text-gray-600">
                Hai già un account?{' '}
                <Link to="/login" className="text-primary-600 hover:text-primary-700 font-semibold transition-colors duration-200">
                  Accedi qui
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
      </div>

      {/* Phone Confirmation Modal */}
      {showPhoneConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            <div className="text-center">
              {/* Icona telefono */}
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
              </div>
              
              <h3 className="text-xl font-bold text-gray-900 mb-2">
                Conferma numero di telefono
              </h3>
              
              <p className="text-gray-600 mb-6">
                Il numero di telefono inserito è:
              </p>
              
              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <p className="text-lg font-semibold text-gray-800">
                  {pendingRegistration?.telefono}
                </p>
              </div>
              
              <p className="text-gray-700 mb-6 font-medium">
                Il numero di telefono è corretto?
              </p>
              
              {/* Pulsanti */}
              <div className="flex space-x-3">
                <button
                  onClick={() => confirmPhoneNumber(false)}
                  className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 px-4 rounded-lg transition-colors duration-200"
                >
                  No, modifica
                </button>
                
                <button
                  onClick={() => confirmPhoneNumber(true)}
                  className="flex-1 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-700 hover:to-primary-800 text-white font-semibold py-3 px-4 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-lg hover:shadow-xl"
                >
                  Sì, è corretto
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error Modal */}
      <ErrorModal
        isOpen={showErrorModal}
        onClose={() => setShowErrorModal(false)}
        title="Errore di Registrazione"
        message={errorMessage}
      />
    </div>
  );
};

export default Register;
