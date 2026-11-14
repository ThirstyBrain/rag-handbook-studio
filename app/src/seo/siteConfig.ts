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

/**
 * The named author, shown as a byline and in structured data. Optional fields are used only when set:
 * add `bio` (a sentence on your experience with production RAG) and `sameAs` profile links such as LinkedIn.
 */
export const AUTHOR: { name: string; url: string; bio?: string; sameAs: string[] } = {
  name: "Kumar Shivam",
  url: PUBLISHER.url,
  sameAs: [PUBLISHER.url],
};

export const REPO_URL = "https://github.com/ThirstyBrain/rag-handbook-studio";
export const ISSUES_URL = `${REPO_URL}/issues`;

/** Prefix for generated social cards (dist/og/<page>.png, 1200x630). */
export const OG_IMAGE_DIR = "/og";

export const TITLE_SUFFIX = " | RAG Handbook";
export const TITLE_MAX = 60;

export const META_DESCRIPTION_MAX = 155;
