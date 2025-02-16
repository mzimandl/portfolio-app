import React from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter as Router } from 'react-router-dom';
import './index.css';
import App from './App';
import { Config } from './common';


export function initPage(config:Config) {
  const root = createRoot(document.getElementById('root') as Element);

  root.render(
    <Router>
      <React.StrictMode>
        <App config={config} />
      </React.StrictMode>
    </Router>
  );
}

document.addEventListener('DOMContentLoaded', () => {
  const configScript = document.getElementById('config') as HTMLDivElement;
  const config: Config = JSON.parse(configScript.textContent || '{}');
  initPage(config);
});