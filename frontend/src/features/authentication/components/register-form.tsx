"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/shared/form-alert";
import { FormField, fieldAria } from "@/components/shared/form-field";
import { PasswordInput } from "@/components/shared/password-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRegister } from "@/features/authentication/hooks";
import {
  PASSWORD_MIN_LENGTH,
  registerSchema,
  type RegisterValues,
} from "@/features/authentication/schemas";
import { isApiError } from "@/lib/api-client";

const PASSWORD_HINT = `At least ${PASSWORD_MIN_LENGTH} characters, with a letter and a number.`;

export function RegisterForm() {
  const router = useRouter();
  const registerUser = useRegister();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { name: "", email: "", password: "", confirmPassword: "" },
  });

  async function onSubmit({ name, email, password }: RegisterValues) {
    try {
      await registerUser.mutateAsync({ name, email, password });
      router.replace("/dashboard");
    } catch (error) {
      if (isApiError(error, 409)) {
        setError("email", { message: error.message });
      } else {
        setError("root", {
          message: isApiError(error) ? error.message : "Something went wrong. Please try again.",
        });
      }
    }
  }

  // method="post": if the form is submitted before the page is interactive, the browser
  // sends it by itself. POST keeps the password out of the URL and the browser history.
  return (
    <form method="post" onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <FormAlert message={errors.root?.message} />

      <FormField id="name" label="Full name" error={errors.name?.message}>
        <Input
          autoComplete="name"
          placeholder="Asha Rao"
          {...fieldAria("name", errors.name?.message)}
          {...register("name")}
        />
      </FormField>

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

      <FormField
        id="password"
        label="Password"
        error={errors.password?.message}
        hint={PASSWORD_HINT}
      >
        <PasswordInput
          autoComplete="new-password"
          {...fieldAria("password", errors.password?.message, PASSWORD_HINT)}
          {...register("password")}
        />
      </FormField>

      <FormField id="confirmPassword" label="Confirm password" error={errors.confirmPassword?.message}>
        <PasswordInput
          autoComplete="new-password"
          {...fieldAria("confirmPassword", errors.confirmPassword?.message)}
          {...register("confirmPassword")}
        />
      </FormField>

      <Button type="submit" size="lg" disabled={isSubmitting} className="w-full">
        {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
        {isSubmitting ? "Creating account…" : "Create account"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-teal-strong hover:underline">
          Log in
        </Link>
      </p>
    </form>
  );
}
