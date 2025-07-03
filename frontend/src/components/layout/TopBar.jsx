import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Navbar from 'react-bootstrap/Navbar';
import Nav from 'react-bootstrap/Nav';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import logo from '../../assets/logo.svg';

function TopBar() {
  const navigate = useNavigate();
  const { isLoggedIn, logout } = useAuth();

  const validModels = [
    'claude-sonnet-4-20250514',
    'gpt-4o',
    'o4-mini-2025-04-16',
    'gpt-4.1-mini-2025-04-14',
    'gemini-2.5-pro'
  ];

  const getInitialModel = () => {
    const storedModel = localStorage.getItem('selectedModel');
    return storedModel && validModels.includes(storedModel) ? storedModel : validModels[0];
  };

  const [selectedModel, setSelectedModel] = useState(getInitialModel());

  useEffect(() => {
    localStorage.setItem('selectedModel', selectedModel);
  }, [selectedModel]);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <Navbar bg="dark" variant="dark" expand="lg" className="px-3">
        <Navbar.Brand as={Link} to="/nodes">
          <img
            src={logo}
            width="30"
            height="30"
            className="d-inline-block align-top me-2"
            alt="CorteXtract Logo"
          />
          Projekt: Befreiung
        </Navbar.Brand>
        
        <Navbar.Toggle aria-controls="basic-navbar-nav" />

        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="ms-auto align-items-center">
            {isLoggedIn && (
              <>
                <div className="d-flex align-items-center me-lg-3 text-light mb-2 mb-lg-0">
                  <span className="me-2">LLM:</span>
                  <Form.Select size="sm" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
					<option value="gemini-2.5-pro">gemini-2.5-pro</option>
                    <option value="claude-sonnet-4-20250514">claude sonnet 4</option>
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="o4-mini-2025-04-16">o4 mini</option>
                    <option value="gpt-4.1-mini-2025-04-14">GPT-4.1</option>
                  </Form.Select>
                </div>
                <Button variant="outline-light" size="sm" onClick={handleLogout}>
                  Log Out
                </Button>
              </>
            )}
            {!isLoggedIn && (
              <Nav.Link as={Link} to="/">Log In</Nav.Link>
            )}
          </Nav>
        </Navbar.Collapse>
    </Navbar>
  );
}

export default TopBar;