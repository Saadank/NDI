import { NextResponse, type NextRequest } from "next/server";

const AUTH_COOKIE = "datarix-auth";

function hasValidToken(req: NextRequest): boolean {
  const cookie = req.cookies.get(AUTH_COOKIE)?.value;
  if (!cookie) return false;
  try {
    const parsed = JSON.parse(decodeURIComponent(cookie));
    return Boolean(parsed?.state?.accessToken);
  } catch {
    return false;
  }
}

export function middleware(req: NextRequest) {
  if (!hasValidToken(req)) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("next", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/data-sharing/:path*",
    "/profile/:path*",
    "/delegation/:path*",
    "/ndmo-compliance/:path*",
  ],
};
