import type { Metadata } from "next";
import { TrustActivityPage } from "@/components/trust/TrustActivityPage";

export const metadata: Metadata = {
  title: "Trust & activity · AethOS",
  description: "What AethOS did, why, and whether it was allowed.",
};

export default function TrustPage() {
  return <TrustActivityPage />;
}
