// src/features/nodes/hooks/useVaultTreeQuery.js

import { useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../../api/apiClient.js';

const flattenTree = (tree) => {
    const flatList = [];
    if (!Array.isArray(tree)) return flatList;
    const stack = [...tree];
    while (stack.length > 0) {
        const node = stack.pop();
        if (!node) continue;
        const { children, ...nodeWithoutChildren } = node;
        flatList.push(nodeWithoutChildren);
        if (Array.isArray(children) && children.length > 0) {
            stack.push(...children);
        }
    }
    return flatList;
};

export const useVaultTreeQuery = (vaultId) => {
    const etagRef = useRef(null);
    const queryClient = useQueryClient();

    return useQuery({
        queryKey: ['vaultTree', vaultId],
        queryFn: async () => {
            const headers = {};
            if (etagRef.current) {
                headers['If-None-Match'] = etagRef.current;
            }
            const res = await apiClient.get(
                `/api/vaults/${vaultId}/nodes/`,
                { headers, validateStatus: s => s < 500 }
            );
            if (res.status === 304) {
                // Return the current cached value — TQ v5 forbids returning undefined.
                return queryClient.getQueryData(['vaultTree', vaultId]);
            }
            const etag = res.headers['etag'];
            if (etag) etagRef.current = etag;
            return res.data;
        },
        enabled: !!vaultId,
        select: (apiResponseTree) => {
            const tree = apiResponseTree || [];
            return {
                tree,
                allNodesFlat: flattenTree(tree),
            };
        },
    });
};
