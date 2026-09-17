import Dashboard from "../components/Dashboard";
import results from "../src/data/results.json";
import priority from "../src/data/priority.json";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";

export default function Home() {
  const lookup_sha256 = createHash("sha256").update(readFileSync(path.join(process.cwd(), "public/data/lookup_grid.json"))).digest("hex");
  return <Dashboard results={{...results,lookup_sha256}} priority={priority} />;
}
