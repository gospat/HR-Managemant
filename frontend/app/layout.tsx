import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "University HR | People & Culture",
  description: "A workspace for university human resources.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-NG">
      <body>{children}</body>
    </html>
  );
}
