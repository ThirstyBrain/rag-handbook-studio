import { useEffect, useState } from "react";
import { chapterHref, findChapter, getHandbook } from "@/content/handbook";
import { Link, useRouter } from "@/shared/router/router";
import { BrandMark } from "@/shared/ui/BrandMark";
import { Icon, type IconName } from "@/shared/ui/Icon";
import { useSearch } from "@/features/search/SearchProvider";
import { getLastRead } from "@/features/reader/readingState";
import "./chrome.css";

const NAV: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/handbook", label: "Handbook", icon: "book" },
  { href: "/architecture", label: "Architecture", icon: "network" },
  { href: "/lab", label: "Lab", icon: "flask" },
  { href: "/decisions", label: "Decisions", icon: "shield" },
  { href: "/glossary", label: "Glossary", icon: "compass" },
];

/** Mobile menu also lists the pages that do not fit in the desktop bar. */
const MOBILE_EXTRA: { href: string; label: string; icon: IconName }[] = [
  { href: "/exercises", label: "Exercises", icon: "terminal" },
  { href: "/references", label: "References", icon: "file" },
];

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

/** The chapter and section the reader was last in, or chapter 1 for a first visit. */
function continueHref(): { href: string; resume: boolean } {
  const last = getLastRead();
  const chapter = last ? findChapter(last.slug) : undefined;
  if (chapter) return { href: chapterHref(chapter, last?.sectionId ?? undefined), resume: true };
  const first = getHandbook().chapters[0];
  return { href: first ? chapterHref(first) : "/handbook", resume: false };
}

export function Header() {
  const { location } = useRouter();
  const { open } = useSearch();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const cont = continueHref();

  useEffect(() => setMenuOpen(false), [location.path]);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const active = (href: string) => (href === "/" ? location.path === "/" : location.path === href || location.path.startsWith(href + "/"));

  return (
    <header className="site-header" data-scrolled={scrolled || undefined} data-home={location.path === "/" || undefined}>
      <div className="site-header__inner page">
        <Link href="/" className="brand" aria-label="RAG Architecture Handbook, home">
          <BrandMark size={44} />
          <span className="brand__divider" aria-hidden="true" />
          <span className="brand__name">
            <span className="brand__name-1">RAG Architecture</span>
            <span className="brand__name-2">Handbook</span>
          </span>
        </Link>

        <nav className="site-nav" aria-label="Primary">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className="site-nav__link" aria-current={active(n.href) ? "page" : undefined}>
              <Icon name={n.icon} size={16} />
              {n.label}
            </Link>
          ))}
        </nav>

        <div className="site-header__tools">
          <button type="button" className="search-trigger" onClick={() => open("button")} aria-label="Search chapters" aria-keyshortcuts={isMac ? "Meta+K" : "Control+K"}>
            <Icon name="search" size={16} />
            <span className="search-trigger__label">Search chapters…</span>
            <kbd className="kbd search-trigger__kbd">{isMac ? "⌘" : "Ctrl"} K</kbd>
          </button>
          <Link href={cont.href} className="btn btn--ink header-cta" title={cont.resume ? "Return to where you left off" : "Start at chapter 1"}>
            {cont.resume ? "Continue Reading" : "Start Reading"}
            <Icon name="arrowRight" size={16} />
          </Link>
          <button type="button" className="menu-toggle" aria-expanded={menuOpen} aria-controls="mobile-nav" onClick={() => setMenuOpen((v) => !v)}>
            <span className="visually-hidden">{menuOpen ? "Close menu" : "Open menu"}</span>
            <span className="menu-toggle__bars" data-open={menuOpen || undefined} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div id="mobile-nav" className="mobile-nav" data-open={menuOpen || undefined} hidden={!menuOpen}>
        <nav aria-label="Primary, mobile" className="page">
          {[...NAV, ...MOBILE_EXTRA].map((n) => (
            <Link key={n.href} href={n.href} className="mobile-nav__link" aria-current={active(n.href) ? "page" : undefined}>
              <Icon name={n.icon} size={20} />
              {n.label}
            </Link>
          ))}
          <Link href={cont.href} className="btn btn--ink mobile-nav__cta">
            {cont.resume ? "Continue Reading" : "Start Reading"}
            <Icon name="arrowRight" size={16} />
          </Link>
        </nav>
      </div>
    </header>
  );
}
