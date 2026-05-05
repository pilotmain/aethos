"use client";

import { useMemo, useState } from "react";

import type { MemberUsage } from "@/types/mission-control";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface MemberUsageTableProps {
  members: MemberUsage[];
  totalTokens: number;
}

type SortKey = "name" | "tokens" | "cost" | "percentage" | "last_active";

export function MemberUsageTable({ members, totalTokens }: MemberUsageTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("tokens");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    const list = [...(members || [])];
    list.sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      switch (sortKey) {
        case "name":
          return a.member_name.localeCompare(b.member_name) * dir;
        case "tokens":
          return (a.tokens - b.tokens) * dir;
        case "cost":
          return (a.cost - b.cost) * dir;
        case "percentage":
          return (a.percentage - b.percentage) * dir;
        case "last_active":
          return (new Date(a.last_active).getTime() - new Date(b.last_active).getTime()) * dir;
        default:
          return 0;
      }
    });
    return list;
  }, [members, sortKey, sortDir]);

  const toggle = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "name" ? "asc" : "desc");
    }
  };

  if (!members || members.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-zinc-500">
        No usage rows yet — run remote provider calls to populate the audit trail.
      </div>
    );
  }

  const head = (key: SortKey, label: string) => (
    <TableHead>
      <button type="button" className="font-medium text-violet-300 hover:underline" onClick={() => toggle(key)}>
        {label}
        {sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
      </button>
    </TableHead>
  );

  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-500">
        Rows mirror provider attribution from recent audits (per-agent splits are not yet in the API). Total tokens in
        view: <span className="tabular-nums text-zinc-300">{totalTokens.toLocaleString()}</span>.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            {head("name", "Source")}
            {head("tokens", "Tokens")}
            {head("cost", "Cost")}
            {head("percentage", "Share")}
            {head("last_active", "Last active")}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((member) => (
            <TableRow key={member.member_id}>
              <TableCell className="font-medium">
                <div className="flex items-center gap-2">
                  <Avatar className="h-7 w-7">
                    <AvatarFallback className="text-[10px]">{member.member_name.charAt(0).toUpperCase()}</AvatarFallback>
                  </Avatar>
                  <span>{member.member_name}</span>
                </div>
              </TableCell>
              <TableCell className="tabular-nums">{member.tokens.toLocaleString()}</TableCell>
              <TableCell className="tabular-nums">${member.cost.toFixed(4)}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <Progress value={member.percentage} max={100} className="h-2 w-24" />
                  <span className="text-xs tabular-nums text-zinc-400">{member.percentage.toFixed(1)}%</span>
                </div>
              </TableCell>
              <TableCell className="text-sm text-zinc-500">
                {new Date(member.last_active).toLocaleDateString()}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
