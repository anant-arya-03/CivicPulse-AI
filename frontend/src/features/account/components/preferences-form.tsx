"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { authKeys } from "@/features/authentication/hooks";
import { Button } from "@/components/ui/button";
import { FormAlert } from "@/components/shared/form-alert";
import type { User } from "@/types/api";

const schema = z.object({
  followup_ready: z.boolean(), status_changes: z.boolean(),
  include_name_in_complaints: z.boolean(), share_exact_coordinates: z.boolean(),
});
type Values = z.infer<typeof schema>;
export function PreferencesForm({ user }: { user: User }) {
  const cache = useQueryClient();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: {
    followup_ready: user.notification_preferences?.followup_ready ?? true,
    status_changes: user.notification_preferences?.status_changes ?? true,
    include_name_in_complaints: user.privacy_settings?.include_name_in_complaints ?? true,
    share_exact_coordinates: user.privacy_settings?.share_exact_coordinates ?? true,
  }});
  const mutation = useMutation({ mutationFn: (values: Values) => api.put<User>("/users/me/settings", {
    notification_preferences: { followup_ready: values.followup_ready, status_changes: values.status_changes },
    privacy_settings: { include_name_in_complaints: values.include_name_in_complaints, share_exact_coordinates: values.share_exact_coordinates },
  }), onSuccess: (updated, values) => {
    cache.setQueryData(authKeys.me, updated);
    void cache.invalidateQueries({ queryKey: ["notifications"] });
    form.reset(values); toast.success("Preferences saved.");
  }});
  return <form method="post" onSubmit={form.handleSubmit(values => mutation.mutate(values))} className="grid gap-5">
    <fieldset className="grid gap-3"><legend className="mb-3 font-semibold">Notification preferences</legend>
      <p className="text-sm text-muted-foreground">Updates appear in your notification bell. No email or push notifications are sent.</p>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" {...form.register("followup_ready")} /> Reminders and escalation updates</label>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" {...form.register("status_changes")} /> Replies and status changes</label>
    </fieldset>
    <fieldset className="grid gap-3"><legend className="mb-3 font-semibold">Privacy settings</legend>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" {...form.register("include_name_in_complaints")} /> Include my name in new letters</label>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" {...form.register("share_exact_coordinates")} /> Include map coordinates in new letters</label>
      <p className="text-sm text-muted-foreground">Applies when a letter is generated next. Existing drafts and messages keep their text. Review or regenerate a draft to remove details already included. Your confirmed address remains part of the complaint.</p>
    </fieldset>
    <FormAlert message={mutation.error?.message} />
    <Button className="w-fit" disabled={!form.formState.isDirty || mutation.isPending}> {mutation.isPending ? "Saving..." : "Save preferences"}</Button>
  </form>;
}
