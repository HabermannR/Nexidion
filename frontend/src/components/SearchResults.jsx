import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import './SearchResults.css';

function SearchResults() {
  const location = useLocation();
  const { results, query } = location.state || { results: [], query: '' };

  return (
    <div className="search-results">
      <h2 className="MenuTitle">Search Results for "{query}"</h2>
      <div className="MenuContainer">
        {results.length === 0 ? (
          <p className="no-results">No results found.</p>
        ) : (
          <ul className="MenuList results-list">
            {results.map((result) => (
              <li key={result.id} className="result-item">
                <Link to={`/nodes/${encodeURIComponent(result.path)}`} className="result-link">
                  <h3 className="result-title">{result.title}</h3>
                  <p className="result-content">{result.content}</p>
                  <span className="similarity-score">
                    Relevance: {(result.similarity * 100).toFixed(2)}%
                  </span>
                  <div className="node-path">{result.path}</div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default SearchResults;