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
  openGraph: {
    title: "AethOS",
    description:
      "The invisible layer that connects all autonomous agents — The Agentic Operating System.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "AethOS — The Agentic Operating System",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AethOS",
    description:
      "The invisible layer that connects all autonomous agents — The Agentic Operating System.",
    images: ["/og-image.png"],
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
