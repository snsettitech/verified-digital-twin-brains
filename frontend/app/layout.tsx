import type { Metadata } from "next";
import "./globals.css";
import { FeatureFlagProvider } from "@/lib/features/FeatureFlags";
import { ToastProvider } from "@/components/ui/Toast";
import { ThemeProvider } from "@/lib/context/ThemeContext";

export const metadata: Metadata = {
  title: "PersonaOn AI",
  description: "Your digital persona, always on.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className="antialiased bg-[#080E1A] text-white"
      >
        <ThemeProvider>
          <FeatureFlagProvider>
            <ToastProvider>
              {children}
            </ToastProvider>
          </FeatureFlagProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
