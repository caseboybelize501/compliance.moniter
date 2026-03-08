import React, { useState, useEffect } from 'react';
import { controlsApi } from '../api/client';

function ControlMatrix() {
  const [controls, setControls] = useState([]);
  const [framework, setFramework] = useState('soc2');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchControls = async () => {
      try {
        const response = await controlsApi.list(framework);
        setControls(response.data.controls || []);
      } catch (error) {
        console.error('Failed to fetch controls:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchControls();
  }, [framework]);

  if (loading) return <div>Loading controls...</div>;

  return (
    <div className="control-matrix">
      <h2>Control Matrix - {framework.toUpperCase()}</h2>
      <select value={framework} onChange={(e) => setFramework(e.target.value)}>
        <option value="soc2">SOC 2</option>
        <option value="hipaa">HIPAA</option>
        <option value="gdpr">GDPR</option>
        <option value="iso27001">ISO 27001</option>
      </select>
      <table>
        <thead>
          <tr>
            <th>Control ID</th>
            <th>Name</th>
            <th>Status</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {controls.map((control) => (
            <tr key={control.id}>
              <td>{control.id}</td>
              <td>{control.name}</td>
              <td>{control.status}</td>
              <td>{control.evidence_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default ControlMatrix;
