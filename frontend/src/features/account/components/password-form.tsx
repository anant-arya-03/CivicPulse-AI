"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { passwordSchema } from "@/features/authentication/schemas";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormAlert } from "@/components/shared/form-alert";
import { FormField, fieldAria } from "@/components/shared/form-field";
const schema = z.object({ current_password: z.string().min(1).max(128), new_password: passwordSchema, confirm: z.string() })
.refine(v => v.new_password === v.confirm, { path: ["confirm"], message: "Passwords do not match." });
type Values = z.infer<typeof schema>;
export function PasswordForm() {
  const cache = useQueryClient(); const router = useRouter();
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) });
  return <form method="post" className="grid max-w-md gap-4" onSubmit={handleSubmit(async values => {
    try { await api.post("/users/me/password", { current_password: values.current_password, new_password: values.new_password }); cache.clear(); router.replace("/login"); }
    catch (e) { setError("root", { message: e instanceof Error ? e.message : "Could not change password." }); }
  })}>
    <p className="text-sm text-muted-foreground">Changing your password signs out every session. Sign in again with your new password.</p>
    {([ ["current_password", "Current password"], ["new_password", "New password"], ["confirm", "Confirm new password"] ] as const).map(([key, label]) =>
      <FormField key={key} id={key} label={label} error={errors[key]?.message}>
        <Input type="password" autoComplete={key === "current_password" ? "current-password" : "new-password"} {...fieldAria(key, errors[key]?.message)} {...register(key)} />
      </FormField>)}
    <FormAlert message={errors.root?.message} /><Button disabled={isSubmitting}>{isSubmitting ? "Changing..." : "Change password"}</Button>
  </form>;
}
