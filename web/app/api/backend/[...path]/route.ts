import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

function backendBase(): string {
  return (
    process.env.BACKEND_PROXY_TARGET?.replace(/\/$/, "") || "http://127.0.0.1:8000"
  );
}

/** 5 minutes — Bedrock cold start + long generation */
const TIMEOUT_MS = 300_000;

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

  const res = await fetch(url, init);
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
