import { lazy, type ComponentType, type LazyExoticComponent } from "react";
import { matchPath } from "@/shared/router/router";

/** Route table. Pages are code-split; each receives its URL params. */
type Page = LazyExoticComponent<ComponentType<{ params: Record<string, string> }>>;

const page = (loader: () => Promise<{ default: ComponentType<{ params: Record<string, string> }> }>): Page => lazy(loader);

export interface RouteDef {
  pattern: string;
  component: Page;
  /** Document title builder. */
  title: (params: Record<string, string>) => string;
}

export const ROUTES: RouteDef[] = [
  { pattern: "/", component: page(() => import("@/features/landing/LandingPage")), title: () => "" },
  { pattern: "/handbook", component: page(() => import("@/features/handbook/HandbookIndexPage")), title: () => "Contents" },
  { pattern: "/handbook/:slug", component: page(() => import("@/features/reader/ChapterPage")), title: () => "" },
  { pattern: "/architecture", component: page(() => import("@/features/architecture/ArchitecturePage")), title: () => "Architecture map" },
  { pattern: "/lab", component: page(() => import("@/features/playground/PlaygroundPage")), title: () => "Retrieval lab" },
  { pattern: "/exercises", component: page(() => import("@/features/exercises/ExercisesPage")), title: () => "Exercises" },
  { pattern: "/decisions", component: page(() => import("@/features/decisions/DecisionsPage")), title: () => "Architecture decisions" },
  { pattern: "/decisions/:id", component: page(() => import("@/features/decisions/DecisionsPage")), title: (p) => p.id ?? "" },
  { pattern: "/glossary", component: page(() => import("@/features/glossary/GlossaryPage")), title: () => "Glossary" },
  { pattern: "/references", component: page(() => import("@/features/references/ReferencesPage")), title: () => "References" },
];

export function resolveRoute(path: string): { route: RouteDef; params: Record<string, string> } | null {
  for (const route of ROUTES) {
    const params = matchPath(route.pattern, path);
    if (params) return { route, params };
  }
  return null;
}
