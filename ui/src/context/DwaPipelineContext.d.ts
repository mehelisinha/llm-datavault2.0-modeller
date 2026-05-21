import { type ReactNode } from "react";
import type { BvProposal, BronzeSnapshot, CatalogSnapshot, ChangeSet, ModelingPlan, SourceSystem, ValidationReport } from "@/api/types";
export type PipelineState = {
    system: SourceSystem | null;
    catalogSnapshot: CatalogSnapshot | null;
    bronzeSnapshot: BronzeSnapshot | null;
    changeSet: ChangeSet | null;
    plan: ModelingPlan | null;
    bv: BvProposal | null;
    validation: ValidationReport | null;
    renderedYaml: string | null;
};
type PipelineContextValue = PipelineState & {
    planId: string | null;
    setSnapshot: (payload: {
        system: SourceSystem;
        catalog_snapshot: CatalogSnapshot;
        bronze_snapshot: BronzeSnapshot;
        change_set: ChangeSet;
    }) => void;
    setPlan: (plan: ModelingPlan) => void;
    setBv: (bv: BvProposal) => void;
    setValidation: (validation: ValidationReport) => void;
    setRenderedYaml: (yaml: string) => void;
    reset: () => void;
};
export declare function DwaPipelineProvider({ children }: {
    children: ReactNode;
}): import("react/jsx-runtime").JSX.Element;
export declare function usePipeline(): PipelineContextValue;
export {};
