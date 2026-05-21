import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type {
  BvProposal,
  BronzeSnapshot,
  CatalogSnapshot,
  ChangeSet,
  ModelingPlan,
  SourceSystem,
  ValidationReport,
} from "@/api/types";

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

const emptyState: PipelineState = {
  system: null,
  catalogSnapshot: null,
  bronzeSnapshot: null,
  changeSet: null,
  plan: null,
  bv: null,
  validation: null,
  renderedYaml: null,
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

const PipelineContext = createContext<PipelineContextValue | null>(null);

export function DwaPipelineProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PipelineState>(emptyState);

  const setSnapshot = useCallback(
    (payload: {
      system: SourceSystem;
      catalog_snapshot: CatalogSnapshot;
      bronze_snapshot: BronzeSnapshot;
      change_set: ChangeSet;
    }) => {
      setState((prev) => ({
        ...prev,
        system: payload.system,
        catalogSnapshot: payload.catalog_snapshot,
        bronzeSnapshot: payload.bronze_snapshot,
        changeSet: payload.change_set,
        plan: null,
        bv: null,
        validation: null,
        renderedYaml: null,
      }));
    },
    [],
  );

  const setPlan = useCallback((plan: ModelingPlan) => {
    setState((prev) => ({ ...prev, plan, bv: null, validation: null }));
  }, []);

  const setBv = useCallback((bv: BvProposal) => {
    setState((prev) => ({ ...prev, bv }));
  }, []);

  const setValidation = useCallback((validation: ValidationReport) => {
    setState((prev) => ({ ...prev, validation }));
  }, []);

  const setRenderedYaml = useCallback((renderedYaml: string) => {
    setState((prev) => ({ ...prev, renderedYaml }));
  }, []);

  const reset = useCallback(() => setState(emptyState), []);

  // Validator sets plan_id to plan.system_id; fall back so governance works
  // even when the user skipped "Validate plan" on the Diff page.
  const planId = state.validation?.plan_id ?? state.plan?.system_id ?? null;

  const value = useMemo(
    () => ({
      ...state,
      planId,
      setSnapshot,
      setPlan,
      setBv,
      setValidation,
      setRenderedYaml,
      reset,
    }),
    [state, planId, setSnapshot, setPlan, setBv, setValidation, setRenderedYaml, reset],
  );

  return (
    <PipelineContext.Provider value={value}>{children}</PipelineContext.Provider>
  );
}

export function usePipeline(): PipelineContextValue {
  const ctx = useContext(PipelineContext);
  if (!ctx) {
    throw new Error("usePipeline must be used within DwaPipelineProvider");
  }
  return ctx;
}
