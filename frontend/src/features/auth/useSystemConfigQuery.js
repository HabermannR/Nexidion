import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';

export const useSystemConfigQuery = () => {
    return useQuery({
        queryKey: ['systemConfig'],
        queryFn: () => apiClient.get('/api/system/config').then(res => res.data),
        staleTime: Infinity,
        retry: false,
    });
};