import { ChevronDown } from "lucide-react";

import {
  Identity,
  ProfileCard,
  ProfileDivider,
  ProfileField,
  ProfileLinkRow,
  ProfileShell,
} from "@/components/features/profile/ProfileShell";

export default function ProfilePage() {
  return (
    <ProfileShell>
      <ProfileCard>
        <Identity
          initials="NA"
          name="Nora Al-Ashgar"
          email="n.al-ashgar@aramco.com"
        />

        <ProfileDivider />

        <div className="flex flex-col gap-5">
          <ProfileField label="Full Name">
            <input
              type="text"
              defaultValue="Nora Al-Ashgar"
              className="h-10 w-full rounded-md border border-auth-border bg-white px-3 text-sm text-auth-text outline-none focus:border-brand/60 focus:ring-2 focus:ring-brand/20"
            />
          </ProfileField>

          <ProfileField label="Email Address">
            <input
              type="email"
              defaultValue="n.al-ashgar@aramco.com"
              disabled
              className="h-10 w-full rounded-md border border-auth-border px-3 text-sm outline-none"
              style={{ backgroundColor: "#FAFAFA", color: "#9E9E9E" }}
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

        <div className="flex justify-end">
          <button
            type="button"
            className="h-10 rounded-md bg-brand px-5 text-sm font-medium text-white hover:bg-brand-hover"
          >
            Save Changes
          </button>
        </div>
      </ProfileCard>
    </ProfileShell>
  );
}
