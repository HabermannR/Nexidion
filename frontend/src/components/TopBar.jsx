import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../api/axios';
import './TopBar.css'; 
import logo from '../assets/logo.svg';

function TopBar() {
  // --- Hooks ---
  const navigate = useNavigate();
  const { isLoggedIn, isAdmin, logout } = useAuth();

  // --- State ---
  const validModels = [
    'claude-sonnet-4-20250514',
    'gpt-4o',
    'o4-mini-2025-04-16',
    'gpt-4.1-mini-2025-04-14',
    'local'
  ];

  const getInitialModel = () => {
    const storedModel = localStorage.getItem('selectedModel');
    if (storedModel && validModels.includes(storedModel)) {
      return storedModel;
    }
    return validModels[0]; // Default to the first valid model
  };

  const [selectedModel, setSelectedModel] = useState(getInitialModel());
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  // --- Effect to save model to localStorage ---
  useEffect(() => {
    localStorage.setItem('selectedModel', selectedModel);
  }, [selectedModel]);

  // --- Handlers ---

  // *** FIX 1: This now calls the REAL logout function from the AuthContext ***
  const handleLogout = () => {
    logout(); // This clears the user's token and auth state
    navigate('/'); // Then, this redirects them to the login page
  };

  const handleModelChange = (e) => {
    setSelectedModel(e.target.value);
  };

  // --- Render (JSX) ---
  // This JSX is cleaned up and structured like your original component
  return (
    <div className="top-bar">
      <Link to="/nodes" className="logo-link">
        <img src={logo} alt="CorteXtract Logo" className="logo" />
        Projekt: Befreiung
      </Link>
      
       <div className="top-bar-right">
        {isLoggedIn && (
          <div className="selectors-container">
            <div className="model-selector">
              LLM:
              <select value={selectedModel} onChange={handleModelChange}>
                <option value="claude-sonnet-4-20250514">claude sonnet 4</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="o4-mini-2025-04-16">o4 mini</option>
                <option value="gpt-4.1-mini-2025-04-14">GPT-4.1</option>
              </select>
            </div>

          </div>
        )}

        <div className="nav-links">
          {isLoggedIn ? (
            <>
              <button onClick={handleLogout}>Log Out</button>
            </>
          ) : (
            <Link to="/">Log In</Link>
          )}
        </div>
      </div>
    </div>
  );
}

export default TopBar;