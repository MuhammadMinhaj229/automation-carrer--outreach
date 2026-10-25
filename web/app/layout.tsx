import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ACIOS - Career Intelligence & Outreach Operating System",
  description: "End-to-End Enterprise Recruitment Pipeline | 5-Tab Human Approval Cockpit",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} dark`}>
      <body className="bg-neutral-950 text-neutral-100 antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
