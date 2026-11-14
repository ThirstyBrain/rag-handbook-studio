import { getHandbook } from "@/content/handbook";
import { Link } from "@/shared/router/router";
import { BrandMark } from "@/shared/ui/BrandMark";

export function Footer() {
  const hb = getHandbook();
  const written = hb.chapters.filter((c) => c.status === "complete").length;
  return (
    <footer className="site-footer">
      <div className="page site-footer__inner">
        <div className="site-footer__about">
          <div className="site-footer__brand">
            <BrandMark size={24} />
            <span>RAG Architecture Handbook</span>
          </div>
          <p>
            A reading interface for <code>rag-architecture-handbook</code>. Every page is rendered from the handbook's own Markdown, ADRs and exercise scripts; {written} of {hb.entries.length} planned chapters are complete so far.
          </p>
        </div>
        <nav className="site-footer__cols" aria-label="Footer">
          <div>
            <p className="site-footer__cols-title">Read</p>
            <Link href="/handbook">Contents</Link>
            <Link href={`/handbook/${hb.chapters[0]?.slug ?? ""}`}>Chapter 1</Link>
            <Link href="/glossary">Glossary</Link>
            <Link href="/references">References</Link>
          </div>
          <div>
            <p className="site-footer__cols-title">Explore</p>
            <Link href="/architecture">Architecture map</Link>
            <Link href="/lab">Retrieval lab</Link>
            <Link href="/exercises">Exercises</Link>
            <Link href="/decisions">Decisions</Link>
            <Link href="/about">About</Link>
          </div>
        </nav>
      </div>
    </footer>
  );
}
