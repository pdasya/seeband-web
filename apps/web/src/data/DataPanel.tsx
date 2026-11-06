import { useEffect } from "react";

import { FileSlot } from "@/data/FileSlot";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

/** A file dropped just beside a slot would otherwise open in the tab, and lose the session. */
function useNoDropOutsideSlots() {
  useEffect(() => {
    const prevent = (event: DragEvent) => {
      event.preventDefault();
    };
    window.addEventListener("dragover", prevent);
    window.addEventListener("drop", prevent);
    return () => {
      window.removeEventListener("dragover", prevent);
      window.removeEventListener("drop", prevent);
    };
  }, []);
}

export function DataPanel() {
  useNoDropOutsideSlots();
  const { data } = STRINGS;
  return (
    <Panel title={data.title} subtitle={data.subtitle}>
      <div className="mt-3 flex flex-col gap-2.5">
        <FileSlot quantity="seebeck" />
        <FileSlot quantity="resistivity" />
        <FileSlot quantity="hall" />
      </div>
    </Panel>
  );
}
