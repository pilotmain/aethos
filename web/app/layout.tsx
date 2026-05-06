import type { Metadata } from "next";
import "./globals.css";
import { ProjectStatusBanner } from "@/components/aethos/ProjectStatusBanner";

export const metadata: Metadata = {
  title: "AethOS",
  description:
    "AethOS — The invisible layer that connects all autonomous agents.",
  icons: {
    icon: [{ url: "/aethos-icon.png", type: "image/png", sizes: "512x512" }],
    shortcut: "/aethos-icon.png",
  },
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
