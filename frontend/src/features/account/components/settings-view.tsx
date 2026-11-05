"use client";

import { Bell, Lock } from "lucide-react";

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

      <div className="grid gap-4 md:grid-cols-2">
        <ComingSoonCard
          icon={Bell}
          title="Notification preferences"
          description="Choose which complaint updates you hear about."
        />
        <ComingSoonCard
          icon={Lock}
          title="Privacy settings"
          description="Control what personal details are included in complaints."
        />
      </div>
    </>
  );
}

function ComingSoonCard({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof Bell;
  title: string;
  description: string;
}) {
  return (
    <Card>
      <CardHeader>
        <span className="mb-2 flex size-10 items-center justify-center rounded-lg bg-secondary text-navy">
          <Icon className="size-5" aria-hidden />
        </span>
        <CardTitle>
          <h2>{title}</h2>
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <span className="rounded-full border border-dashed border-input px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
          Available in a later milestone
        </span>
      </CardContent>
    </Card>
  );
}
