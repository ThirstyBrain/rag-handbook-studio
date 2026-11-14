import { chapterHref } from "@/content/handbook";
import { Link } from "@/shared/router/router";
import { Empty } from "@/shared/ui/States";
import { interviewGroups } from "./interviewData";

/** Every chapter's interview questions and model answers on one page, each group linked to its chapter. */
export default function InterviewPage() {
  const groups = interviewGroups();
  const total = groups.reduce((sum, g) => sum + g.items.length, 0);
  return (
    <div className="page">
      <header className="page-head">
        <p className="page-head__eyebrow">Interview prep</p>
        <h1 className="page-head__title">RAG interview questions</h1>
        <p className="page-head__lede">
          {total} questions with concise model answers from {groups.length} chapters. Each group links to the chapter that explains the answer in full, with its evidence.
        </p>
      </header>
      {groups.length === 0 ? (
        <Empty title="No interview questions yet" />
      ) : (
        <div className="prose">
          {groups.map(({ chapter, items }) => (
            <section key={chapter.number} id={chapter.slug}>
              <h2>
                <Link href={chapterHref(chapter)}>
                  Chapter {chapter.number}: {chapter.title}
                </Link>
              </h2>
              {items.map((item) => (
                <div key={item.question}>
                  <h3>{item.question}</h3>
                  <p>{item.answer}</p>
                </div>
              ))}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
