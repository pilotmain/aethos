import { Header } from "@/components/mission-control/Header";
import { Sidebar } from "@/components/mission-control/Sidebar";

export default function MissionControlShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-zinc-950 text-zinc-100">
      <Sidebar />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col lg:pl-64">
        <Header />
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
