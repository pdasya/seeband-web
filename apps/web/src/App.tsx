import { AlertCircleIcon, PlayIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const CARD = "rounded-xl border bg-card p-5 shadow-card flex flex-col gap-4";

/**
 * The base components with the design's values, to compare with the design.
 *
 * U2 replaces this page. Its text is not translated, as i18n comes with U3, and its values are
 * only samples.
 */
export function App() {
  return (
    <main className="mx-auto grid max-w-[1440px] grid-cols-3 items-start gap-6 p-6">
      <section className={CARD}>
        <h2 className="text-lg font-semibold tracking-[-0.01em]">
          Buttons and badges
        </h2>
        <div className="flex flex-wrap gap-2">
          <Button>
            <PlayIcon fill="currentColor" />
            Run fit
          </Button>
          <Button variant="outline">Initial guess</Button>
          <Button variant="secondary">More graphs</Button>
          <Button variant="ghost">Reset</Button>
          <Button disabled>Disabled</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="neutral">Manual parameters</Badge>
          <Badge variant="info">Fitting… iteration 3</Badge>
          <Badge variant="success">Converged in 7 iter.</Badge>
          <Badge variant="warning">Iteration limit reached</Badge>
          <Badge variant="suggestion">Initial guess</Badge>
        </div>
      </section>

      <section className={CARD}>
        <h2 className="text-lg font-semibold tracking-[-0.01em]">Controls</h2>
        <Tabs defaultValue="seebeck">
          <TabsList>
            <TabsTrigger value="seebeck">S(T)</TabsTrigger>
            <TabsTrigger value="resistivity">ρ(T)</TabsTrigger>
            <TabsTrigger value="hall">R_H(T)</TabsTrigger>
          </TabsList>
        </Tabs>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          N₁
          <Input type="number" defaultValue={1} />
        </label>
        <Select defaultValue="acPh">
          <SelectTrigger aria-label="Scattering" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="acPh">Acoustic phonons (acPh)</SelectItem>
            <SelectItem value="dis">Alloy disorder (dis)</SelectItem>
          </SelectContent>
        </Select>
        <Slider aria-label="m_eff" defaultValue={[40]} />
        <div className="flex items-center justify-between gap-3 text-sm font-medium">
          Interpolation
          <Switch aria-label="Interpolation" defaultChecked />
        </div>
      </section>

      <section className={CARD}>
        <h2 className="text-lg font-semibold tracking-[-0.01em]">
          Tables and alerts
        </h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Parameter</TableHead>
              <TableHead className="text-right">Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>E_g</TableCell>
              <TableCell className="text-right font-mono">800 K</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <Alert variant="warning">
          <AlertCircleIcon />
          <AlertTitle>No R_H(T) data.</AlertTitle>
          <AlertDescription>
            Upload a Hall file to determine m₁.
          </AlertDescription>
        </Alert>
        <Alert variant="destructive">
          <AlertCircleIcon />
          <AlertTitle>Check the mapping.</AlertTitle>
          <AlertDescription>Assign exactly one column to T.</AlertDescription>
        </Alert>
      </section>
    </main>
  );
}
