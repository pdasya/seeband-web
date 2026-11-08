import { DownloadIcon } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { useExport } from "@/model/useExport";
import { STRINGS } from "@/strings";

const { export: text } = STRINGS;

interface Format {
  id: string;
  label: string;
  text: string;
  download: () => Promise<void>;
}

/** A button that opens a choice of formats, the first chosen, and downloads in the one picked. */
function FormatDialog({
  title,
  description,
  formats,
  busy,
}: {
  title: string;
  description: string;
  formats: readonly [Format, ...Format[]];
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState(formats[0].id);
  const id = useId();
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" disabled={busy}>
          <DownloadIcon aria-hidden="true" />
          {title}
        </Button>
      </DialogTrigger>
      <DialogContent closeLabel={text.close}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <RadioGroup
          aria-label={text.format}
          value={chosen}
          onValueChange={setChosen}
        >
          {formats.map((format) => (
            <div key={format.id} className="flex items-start gap-3">
              <RadioGroupItem
                id={`${id}-${format.id}`}
                value={format.id}
                aria-describedby={`${id}-${format.id}-text`}
                className="mt-0.5"
              />
              <label htmlFor={`${id}-${format.id}`} className="flex flex-col">
                <span className="text-sm font-medium">{format.label}</span>
                <span
                  id={`${id}-${format.id}-text`}
                  className="text-xs text-muted-foreground"
                >
                  {format.text}
                </span>
              </label>
            </div>
          ))}
        </RadioGroup>
        <DialogFooter>
          <Button
            disabled={busy}
            onClick={() => {
              setOpen(false);
              void formats
                .find(({ id: format }) => format === chosen)
                ?.download();
            }}
          >
            <DownloadIcon aria-hidden="true" />
            {text.download}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** The design's two exports, each in a format the user picks in a dialog. */
export function ExportButtons({
  exporter,
}: {
  exporter: ReturnType<typeof useExport>;
}) {
  const { busy } = exporter;
  return (
    <>
      <FormatDialog
        title={text.data}
        description={text.dialogText}
        busy={busy}
        formats={[
          { id: "text", ...text.formats.data, download: exporter.data },
          { id: "csv", ...text.formats.csv, download: exporter.csv },
          { id: "zip", ...text.formats.zip, download: exporter.zip },
        ]}
      />
      <FormatDialog
        title={text.parameters}
        description={text.parametersDialogText}
        busy={busy}
        formats={[
          {
            id: "text",
            ...text.parameterFormats.data,
            download: exporter.parameters,
          },
          {
            id: "csv",
            ...text.parameterFormats.csv,
            download: exporter.parametersCsv,
          },
        ]}
      />
    </>
  );
}
