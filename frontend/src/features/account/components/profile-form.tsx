"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { FormAlert } from "@/components/shared/form-alert";
import { FormField, fieldAria } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUpdateProfile } from "@/features/account/hooks";
import { nameSchema } from "@/features/authentication/schemas";
import { isApiError } from "@/lib/api-client";
import type { User } from "@/types/api";

const profileSchema = z.object({ name: nameSchema });
type ProfileValues = z.infer<typeof profileSchema>;

export function ProfileForm({ user }: { user: User }) {
  const updateProfile = useUpdateProfile();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: user.name },
  });

  async function onSubmit(values: ProfileValues) {
    try {
      const updated = await updateProfile.mutateAsync(values);
      reset({ name: updated.name });
      toast.success("Profile updated.");
    } catch (error) {
      setError("root", {
        message: isApiError(error) ? error.message : "Couldn't save your changes.",
      });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid max-w-md gap-5">
      <FormAlert message={errors.root?.message} />
      <FormField id="name" label="Full name" error={errors.name?.message}>
        <Input autoComplete="name" {...fieldAria("name", errors.name?.message)} {...register("name")} />
      </FormField>
      <div>
        <Button type="submit" disabled={isSubmitting || !isDirty}>
          {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
          Save changes
        </Button>
      </div>
    </form>
  );
}
