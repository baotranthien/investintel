import type { Metadata } from "next";
import ResearchWorkspaceClient from "./research-workspace";

export async function generateMetadata({ params }: { params: Promise<{ ticker: string }> }): Promise<Metadata> {
  const { ticker } = await params;
  return { title: `${ticker.toUpperCase()} Research`, description: `Evidence-first research workspace for ${ticker.toUpperCase()}.` };
}

export default async function ResearchAssetPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  return <ResearchWorkspaceClient symbol={ticker.toUpperCase()} />;
}
