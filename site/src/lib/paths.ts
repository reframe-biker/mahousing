import path from "path";

// process.cwd() is site/ in local dev, monorepo root on Vercel
// (Vercel sets cwd to the project root, which we configure as the monorepo root)

function repoRoot(): string {
  const cwd = process.cwd();
  return cwd.endsWith("site") ? path.join(cwd, "..") : cwd;
}

export function getDataPath(...segments: string[]): string {
  return path.join(repoRoot(), "data", ...segments);
}

export function getRepoRoot(...segments: string[]): string {
  return path.join(repoRoot(), ...segments);
}
