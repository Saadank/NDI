import type { RequestFile } from "@/lib/types/data-sharing/file.types";

export interface FileAttachmentsProps {
  requestId: number;
  files: RequestFile[];
}

export function FileAttachments(_props: FileAttachmentsProps) {
  return null;
}
