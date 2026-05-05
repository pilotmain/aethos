import type { Metadata } from "next";
import "./globals.css";
import { ProjectStatusBanner } from "@/components/aethos/ProjectStatusBanner";

export const metadata: Metadata = {
  title: "AethOS",
  description: "AethOS — The Agentic Operating System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full min-h-0">
        <ProjectStatusBanner />
        {children}
      </body>
    </html>
  );
}
