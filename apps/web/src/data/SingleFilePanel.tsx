import {
  AlertCircleIcon,
  LoaderCircleIcon,
  Table2Icon,
  XIcon,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DropArea, useFileDrop } from "@/data/DropArea";
import { issueMessage, noDataMessages } from "@/data/messages";
import {
  assignColumn,
  failSingleFile,
  loadSingleFile,
  removeSingleFile,
} from "@/data/singleFile";
import { cn } from "@/lib/utils";
import {
  QUANTITIES,
  useSessionStore,
  type ColumnRole,
  type ParsedTable,
} from "@/session/store";
import { STRINGS } from "@/strings";

const IGNORE = "ignore";
const PREVIEW_ROWS = 3;
const ROLES: readonly ColumnRole["role"][] = ["temperature", ...QUANTITIES];

const { data: text } = STRINGS;

function roleSymbol(role: ColumnRole["role"]): string {
  return role === "temperature" ? "T" : text.quantities[role].symbol;
}

function formatValue(value: number | undefined, isTemperature: boolean) {
  if (value === undefined) {
    return "";
  }
  return isTemperature ? String(value) : value.toExponential(3);
}

function FileIcon() {
  return (
    <div className="flex size-8 flex-none items-center justify-center rounded-md bg-muted">
      <Table2Icon className="size-4" aria-hidden="true" />
    </div>
  );
}

function columnName(table: ParsedTable, column: number): string {
  return (
    table.headers?.[column] ?? `${text.single.column} ${String(column + 1)}`
  );
}

function ColumnMapping({
  table,
  mapping,
}: {
  table: ParsedTable;
  mapping: readonly ColumnRole[];
}) {
  const roleOf = (column: number) =>
    mapping.find((item) => item.column === column)?.role;
  return (
    <>
      <div className="flex flex-col gap-0.5 pt-1">
        <span className="text-[13px] font-medium">{text.single.mapTitle}</span>
        <span className="text-xs text-muted-foreground">
          {text.single.mapHint}
        </span>
      </div>
      {Array.from({ length: table.column_count }, (_, column) => {
        const name = columnName(table, column);
        const role = roleOf(column);
        return (
          <div
            key={column}
            className="grid grid-cols-[minmax(0,1fr)_128px] items-center gap-2"
          >
            <div className="min-w-0">
              <div className="truncate font-mono text-[13px] font-medium">
                {name}
              </div>
              <div className="truncate font-mono text-xs text-muted-foreground">
                {formatValue(
                  table.preview[0]?.[column],
                  role === "temperature",
                )}
              </div>
            </div>
            <Select
              value={role ?? IGNORE}
              onValueChange={(value) => {
                void assignColumn(
                  column,
                  value === IGNORE ? null : (value as ColumnRole["role"]),
                );
              }}
            >
              <SelectTrigger
                size="sm"
                className="w-full"
                aria-label={`${text.single.columnRole} ${name}`}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((option) => (
                  <SelectItem key={option} value={option}>
                    {roleSymbol(option)}
                  </SelectItem>
                ))}
                <SelectItem value={IGNORE}>{text.single.ignore}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        );
      })}
    </>
  );
}

function ParsedChips({ table }: { table: ParsedTable }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {QUANTITIES.map((quantity) => {
        const measurement = table.measurements[quantity];
        const { symbol } = text.quantities[quantity];
        return (
          <Badge
            key={quantity}
            variant={measurement === undefined ? "neutral" : "success"}
          >
            {measurement === undefined
              ? `${symbol} · ${text.single.notFound}`
              : `${symbol} · ${String(measurement.points)} ${text.points}`}
          </Badge>
        );
      })}
    </div>
  );
}

function Preview({
  table,
  mapping,
}: {
  table: ParsedTable;
  mapping: readonly ColumnRole[];
}) {
  const roleOf = (column: number) =>
    mapping.find((item) => item.column === column)?.role;
  const columns = Array.from({ length: table.column_count }, (_, c) => c);
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table className="font-mono text-xs">
        <TableCaption className="mt-0 caption-top p-2 pb-0 text-left font-sans text-xs">
          {text.single.preview}
        </TableCaption>
        <TableHeader>
          <TableRow>
            {columns.map((column) => {
              const role = roleOf(column);
              const name = columnName(table, column);
              return (
                <TableHead
                  key={column}
                  className={cn(
                    "h-auto px-2.5 py-1.5 font-medium",
                    role === undefined && "text-muted-foreground",
                  )}
                >
                  {role === undefined ? name : `${roleSymbol(role)} ← ${name}`}
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {table.preview.slice(0, PREVIEW_ROWS).map((row, index) => (
            <TableRow key={index}>
              {columns.map((column) => {
                const role = roleOf(column);
                return (
                  <TableCell
                    key={column}
                    className={cn(
                      "px-2.5 py-1.5",
                      role === undefined && "text-muted-foreground",
                    )}
                  >
                    {formatValue(row[column], role === "temperature")}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function Problems({ table }: { table: ParsedTable }) {
  if (table.errors.length === 0) {
    return null;
  }
  return (
    <Alert variant="destructive">
      <AlertCircleIcon aria-hidden="true" />
      <AlertTitle>{text.single.errorTitle}</AlertTitle>
      <AlertDescription>
        <ul className="m-0 list-none p-0">
          {noDataMessages(table.errors, []).map((message, index) => (
            <li key={index}>{message}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}

/** One table with several quantities, whose columns a user can assign. */
export function SingleFilePanel() {
  const file = useSessionStore((state) => state.singleFile);
  const handlers = {
    onFile: (chosen: File) => {
      void loadSingleFile(chosen);
    },
    onSeveralFiles: () => {
      failSingleFile(text.oneFile);
    },
  };
  const { dragging, dropTarget } = useFileDrop(handlers);
  const table = file?.table ?? null;

  const status = (
    <div role="status" className="sr-only">
      {file?.loading === true ? `${file.name}: ${text.reading}` : ""}
      {file?.loading !== true && table !== null && file !== null
        ? `${file.name}: ${QUANTITIES.filter(
            (q) => table.measurements[q] !== undefined,
          )
            .map((q) => text.quantities[q].title)
            .join(", ")}`
        : ""}
    </div>
  );
  const failure = file?.failure != null && (
    <Alert variant="destructive">
      <AlertCircleIcon aria-hidden="true" />
      <AlertDescription>
        {file.name !== "" && (
          <div className="font-mono break-all">{file.name}</div>
        )}
        {file.failure}
      </AlertDescription>
    </Alert>
  );

  if (table === null || file === null) {
    return (
      <div className="flex flex-col gap-2.5">
        {status}
        {file?.loading === true ? (
          <div
            data-file-slot="table"
            className="flex items-center gap-3 rounded-lg border px-3 py-2.5"
            {...dropTarget}
          >
            <FileIcon />
            <div className="min-w-0 flex-auto">
              <div className="truncate font-mono text-[13px] font-medium">
                {file.name}
              </div>
              <div className="text-xs text-muted-foreground">
                {text.reading}
              </div>
            </div>
            <LoaderCircleIcon
              className="size-4 flex-none animate-spin text-muted-foreground"
              aria-hidden="true"
            />
          </div>
        ) : (
          <DropArea
            slotId="table"
            icon={<FileIcon />}
            title={text.single.dropTitle}
            {...handlers}
          />
        )}
        {failure}
      </div>
    );
  }

  const usable = QUANTITIES.some(
    (quantity) => table.measurements[quantity] !== undefined,
  );
  return (
    <div className="flex flex-col gap-2.5">
      {status}
      <div
        data-file-slot="table"
        className={cn(
          "flex items-center gap-3 rounded-lg border px-3 py-2.5",
          dragging && "border-ring bg-muted",
        )}
        {...dropTarget}
      >
        <FileIcon />
        <div className="min-w-0 flex-auto">
          <div
            className="truncate font-mono text-[13px] font-medium"
            title={file.name}
          >
            {file.name}
          </div>
          <div className="text-xs text-muted-foreground">
            {`${String(table.row_count)} ${text.single.rows} · ${String(table.column_count)} ${text.single.columns}`}
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={text.remove}
          onClick={removeSingleFile}
        >
          <XIcon aria-hidden="true" />
        </Button>
      </div>
      {table.column_count > 0 && (
        <ColumnMapping table={table} mapping={file.mapping} />
      )}
      {failure}
      <Problems table={table} />
      <ParsedChips table={table} />
      {table.preview.length > 0 && (
        <Preview table={table} mapping={file.mapping} />
      )}
      {table.warnings.length > 0 && (
        <ul
          className={cn(
            "m-0 list-none p-0 text-xs",
            usable ? "text-muted-foreground" : "text-destructive",
          )}
        >
          {table.warnings.map((warning, index) => (
            <li key={index}>{issueMessage(warning)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
