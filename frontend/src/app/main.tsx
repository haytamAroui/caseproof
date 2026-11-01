import { createRoot } from 'react-dom/client';
import { App } from './App';
import { ErrorBoundary } from './ErrorBoundary';
import './theme.css';
const root = document.getElementById('root');
if (!root) throw Error('Application root missing');
createRoot(root).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
