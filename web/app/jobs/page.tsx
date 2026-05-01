import { redirect } from "next/navigation";

export default function JobsPageRedirect() {
  redirect("/?p=job");
}
