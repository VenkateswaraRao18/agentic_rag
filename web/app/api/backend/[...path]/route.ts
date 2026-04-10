import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Vercel caps this by plan (Hobby often 10–60s; Pro can be much higher).
 * Increase on Pro if Bedrock regularly runs longer than your plan limit.
 */
export const maxDuration = 60;
export const dynamic = "force-dynamic";

function backendBase(): string {
  return (
    process.env.BACKEND_PROXY_TARGET?.replace(/\/$/, "") || "http://127.0.0.1:8000"
  );
}

/** 5 minutes — Bedrock cold start + long generation */
const TIMEOUT_MS = 300_000;

/** Render (and similar) often return 502 while the dyno wakes or during brief proxy glitches. */
const RETRYABLE = new Set([502, 503]);
const MAX_ATTEMPTS = 3;

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function proxy(req: NextRequest, pathSegments: string[]): Promise<NextResponse> {
  const path = pathSegments.join("/") + req.nextUrl.search;
  const url = new URL(path, backendBase() + "/");

  const init: RequestInit = {
    method: req.method,
    headers: {},
    signal: AbortSignal.timeout(TIMEOUT_MS),
  };

  const ct = req.headers.get("content-type");
  if (ct) (init.headers as Record<string, string>)["Content-Type"] = ct;

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  let res: Response | undefined;
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    if (attempt > 0) {
      await sleep(1200 * attempt);
    }
    res = await fetch(url, init);
    if (!RETRYABLE.has(res.status)) {
      break;
    }
  }
  if (!res) {
    return NextResponse.json(
      { error: "Upstream request failed after retries" },
      { status: 502 },
    );
  }

  const body = await res.arrayBuffer();
  const out = new NextResponse(body, { status: res.status });
  const outCt = res.headers.get("content-type");
  if (outCt) out.headers.set("content-type", outCt);
  return out;
}

export async function GET(
  req: NextRequest,
  ctx: { params: { path: string[] } },
) {
  return proxy(req, ctx.params.path);
}

export async function POST(
  req: NextRequest,
  ctx: { params: { path: string[] } },
) {
  return proxy(req, ctx.params.path);
}

export async function OPTIONS(
  req: NextRequest,
  ctx: { params: { path: string[] } },
) {
  return proxy(req, ctx.params.path);
}
