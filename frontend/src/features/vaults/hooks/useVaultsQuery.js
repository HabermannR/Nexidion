// src/features/vaults/hooks/useVaultsQuery.js
//
// Single source of truth for the ['allVaults'] cache key.
//
// Uses ETag-based conditional GET requests. On a 304 Not Modified response,
// TanStack Query v5 requires the queryFn to return a defined value — returning
// undefined throws "Query data cannot be undefined". The fix: read the current
// cached value from queryClient inside the queryFn and return it directly when
// the server says nothing has changed.

import { useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../../api/apiClient.js';

export const useVaultsQuery = () => {
    const etagRef = useRef(null);
    const queryClient = useQueryClient();

    return useQuery({
        queryKey: ['allVaults'],
        queryFn: async () => {
            const headers = {};
            if (etagRef.current) {
                headers['If-None-Match'] = etagRef.current;
            }
            const res = await apiClient.get('/api/vaults/', {
                headers,
                validateStatus: s => s < 500,
            });
            if (res.status === 304) {
                // Return the current cached value — TQ v5 forbids returning undefined.
                return queryClient.getQueryData(['allVaults']);
            }
            const etag = res.headers['etag'];
            if (etag) etagRef.current = etag;
            return res.data;
        },
    });
};
