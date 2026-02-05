export const resolveApiBaseUrl = () => {
  const explicit =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_BACKEND_API_URL;

  if (explicit) {
    return explicit.replace(/\/$/, '');
  }

  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8000';
    }
  }

  return 'https://verified-digital-twin-brains.onrender.com';
};

export const resolveApiHostLabel = () => {
  const base = resolveApiBaseUrl();
  try {
    return new URL(base).host;
  } catch {
    return base.replace(/^https?:\/\//, '');
  }
};
