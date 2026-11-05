import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LaunchSignal — Marketing operations",
  description: "From website findings to accountable marketing execution.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
