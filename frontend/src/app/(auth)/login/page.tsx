import type { Metadata } from "next";
import { Suspense } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LoginForm } from "@/features/authentication/components/login-form";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">
          <h1>Welcome back</h1>
        </CardTitle>
        <CardDescription>Log in to report issues and track your complaints.</CardDescription>
      </CardHeader>
      <CardContent>
        {/* LoginForm reads ?next= from the URL, which must sit inside a Suspense boundary. */}
        <Suspense>
          <LoginForm />
        </Suspense>
      </CardContent>
    </Card>
  );
}
