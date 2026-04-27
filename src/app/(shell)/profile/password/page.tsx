import Link from "next/link";
import { Shield } from "lucide-react";

import { Breadcrumb } from "@/components/shared/Breadcrumb";
import { PasswordInput } from "@/components/features/profile/PasswordInput";
import {
  ProfileCard,
  ProfileField,
} from "@/components/features/profile/ProfileShell";

export default function ChangePasswordPage() {
  return (
    <main className="flex-1 flex flex-col gap-6 px-[240px] py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Profile", href: "/profile" },
          { label: "Change Password" },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">Change Password</h1>

      <ProfileCard>
        <div
          className="flex items-center gap-[10px] rounded-md p-3"
          style={{
            backgroundColor: "#FFF5F0",
            border: "1px solid #FDDCCC",
          }}
        >
          <Shield className="h-4 w-4 shrink-0 text-brand" />
          <p className="text-[13px] font-normal text-brand">
            Your password must be at least 8 characters and include a number.
          </p>
        </div>

        <div className="flex flex-col gap-5">
          <ProfileField label="Current Password">
            <PasswordInput
              name="current_password"
              defaultValue="••••••••••••"
            />
          </ProfileField>
          <ProfileField label="New Password">
            <PasswordInput name="new_password" focused />
          </ProfileField>
          <ProfileField label="Confirm New Password">
            <PasswordInput name="confirm_password" />
          </ProfileField>
        </div>

        <div className="flex justify-end gap-3">
          <Link
            href="/profile"
            className="inline-flex h-10 items-center rounded-md border border-auth-border bg-white px-5 text-sm font-medium text-auth-text hover:bg-auth-bg"
          >
            Cancel
          </Link>
          <button
            type="button"
            className="h-10 rounded-md bg-brand px-5 text-sm font-medium text-white hover:bg-brand-hover"
          >
            Save Password
          </button>
        </div>
      </ProfileCard>
    </main>
  );
}
