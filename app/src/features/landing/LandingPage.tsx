import { Hero } from "./Hero";
import { BenchBand } from "./BenchBand";
import { ReadingPath } from "./ReadingPath";
import { EvidenceBand } from "./EvidenceBand";
import { ExerciseShowcase } from "./ExerciseShowcase";
import { DecisionsBand } from "./DecisionsBand";
import { ExploreBand } from "./ExploreBand";
import "./landing.css";
import "./hero.css";

export default function LandingPage() {
  return (
    <div className="landing">
      <Hero />
      <BenchBand />
      <ReadingPath />
      <ExploreBand />
      <EvidenceBand />
      <ExerciseShowcase />
      <DecisionsBand />
    </div>
  );
}
