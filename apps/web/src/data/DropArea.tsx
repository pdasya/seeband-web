import { UploadIcon } from "lucide-react";
import {
  useState,
  type ChangeEvent,
  type DragEvent,
  type ReactNode,
  type Ref,
} from "react";

import { ACCEPTED_EXTENSIONS } from "@/data/readFile";
import { cn } from "@/lib/utils";
import { STRINGS } from "@/strings";

export interface FileDropHandlers {
  onFile: (file: File) => void;
  onSeveralFiles: () => void;
}

/** What makes an element take a dropped file. It lights up only for a file, not for text. */
export function useFileDrop({ onFile, onSeveralFiles }: FileDropHandlers) {
  const [dragging, setDragging] = useState(false);
  return {
    dragging,
    dropTarget: {
      onDragOver: (event: DragEvent) => {
        if (event.dataTransfer.types.includes("Files")) {
          event.preventDefault();
          setDragging(true);
        }
      },
      onDragLeave: () => {
        setDragging(false);
      },
      onDrop: (event: DragEvent) => {
        event.preventDefault();
        setDragging(false);
        const { files } = event.dataTransfer;
        const [file] = files;
        if (files.length > 1) {
          onSeveralFiles();
        } else if (file !== undefined) {
          onFile(file);
        }
      },
    },
  };
}

/**
 * The dashed place to drop or choose a file. A `footer` sits inside the same frame, below the part
 * that opens the file picker, so a control there neither opens it nor shifts the slot.
 */
export function DropArea({
  icon,
  title,
  inputRef,
  slotId,
  footer,
  ...handlers
}: FileDropHandlers & {
  icon: ReactNode;
  title: string;
  inputRef?: Ref<HTMLInputElement>;
  slotId: string;
  footer?: ReactNode;
}) {
  const { dragging, dropTarget } = useFileDrop(handlers);
  const onChoose = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // So that choosing the same file again, perhaps after editing it, reads it again.
    event.target.value = "";
    if (file !== undefined) {
      handlers.onFile(file);
    }
  };
  return (
    <div
      data-file-slot={slotId}
      className={cn(
        "rounded-lg border border-dashed border-[var(--color-zinc-300)] bg-[var(--color-zinc-50)] has-[input[type=file]:focus-visible]:outline-2 has-[input[type=file]:focus-visible]:outline-offset-2 has-[input[type=file]:focus-visible]:outline-ring",
        dragging && "border-ring bg-muted",
      )}
      {...dropTarget}
    >
      <label className="relative flex cursor-pointer items-center gap-3 px-3 py-2.5">
        {icon}
        <div className="min-w-0 flex-auto">
          <div className="text-[13px] font-medium">{title}</div>
          <div className="text-xs text-muted-foreground">
            {STRINGS.data.dropHint}
          </div>
        </div>
        <UploadIcon
          className="size-4 flex-none text-muted-foreground"
          aria-hidden="true"
        />
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="sr-only"
          onChange={onChoose}
        />
      </label>
      {footer !== undefined && (
        <div className="border-t border-dashed border-[var(--color-zinc-300)] px-3 py-2">
          {footer}
        </div>
      )}
    </div>
  );
}
