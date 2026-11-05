"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/shared/form-alert";
import { FormField, fieldAria } from "@/components/shared/form-field";
import { PasswordInput } from "@/components/shared/password-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLogin } from "@/features/authentication/hooks";
import { loginSchema, type LoginValues } from "@/features/authentication/schemas";
import { isApiError } from "@/lib/api-client";
import { getSafeRedirect } from "@/lib/safe-redirect";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const login = useLogin();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginValues) {
    try {
      await login.mutateAsync(values);
      router.replace(getSafeRedirect(searchParams.get("next")));
    } catch (error) {
      setError("root", {
        message: isApiError(error) ? error.message : "Something went wrong. Please try again.",
      });
    }
  }

  // method="post": if the form is submitted before the page is interactive, the browser
  // sends it by itself. POST keeps the password out of the URL and the browser history.
  return (
    <form method="post" onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <FormAlert message={errors.root?.message} />

      <FormField id="email" label="Email" error={errors.email?.message}>
        <Input
          type="email"
          autoComplete="email"
          inputMode="email"
          placeholder="you@example.com"
          {...fieldAria("email", errors.email?.message)}
          {...register("email")}
        />
      </FormField>

      <FormField id="password" label="Password" error={errors.password?.message}>
        <PasswordInput
          autoComplete="current-password"
          {...fieldAria("password", errors.password?.message)}
          {...register("password")}
        />
      </FormField>

      <Button type="submit" size="lg" disabled={isSubmitting} className="w-full">
        {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
        {isSubmitting ? "Logging in…" : "Log in"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        New to CivicPulse AI?{" "}
        <Link href="/register" className="font-medium text-teal-strong hover:underline">
          Create an account
        </Link>
      </p>
    </form>
  );
}
