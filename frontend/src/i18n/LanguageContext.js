/** Selected UI language, persisted the same way the auth token is. */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { translations } from './translations';

const STORAGE_KEY = 'ayudrishti.language';
const DEFAULT_LANGUAGE = 'en';

const LanguageContext = createContext(null);

function resolve(dict, path) {
  return path.split('.').reduce((node, key) => (node == null ? node : node[key]), dict);
}

function interpolate(template, params) {
  if (!params) return template;
  return Object.keys(params).reduce(
    (text, key) => text.replaceAll(`{${key}}`, String(params[key])),
    template,
  );
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(DEFAULT_LANGUAGE);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((stored) => {
        if (stored && translations[stored]) setLanguageState(stored);
      })
      .finally(() => setLoaded(true));
  }, []);

  const setLanguage = useCallback((code) => {
    if (!translations[code]) return;
    setLanguageState(code);
    AsyncStorage.setItem(STORAGE_KEY, code);
  }, []);

  const t = useCallback(
    (key, params) => {
      const dict = translations[language] ?? translations[DEFAULT_LANGUAGE];
      const value = resolve(dict, key) ?? resolve(translations[DEFAULT_LANGUAGE], key) ?? key;
      return interpolate(value, params);
    },
    [language],
  );

  const value = useMemo(
    () => ({ language, setLanguage, t, loaded }),
    [language, setLanguage, t, loaded],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useLanguage must be used inside a LanguageProvider');
  return context;
}
