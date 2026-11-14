import { aboutSections } from "./aboutContent";

/** Who the handbook is for, how its claims are labelled, who maintains it and how to report an error. */
export default function AboutPage() {
  const sections = aboutSections();
  return (
    <div className="page">
      <header className="page-head">
        <p className="page-head__eyebrow">About</p>
        <h1 className="page-head__title">About the handbook</h1>
      </header>
      <div className="prose">
        {sections.map((s) => (
          <section key={s.id} id={s.id}>
            <h2>{s.title}</h2>
            {s.paragraphs.map((p) => (
              <p key={p}>{p}</p>
            ))}
            {s.list && (
              <dl>
                {s.list.map((item) => (
                  <div key={item.term}>
                    <dt>
                      <strong>{item.term}</strong>
                    </dt>
                    <dd>{item.text}</dd>
                  </div>
                ))}
              </dl>
            )}
            {s.link && (
              <p>
                <a href={s.link.href} target="_blank" rel="noopener noreferrer">
                  {s.link.label}
                </a>
              </p>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
