import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

function NodeList() {
  const navigate = useNavigate();

  useEffect(() => {
    const getFirstNodeAndRedirect = async () => {
      try {
        // We just need the tree to find the first node
        const response = await api.get('/api/nodes/tree');
        const treeData = response.data;

        if (treeData && treeData.length > 0) {
          // Found nodes, redirect to the very first one
          const firstNodeId = treeData[0].id;
          navigate(`/nodes/${firstNodeId}`, { replace: true });
        } else {
          // No nodes exist yet. Maybe redirect to a "create your first node" page?
          // For now, let's just show a message.
          navigate('/nodes/new'); // Or handle this case as you see fit
        }
      } catch (error) {
        console.error("Could not fetch node tree for redirection:", error);
        // Handle error, maybe show an error page
      }
    };

    getFirstNodeAndRedirect();
  }, [navigate]);

  // This component will only show "Loading..." briefly while it redirects.
  return <div>Loading...</div>;
}

export default NodeList;