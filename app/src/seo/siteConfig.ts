/**
 * Single source for site identity used by metadata, structured data, the sitemap and the About page.
 * Change the publisher here once the real author or a custom domain is known.
 */
export const SITE_NAME = "RAG Architecture Handbook";
export const SITE_SUBTITLE = "The Production-Grade RAG Architecture & Engineering Handbook";
export const SITE_TITLE = `${SITE_NAME}: Production RAG Engineering Guide`;
export const SITE_DESCRIPTION =
  "An evidence-labelled handbook for building production RAG systems: chapters, architecture decisions, runnable exercises and a hybrid retrieval lab.";
export const SITE_DEFINITION =
  "The RAG Architecture Handbook is an implementation-oriented reference for architects and engineers who design, evaluate, secure and operate Retrieval-Augmented Generation systems.";

/** Used when no deployment URL is provided (SITE_URL or Netlify's URL variable). */
export const DEFAULT_SITE_URL = "https://rag-handbook-studio.netlify.app";

export const PUBLISHER = {
  name: "ThirstyBrain",
  url: "https://github.com/ThirstyBrain",
} as const;

export const REPO_URL = "https://github.com/ThirstyBrain/rag-handbook-studio";
export const ISSUES_URL = `${REPO_URL}/issues`;

/** Optional 1200x630 social card. Used only when the file exists in public/. */
export const OG_IMAGE_PATH = "/og-image.png";

export const META_DESCRIPTION_MAX = 155;
