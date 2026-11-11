import { isInternalHref, matchPath } from "./router";

describe("router", () => {
  it("matches static and parameterised paths", () => {
    expect(matchPath("/handbook", "/handbook")).toEqual({});
    expect(matchPath("/handbook/:slug", "/handbook/09-hybrid-search")).toEqual({ slug: "09-hybrid-search" });
    expect(matchPath("/handbook/:slug", "/handbook")).toBeNull();
    expect(matchPath("/decisions/:id", "/glossary/x")).toBeNull();
  });
  it("decodes params", () => {
    expect(matchPath("/x/:id", "/x/a%20b")).toEqual({ id: "a b" });
  });
  it("only treats same-origin paths as internal", () => {
    expect(isInternalHref("/lab")).toBe(true);
    expect(isInternalHref("//evil.example")).toBe(false);
    expect(isInternalHref("https://x")).toBe(false);
  });
});
