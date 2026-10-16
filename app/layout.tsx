import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FraudLens | Fraud Analytics & Strategy",
  description: "Poojan Desai’s interactive fraud analytics project: compare detection thresholds, review workload, financial cost, and explanations using synthetic transaction data.",
  metadataBase: new URL("https://fraudlens-poojan-desai.netlify.app"),
  alternates: { canonical: "/" },
  authors: [{ name: "Poojan Desai" }],
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body></html>;
}
