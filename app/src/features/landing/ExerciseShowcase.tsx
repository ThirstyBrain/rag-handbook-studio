import { getHandbook } from "@/content/handbook";
import { Link } from "@/shared/router/router";
import { ExercisePanel } from "@/features/exercises/ExercisePanel";

const FEATURED = "ch09_hybrid_search.py";

export function ExerciseShowcase() {
  const hb = getHandbook();
  const runs = hb.exercises.reduce((s, e) => s + e.runs.length, 0);
  const featured = hb.exercises.find((e) => e.file === FEATURED) ?? hb.exercises[0];
  if (!featured) return null;

  return (
    <section className="band band--bench" aria-labelledby="ex-title">
      <div className="page">
        <div className="band-head band-head--dark">
          <h2 id="ex-title" className="band-head__title">
            Claims marked executed come with the script and its output
          </h2>
          <p className="band-head__text">
            {hb.exercises.length} standard-library Python exercises back the chapters. The output below is from a real run of the script, captured at build time ({runs} runs in total), shown next to the exact source that produced it.
          </p>
        </div>
        <ExercisePanel file={featured.file} layout="split" showChapterLink />
        <p className="band__more">
          <Link href="/exercises" className="btn btn--quiet">
            See all {hb.exercises.length} exercises
          </Link>
        </p>
      </div>
    </section>
  );
}
