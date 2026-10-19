// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-01, BR-C-10
// LEGACY: source/index.php:19-37 (<table border=0 + per-row action links)
// COMPONENT: components/UsersDataTable
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// shadcn <Table> primitive over the rows from useUsersQuery.
// Default sort is server-supplied (id DESC per BR-C-01); we do NOT
// re-sort in the client for the MVP. Per-row Edit / Delete action
// buttons carry aria-label="Edit ${name}" / "Delete ${name}" to keep
// WCAG 4.1.2 for icon-only buttons.
//
// No raw <table> outside the shadcn primitive — Gate-2 lock.

import { Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { User } from "@/types/user";

export interface UsersDataTableProps {
  rows: User[];
  onEdit: (user: User) => void;
  onDelete: (user: User) => void;
}

export function UsersDataTable({
  rows,
  onEdit,
  onDelete,
}: UsersDataTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[80px]">ID</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="w-[80px]">Age</TableHead>
          <TableHead>Email</TableHead>
          <TableHead className="w-[140px] text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((u) => (
          <TableRow key={u.id} data-testid={`user-row-${u.id}`}>
            <TableCell className="font-mono text-muted-foreground">
              {u.id}
            </TableCell>
            <TableCell className="font-medium">{u.name}</TableCell>
            <TableCell>{u.age}</TableCell>
            <TableCell>{u.email}</TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-2">
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`Edit ${u.name}`}
                  onClick={() => onEdit(u)}
                >
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`Delete ${u.name}`}
                  onClick={() => onDelete(u)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" aria-hidden="true" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default UsersDataTable;
