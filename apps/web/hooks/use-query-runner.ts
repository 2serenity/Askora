"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { QueryRequest } from "@/types/api";

export function useQueryRunner() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: QueryRequest) => api.runQuery(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["query-history"] });
    }
  });
}

