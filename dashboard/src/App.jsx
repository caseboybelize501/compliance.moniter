import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import ControlMatrix from './pages/ControlMatrix';
import ViolationFeed from './pages/ViolationFeed';
import EvidenceViewer from './pages/EvidenceViewer';
import AuditPackage from './pages/AuditPackage';
import RemediationBoard from './pages/RemediationBoard';
import Integrations from './pages/Integrations';

function App() {
  return (
    <Router>
      <div className="App">
        <header className="App-header">
          <h1>ACMP Dashboard</h1>
          <nav>
            <a href="/controls">Controls</a>
            <a href="/violations">Violations</a>
            <a href="/evidence">Evidence</a>
            <a href="/reports">Reports</a>
            <a href="/remediation">Remediation</a>
            <a href="/integrations">Integrations</a>
          </nav>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Navigate to="/controls" replace />} />
            <Route path="/controls" element={<ControlMatrix />} />
            <Route path="/violations" element={<ViolationFeed />} />
            <Route path="/evidence" element={<EvidenceViewer />} />
            <Route path="/reports" element={<AuditPackage />} />
            <Route path="/remediation" element={<RemediationBoard />} />
            <Route path="/integrations" element={<Integrations />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
