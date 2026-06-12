"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addSteward,
  archiveDomain,
  createDomain,
  createSubdomain,
  listDomains,
  removeSteward,
  updateDomain,
} from "@/lib/api/products/ndmo-compliance/glossary.api";
import type {
  CreateDomainBody,
  CreateSubdomainBody,
  GlossaryDomain,
  GlossaryDomainNode,
} from "@/lib/types/ndmo-compliance/glossary";

import { GLOSSARY_NS } from "./useGlossary";

export function useGlossaryDomains(params: { include_archived?: boolean } = {}) {
  return useQuery({
    queryKey: [GLOSSARY_NS, "domains", params],
    queryFn: () => listDomains(params),
  });
}

/** Flat domain list → nested tree (top-level nodes first). */
export function buildDomainTree(domains: GlossaryDomain[]): GlossaryDomainNode[] {
  const byId = new Map<string, GlossaryDomainNode>();
  domains.forEach((d) => byId.set(d.id, { ...d, children: [] }));
  const roots: GlossaryDomainNode[] = [];
  byId.forEach((node) => {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

export function useCreateDomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateDomainBody) => createDomain(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "domains"] }),
  });
}

export function useCreateSubdomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ parentId, body }: { parentId: string; body: CreateSubdomainBody }) =>
      createSubdomain(parentId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "domains"] }),
  });
}

export function useUpdateDomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<CreateDomainBody> }) =>
      updateDomain(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "domains"] }),
  });
}

export function useArchiveDomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => archiveDomain(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "domains"] }),
  });
}

export function useAssignSteward() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ domainId, userId }: { domainId: string; userId: number }) =>
      addSteward(domainId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "domains"] }),
  });
}

export function useRemoveSteward() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ domainId, userId }: { domainId: string; userId: number }) =>
      removeSteward(domainId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: [GLOSSARY_NS, "domains"] }),
  });
}
