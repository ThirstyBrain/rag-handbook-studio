import { getHandbook } from "@/content/handbook";
import { Link } from "@/shared/router/router";
import { Icon, type IconName } from "@/shared/ui/Icon";
import { HandbookPreview } from "./HandbookPreview";
import { HeroBackdrop } from "./HeroBackdrop";
import { PipelineGlance } from "./PipelineGlance";

export function Hero() {
  const hb = getHandbook();
  const first = hb.chapters[0];

  const FEATURES: { icon: IconName; title: string; detail: string; href: string }[] = [
    { icon: "book", title: `${hb.entries.length} Chapters`, detail: "In-depth Coverage", href: "/handbook" },
    { icon: "network", title: "Interactive", detail: "Architecture", href: "/architecture" },
    { icon: "code", title: "Real-World", detail: "Patterns", href: "/decisions" },
    { icon: "shield", title: "Production", detail: "Ready", href: "/exercises" },
  ];

  return (
    <section className="hero" aria-labelledby="hero-title">
      <HeroBackdrop />
      <div className="hero__grid page">
        <div className="hero__copy">
          <p className="hero__eyebrow">Learn · Explore · Architect</p>
          <h1 id="hero-title" className="hero__title">
            <span className="hero__line">The RAG</span>{" "}
            <span className="hero__line">Architecture</span>{" "}
            <span className="hero__line hero__line--accent">Handbook</span>
          </h1>
          <p className="hero__subtitle">From fundamentals to enterprise-scale intelligent retrieval systems.</p>
          <p className="hero__lede">
            An implementation-oriented reference for architects and principal engineers who design, build, evaluate, secure and operate retrieval-augmented generation systems.
          </p>

          <ul className="hero__features">
            {FEATURES.map((f) => (
              <li key={f.title}>
                <Link href={f.href} className="hero__feature">
                  <Icon name={f.icon} size={26} strokeWidth={1.5} />
                  <span className="hero__feature-title">{f.title}</span>
                  <span className="hero__feature-detail">{f.detail}</span>
                </Link>
              </li>
            ))}
          </ul>

          <div className="hero__actions">
            {first && (
              <Link href={`/handbook/${first.slug}`} className="btn hero__cta">
                <Icon name="book" size={20} />
                Start Reading
                <Icon name="arrowRight" size={18} className="hero__cta-arrow" />
              </Link>
            )}
            <Link href="/architecture" className="btn hero__cta-2">
              <span className="hero__play">
                <Icon name="play" size={22} />
              </span>
              Explore Architecture
            </Link>
          </div>
        </div>

        <div className="hero__visual">
          <PipelineGlance />
          <span className="hero__drop" aria-hidden="true" />
          <HandbookPreview />
        </div>

        <aside className="confidence" aria-label="About this handbook">
          <div className="confidence__main">
            <Icon name="chart" size={40} strokeWidth={1.6} className="confidence__icon" />
            <div>
              <p className="confidence__title">Build RAG Systems with Confidence</p>
              <p className="confidence__text">Understand the patterns, trade-offs and decisions behind production-ready architectures.</p>
            </div>
          </div>
          <div className="confidence__side">
            <Icon name="users" size={36} strokeWidth={1.6} className="confidence__icon" />
            <p className="confidence__text">A must-read for architects, engineers and builders.</p>
          </div>
        </aside>
      </div>
    </section>
  );
}
