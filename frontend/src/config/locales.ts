/**
 * Locale configurations
 * Maps i18n language codes to Intl locale codes
 */

export interface LocaleConfig {
  code: string;         // i18n language code
  locale: string;       // Intl.NumberFormat locale
  dateLocale: string;   // Date formatting locale
  label: string;        // Display name
}

export const LOCALES: LocaleConfig[] = [
  { code: 'en', locale: 'en-US', dateLocale: 'en-US', label: 'English' },
  { code: 'tr', locale: 'tr-TR', dateLocale: 'tr-TR', label: 'Türkçe' },
  // Future locales:
  // { code: 'de', locale: 'de-DE', dateLocale: 'de-DE', label: 'Deutsch' },
  // { code: 'fr', locale: 'fr-FR', dateLocale: 'fr-FR', label: 'Français' },
];

/**
 * Get Intl locale from i18n language code
 */
export const getLocale = (languageCode: string): string => {
  const config = LOCALES.find((l) => l.code === languageCode);
  return config?.locale || 'en-US';
};

/**
 * Get date locale from i18n language code
 */
export const getDateLocale = (languageCode: string): string => {
  const config = LOCALES.find((l) => l.code === languageCode);
  return config?.dateLocale || 'en-US';
};

/**
 * Get locale config by code
 */
export const getLocaleConfig = (languageCode: string): LocaleConfig | undefined => {
  return LOCALES.find((l) => l.code === languageCode);
};
