"use client";

import { PreferencesForm } from "./preferences-form";
import { PasswordForm } from "./password-form";

import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ProfileForm } from "@/features/account/components/profile-form";
import { useCurrentUser } from "@/features/authentication/hooks";
import type { User } from "@/types/api";

const dateFormatter = new Intl.DateTimeFormat("en", { dateStyle: "long" });

export function SettingsView() {
  const { data: user } = useCurrentUser(); // undefined for a moment while loading

  return (
    <div className="grid gap-8">
      <PageHeader title="Settings" description="Manage your profile and account." />
      {user ? <SettingsContent user={user} /> : <SettingsSkeleton />}
    </div>
  );
}

function SettingsSkeleton() {
  return (
    <div className="grid gap-8" aria-busy="true" aria-label="Loading settings">
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-32 rounded-xl" />
    </div>
  );
}

function SettingsContent({ user }: { user: User }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Profile</h2>
          </CardTitle>
          <CardDescription>Your name appears on complaints you choose to send.</CardDescription>
        </CardHeader>
        <CardContent>
          <ProfileForm user={user} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Account</h2>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Email</dt>
              <dd className="mt-1 font-medium break-all">{user.email}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Member since</dt>
              <dd className="mt-1 font-medium">{dateFormatter.format(new Date(user.created_at))}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card><CardHeader><CardTitle><h2>Preferences</h2></CardTitle></CardHeader><CardContent><PreferencesForm user={user} /></CardContent></Card>
      <Card><CardHeader><CardTitle><h2>Change password</h2></CardTitle></CardHeader><CardContent><PasswordForm /></CardContent></Card>
    </>
  );
}
