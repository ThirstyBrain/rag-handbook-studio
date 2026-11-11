import { Suspense, useEffect } from "react";
import { track } from "@/shared/analytics/track";
import { RouterProvider, useRouter } from "@/shared/router/router";
import { Loading } from "@/shared/ui/States";
import { SearchProvider } from "@/features/search/SearchProvider";
import { ErrorBoundary } from "./ErrorBoundary";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { NotFound } from "./NotFound";
import { resolveRoute } from "./routes";
import { useScrollRestoration } from "./useScrollRestoration";

const SITE = "RAG Architecture Handbook";

function CurrentRoute() {
  const { location } = useRouter();
  const match = resolveRoute(location.path);
  useScrollRestoration(location);

  useEffect(() => {
    track({ name: "page_view", path: location.path });
    const t = match?.route.title(match.params);
    if (t !== "") document.title = t ? `${t} — ${SITE}` : SITE;
  }, [location.path, match]);

  if (!match) return <NotFound />;
  const Page = match.route.component;
  return (
    <ErrorBoundary key={location.path}>
      <Suspense fallback={<Loading label="Loading page" />}>
        <Page params={match.params} />
      </Suspense>
    </ErrorBoundary>
  );
}

export function App() {
  return (
    <RouterProvider>
      <SearchProvider>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <Header />
        <main id="main" tabIndex={-1}>
          <CurrentRoute />
        </main>
        <Footer />
      </SearchProvider>
    </RouterProvider>
  );
}
