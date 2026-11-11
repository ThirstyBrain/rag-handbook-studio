import { useEffect, useMemo, useState } from "react";
import { track } from "@/shared/analytics/track";
import { useRouter } from "@/shared/router/router";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { ArchitectureMap } from "./ArchitectureMap";
import { StageDetail } from "./StageDetail";
import { STAGES } from "./stages";
import "./architecture.css";

export default function ArchitecturePage() {
  const { location, navigate } = useRouter();
  const compact = useMediaQuery("(max-width: 760px)");
  const fromHash = STAGES.find((s) => s.id === location.hash)?.id;
  const [selected, setSelected] = useState(fromHash ?? "retrieve");

  useEffect(() => {
    if (fromHash) setSelected(fromHash);
  }, [fromHash]);

  const stage = useMemo(() => STAGES.find((s) => s.id === selected) ?? STAGES[0]!, [selected]);

  const select = (id: string) => {
    setSelected(id);
    navigate(`/architecture#${id}`, { replace: true });
    track({ name: "architecture_stage", stage: id });
    if (compact) requestAnimationFrame(() => document.getElementById("stage-detail")?.scrollIntoView({ block: "start" }));
  };

  return (
    <div className="page arch">
      <header className="page-head">
        <p className="page-head__eyebrow">Explore the system</p>
        <h1 className="page-head__title">Architecture map</h1>
        <p className="page-head__lede">
          A production RAG system as two paths: documents are prepared ahead of time, questions are answered per request. Select a stage to open the handbook's diagrams, chapters and decisions for it.
        </p>
      </header>

      <ArchitectureMap selected={selected} onSelect={select} compact={compact} />
      <StageDetail key={stage.id} stage={stage} />
    </div>
  );
}
