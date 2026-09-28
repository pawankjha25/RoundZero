// Server-side Supabase client for Server Components and Route Handlers (the
// /auth/callback route uses this). Reads/writes the session via Next.js's
// cookies() - see middleware.ts for why writes here are wrapped in try/catch
// (Server Components can't set cookies; middleware handles the actual refresh).
import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
        } catch {
          // Called from a Server Component - middleware.ts refreshes the
          // session on the next request, so this is safe to ignore here.
        }
      },
    },
  });
}
