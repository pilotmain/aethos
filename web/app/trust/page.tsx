import type { Metadata } from "next";
import { TrustActivityPage } from "@/components/trust/TrustActivityPage";

export const metadata: Metadata = {
  title: "Trust & activity · Nexa",
  description: "What Nexa did, why, and whether it was allowed.",
};

export default function TrustPage() {
  return <TrustActivityPage />;
}
