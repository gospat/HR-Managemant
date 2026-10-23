import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Bells University of Technology | People & Culture",
  description: "People and culture workspace for Bells University of Technology.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-NG">
      <body>{children}</body>
    </html>
  );
}
