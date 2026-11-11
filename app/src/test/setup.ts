import "@testing-library/jest-dom/vitest";

// jsdom lacks these browser APIs; the components feature-detect them, but tests need stable stubs.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({ matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false }) as MediaQueryList;
}
class IO {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(window as any).IntersectionObserver ??= IO;
window.scrollTo = () => {};
Element.prototype.scrollIntoView = function () {};
