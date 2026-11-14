/** File name of a page's social card: "/handbook/01-x" becomes "handbook-01-x.png". Pure, so the client can use it too. */
export const ogFileName = (path: string): string => `${path === "/" ? "home" : path.slice(1).replace(/\//g, "-")}.png`;
