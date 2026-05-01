import { redirect } from "next/navigation";

export default function SystemPageRedirect() {
  redirect("/?p=system");
}
