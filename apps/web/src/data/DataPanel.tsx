import { useEffect } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileSlot } from "@/data/FileSlot";
import { SingleFilePanel } from "@/data/SingleFilePanel";
import { useSessionStore, type DataMode } from "@/session/store";
import { Panel } from "@/shell/layout";
import { STRINGS } from "@/strings";

/** A file dropped just beside a slot would otherwise open in the tab, and lose the session.
 * Text is left alone, as a drop into a field is useful. */
function useNoDropOutsideSlots() {
  useEffect(() => {
    const prevent = (event: DragEvent) => {
      if (event.dataTransfer?.types.includes("Files") === true) {
        event.preventDefault();
      }
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
  const mode = useSessionStore((state) => state.dataMode);
  const setMode = useSessionStore((state) => state.setDataMode);
  return (
    <Panel title={data.title} subtitle={data.subtitle}>
      <Tabs
        value={mode}
        onValueChange={(value) => {
          setMode(value as DataMode);
        }}
        className="mt-3 gap-2.5"
      >
        <TabsList className="w-full" aria-label={data.source.label}>
          <TabsTrigger value="separate">{data.source.separate}</TabsTrigger>
          <TabsTrigger value="single">{data.source.single}</TabsTrigger>
        </TabsList>
        <TabsContent value="separate" className="flex flex-col gap-2.5">
          <FileSlot quantity="seebeck" />
          <FileSlot quantity="resistivity" />
          <FileSlot quantity="hall" />
        </TabsContent>
        <TabsContent value="single">
          <SingleFilePanel />
        </TabsContent>
      </Tabs>
    </Panel>
  );
}
