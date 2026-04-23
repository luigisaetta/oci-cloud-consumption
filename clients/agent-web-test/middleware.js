/**
 * Basic Auth middleware for dev protection of the Next.js test client.
 * Enabled when DEV_BASIC_AUTH_USER and DEV_BASIC_AUTH_PASS are configured.
 */
import { NextResponse } from "next/server";

function unauthorizedResponse() {
  return new NextResponse("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="Dev Access", charset="UTF-8"',
    },
  });
}

export function middleware(request) {
  const expectedUser = process.env.DEV_BASIC_AUTH_USER;
  const expectedPass = process.env.DEV_BASIC_AUTH_PASS;

  // Keep local DX simple: if credentials are not configured, do not enforce auth.
  if (!expectedUser || !expectedPass) {
    return NextResponse.next();
  }

  const authHeader = request.headers.get("authorization") || "";
  if (!authHeader.startsWith("Basic ")) {
    return unauthorizedResponse();
  }

  let decoded = "";
  try {
    decoded = atob(authHeader.slice(6));
  } catch (_error) {
    return unauthorizedResponse();
  }

  const separatorIndex = decoded.indexOf(":");
  if (separatorIndex < 0) {
    return unauthorizedResponse();
  }

  const providedUser = decoded.slice(0, separatorIndex);
  const providedPass = decoded.slice(separatorIndex + 1);
  if (providedUser !== expectedUser || providedPass !== expectedPass) {
    return unauthorizedResponse();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
