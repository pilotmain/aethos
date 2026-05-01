import { redirect } from "next/navigation";

export default function KeysPageRedirect() {
  redirect("/?p=keys");
}
