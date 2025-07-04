// src/components/layout/MainLayout.jsx (Version mit breiteren Mobile-Overlays)

import React from 'react';
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Button from 'react-bootstrap/Button';
import Accordion from 'react-bootstrap/Accordion';

import './MainLayout.css';

function MainLayout({ 
  treeView, 
  mainContent, 
  contextPanel, 
  versionHistory, 
  onToggleTree, 
  onToggleContext, 
  onToggleVersions 
}) {
    
  return (
    <Container fluid className="main-layout-container">
      <Row className="main-layout-row g-0">
        
        {/* SPALTE 1: TREE (nur Desktop) */}
        <Col 
          lg={3} 
          className="d-none d-lg-flex tree-column p-0"
        >
          {treeView}
        </Col>

        {/* SPALTE 2: CONTENT (Desktop und Mobil) */}
        <Col 
          xs={12} 
          lg={6} 
          className="main-content-col order-2 order-lg-2"
        >
          {mainContent}
        </Col>

        {/* MOBILE AKTIONSLEISTE */}
        <Col 
          xs={12} 
          className="order-1 d-lg-none"
        >
          <Row className="g-2 p-3 align-items-center bg-light border-bottom">
            <Col>
              <Button variant="outline-secondary" className="w-100" onClick={onToggleTree}>
                ☰ Navigation
              </Button>
            </Col>
            
            <Col>
              <Button variant="outline-secondary" className="w-100" onClick={onToggleVersions}>
                🕒 Versionen
              </Button>
            </Col>
            
            <Col>
              <Button variant="outline-secondary" className="w-100" onClick={onToggleContext}>
                ⚙️ Context  
              </Button>
            </Col>
          </Row>
        </Col>

        {/* DESKTOP CONTEXT/VERSION-SPALTE */}
        <Col 
          lg={3} 
          className="d-none d-lg-block order-lg-3 context-panel-col"
        >
          <div className="desktop-sidebar-wrapper">
             {contextPanel}
             <hr className="my-3" />
             {versionHistory}
          </div>
        </Col>

      </Row>
    </Container>
  );
}

export default MainLayout;