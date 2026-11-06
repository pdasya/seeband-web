/**
 * The language choice, shared by the site and the app through one cookie, as they are separate
 * builds on one origin. It holds only a language code.
 */
export const LANGUAGE_COOKIE = "seeband_language";
const ONE_YEAR_S = 60 * 60 * 24 * 365;

function decoded(value: string): string | null {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

export function readLanguage<T extends string>(
  cookies: string,
  languages: readonly T[],
  fallback: T,
): T {
  const prefix = `${LANGUAGE_COOKIE}=`;
  for (const part of cookies.split(";")) {
    const cookie = part.trim();
    if (cookie.startsWith(prefix)) {
      const value = decoded(cookie.slice(prefix.length));
      return languages.find((language) => language === value) ?? fallback;
    }
  }
  return fallback;
}

export function languageCookie(language: string): string {
  return `${LANGUAGE_COOKIE}=${encodeURIComponent(language)}; Path=/; Max-Age=${String(ONE_YEAR_S)}; SameSite=Lax`;
}
