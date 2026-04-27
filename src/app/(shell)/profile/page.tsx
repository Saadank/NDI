"use client";

import { ChevronDown } from "lucide-react";

import {
  Identity,
  ProfileCard,
  ProfileDivider,
  ProfileField,
  ProfileLinkRow,
  ProfileShell,
} from "@/components/features/profile/ProfileShell";
import { useCurrentUser } from "@/lib/hooks/platform/useAuth";
import { useAuthStore } from "@/lib/store/auth.store";

export default function ProfilePage() {
  // The auth store is hydrated from localStorage at login. We additionally
  // refetch /users/me via React Query so the profile reflects any changes
  // made server-side since this session was created.
  const userQuery = useCurrentUser();
  const storeUser = useAuthStore((s) => s.user);
  const user = userQuery.data ?? storeUser;

  const fullName = user
    ? `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || user.email
    : "—";
  const initials = user
    ? `${user.first_name?.[0] ?? ""}${user.last_name?.[0] ?? ""}`.toUpperCase() ||
      user.email[0].toUpperCase()
    : "?";

  return (
    <ProfileShell>
      <ProfileCard>
        <Identity
          initials={initials}
          name={fullName}
          email={user?.email ?? "—"}
        />

        <ProfileDivider />

        <div className="flex flex-col gap-5">
          <ProfileField label="Full Name">
            <input
              type="text"
              defaultValue={fullName}
              className="h-10 w-full rounded-md border border-auth-border bg-white px-3 text-sm text-auth-text outline-none focus:border-brand/60 focus:ring-2 focus:ring-brand/20"
            />
          </ProfileField>

          <ProfileField label="Email Address">
            <input
              type="email"
              defaultValue={user?.email ?? ""}
              disabled
              className="h-10 w-full rounded-md border border-auth-border px-3 text-sm outline-none"
              style={{ backgroundColor: "#FAFAFA", color: "#9E9E9E" }}
            />
          </ProfileField>

          <ProfileField label="Role">
            <input
              type="text"
              value={user?.product_role ?? user?.platform_role ?? "—"}
              disabled
              className="h-10 w-full rounded-md border border-auth-border px-3 text-sm outline-none"
              style={{ backgroundColor: "#FAFAFA", color: "#9E9E9E" }}
              readOnly
            />
          </ProfileField>

          <ProfileField label="Language">
            <div className="relative">
              <select
                defaultValue="en"
                className="h-10 w-full appearance-none rounded-md border border-auth-border bg-white pl-3 pr-9 text-sm text-auth-text outline-none focus:border-brand/60 focus:ring-2 focus:ring-brand/20"
              >
                <option value="en">English</option>
                <option value="ar">العربية</option>
              </select>
              <ChevronDown
                className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2"
                style={{ color: "#BABABA" }}
              />
            </div>
          </ProfileField>
        </div>

        <ProfileDivider />

        <div className="flex flex-col">
          <ProfileLinkRow label="Change Password" href="/profile/password" />
          <ProfileLinkRow
            label="Notification Preferences"
            href="/profile/notifications"
          />
          <ProfileLinkRow label="Delegation Settings" href="/delegation" last />
        </div>
      </ProfileCard>
    </ProfileShell>
  );
}
