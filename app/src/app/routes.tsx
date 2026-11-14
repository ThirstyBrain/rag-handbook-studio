import { lazy, type ComponentType, type LazyExoticComponent } from "react";
import { matchPath } from "@/shared/router/router";

/** Route table. Pages are code-split; each receives its URL params. */
type Page = LazyExoticComponent<ComponentType<{ params: Record<string, string> }>>;

const page = (loader: () => Promise<{ default: ComponentType<{ params: Record<string, string> }> }>): Page => lazy(loader);

export interface RouteDef {
  pattern: string;
  component: Page;
}

export const ROUTES: RouteDef[] = [
  { pattern: "/", component: page(() => import("@/features/landing/LandingPage")) },
  { pattern: "/handbook", component: page(() => import("@/features/handbook/HandbookIndexPage")) },
  { pattern: "/handbook/:slug", component: page(() => import("@/features/reader/ChapterPage")) },
  { pattern: "/architecture", component: page(() => import("@/features/architecture/ArchitecturePage")) },
  { pattern: "/lab", component: page(() => import("@/features/playground/PlaygroundPage")) },
  { pattern: "/exercises", component: page(() => import("@/features/exercises/ExercisesPage")) },
  { pattern: "/decisions", component: page(() => import("@/features/decisions/DecisionsPage")) },
  { pattern: "/decisions/:id", component: page(() => import("@/features/decisions/DecisionsPage")) },
  { pattern: "/glossary", component: page(() => import("@/features/glossary/GlossaryPage")) },
  { pattern: "/references", component: page(() => import("@/features/references/ReferencesPage")) },
  { pattern: "/interview-questions", component: page(() => import("@/features/interview/InterviewPage")) },
  { pattern: "/about", component: page(() => import("@/features/about/AboutPage")) },
];

export function resolveRoute(path: string): { route: RouteDef; params: Record<string, string> } | null {
  for (const route of ROUTES) {
    const params = matchPath(route.pattern, path);
    if (params) return { route, params };
  }
  return null;
}
